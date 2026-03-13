from __future__ import annotations

import json
from collections import Counter
from typing import Any


class EnvironmentAnalyzer:
    # Configurable thresholds
    THRESHOLDS = {
        "snmp_min": 50,
        "disabled_items_min": 100,
        "trigger_problem_min": 10,
        "proxy_stale_seconds": 300,
    }

    def __init__(
        self,
        hosts: list[dict[str, Any]],
        templates: list[dict[str, Any]],
        items: list[dict[str, Any]],
        triggers: list[dict[str, Any]] | None = None,
        proxies: list[dict[str, Any]] | None = None,
        internal_metrics: list[dict[str, Any]] | None = None,
        frontend_url: str | None = None,
        thresholds: dict | None = None,
    ):
        self.hosts = hosts
        self.templates = templates
        self.items = items
        self.triggers = triggers or []
        self.proxies = proxies or []
        self.internal_metrics = internal_metrics or []
        self.frontend_url = frontend_url.rstrip("/") if frontend_url else None
        if thresholds:
            self.THRESHOLDS = {**self.THRESHOLDS, **thresholds}

    # ── Link helpers ──────────────────────────────────────────────────────────

    def _host_link(self, hostid: str) -> str | None:
        if not self.frontend_url:
            return None
        return f"{self.frontend_url}/zabbix.php?action=host.edit&hostid={hostid}"

    def _template_link(self, templateid: str) -> str | None:
        if not self.frontend_url:
            return None
        return f"{self.frontend_url}/zabbix.php?action=template.edit&templateid={templateid}"

    # ── Analysis helpers ──────────────────────────────────────────────────────

    def _analyze_triggers(self) -> dict[str, int]:
        disabled = sum(1 for t in self.triggers if str(t.get("status", "0")) == "1")
        in_problem = sum(1 for t in self.triggers if str(t.get("value", "0")) == "1")
        with_error = sum(1 for t in self.triggers if t.get("error"))
        return {
            "total_triggers": len(self.triggers),
            "disabled_triggers": disabled,
            "problem_triggers": in_problem,
            "error_triggers": with_error,
        }

    def _analyze_proxies(self) -> dict[str, Any]:
        if not self.proxies:
            return {"total_proxies": 0, "stale_proxies": 0, "proxy_host_counts": []}
        import time
        now = int(time.time())
        stale = []
        proxy_host_counts = []
        for p in self.proxies:
            last = int(p.get("lastaccess") or 0)
            is_stale = (now - last) > self.THRESHOLDS["proxy_stale_seconds"] if last else True
            if is_stale:
                stale.append(p.get("host", "unknown"))
            proxy_host_counts.append({
                "name": p.get("host", "unknown"),
                "value": len(p.get("hosts") or []),
            })
        return {
            "total_proxies": len(self.proxies),
            "stale_proxies": len(stale),
            "stale_proxy_names": stale,
            "proxy_host_counts": sorted(proxy_host_counts, key=lambda x: -x["value"])[:10],
        }

    def _analyze_item_types(self) -> dict[str, int]:
        type_map = {
            "0": "Zabbix agent",
            "2": "Zabbix trapper",
            "3": "Simple check",
            "5": "Zabbix internal",
            "7": "Zabbix agent (active)",
            "9": "Web item",
            "10": "External check",
            "11": "Database monitor",
            "12": "IPMI agent",
            "13": "SSH agent",
            "14": "TELNET agent",
            "15": "Calculated",
            "16": "JMX agent",
            "17": "SNMP trap",
            "18": "Dependent item",
            "19": "HTTP agent",
            "20": "SNMP agent",
            "21": "Script",
        }
        counter: Counter[str] = Counter()
        for item in self.items:
            t = str(item.get("type", "0"))
            counter[type_map.get(t, f"Type {t}")] += 1
        return dict(counter.most_common(8))

    def _build_poller_tuning(self, item_types: dict, totals: dict, proxy_data: dict) -> list[dict]:
        """
        Gera sugestões de parâmetros do zabbix_server.conf / zabbix_proxy.conf
        com base na distribuição de itens coletados.
        """
        # Contagens por grupo de poller
        passive_agent  = item_types.get("Zabbix agent", 0)
        active_agent   = item_types.get("Zabbix agent (active)", 0)
        trapper        = item_types.get("Zabbix trapper", 0)
        simple         = item_types.get("Simple check", 0)
        snmp           = (item_types.get("SNMP agent", 0)
                          + totals.get("snmp_candidates", 0))
        ipmi           = item_types.get("IPMI agent", 0)
        jmx            = item_types.get("JMX agent", 0)
        http           = item_types.get("HTTP agent", 0)
        external       = item_types.get("External check", 0)
        calculated     = item_types.get("Calculated", 0)
        total          = totals.get("items", 0)
        n_proxies      = proxy_data.get("total_proxies", 0)

        # Carga efetiva no server (proxies absorvem parte)
        # Estimativa conservadora: cada proxy absorve ~30% da carga média
        load_factor = max(0.4, 1 - (n_proxies * 0.25))

        def suggest(count: int, per_poller: int, minimum: int = 1) -> int:
            return max(minimum, round((count * load_factor) / per_poller))

        suggestions = []

        # StartPollers — itens passivos (agent, simple check, external, calculated)
        passive_total = passive_agent + simple + external + calculated
        sp = suggest(passive_total, per_poller=800, minimum=5)
        suggestions.append({
            "param": "StartPollers",
            "current_default": 5,
            "suggested": sp,
            "impact": "high" if sp > 5 else "ok",
            "reason": (
                f"{passive_total} itens passivos detectados "
                f"({'distribuídos em ' + str(n_proxies) + ' proxies, ' if n_proxies else ''}"
                f"carga estimada no server: {int(passive_total * load_factor)})."
            ),
        })

        # StartPollersUnreachable — hosts indisponíveis
        unavail = totals.get("unavailable_hosts", 0)
        spu = max(1, min(unavail // 10 + 1, 10))
        suggestions.append({
            "param": "StartPollersUnreachable",
            "current_default": 1,
            "suggested": spu,
            "impact": "high" if unavail > 20 else "ok",
            "reason": (
                f"{unavail} hosts indisponíveis detectados. "
                "Aumentar evita bloqueio do poller principal."
            ),
        })

        # StartTrappers — active agent + trapper
        trappers_load = active_agent + trapper
        st = suggest(trappers_load, per_poller=1000, minimum=5)
        suggestions.append({
            "param": "StartTrappers",
            "current_default": 5,
            "suggested": st,
            "impact": "high" if st > 5 else "ok",
            "reason": f"{trappers_load} itens de agente ativo/trapper detectados.",
        })

        # StartSNMPTrapper / SNMP pollers
        if snmp > 0:
            snmp_p = suggest(snmp, per_poller=300, minimum=1)
            suggestions.append({
                "param": "StartPollers (SNMP)",
                "current_default": "incluso no StartPollers",
                "suggested": f"+{snmp_p} dedicados",
                "impact": "high" if snmp > 500 else "medium",
                "reason": (
                    f"{snmp} itens SNMP detectados. "
                    "No Zabbix 7+ considere coleta SNMP assíncrona (bulk walk)."
                ),
            })

        # StartHTTPPollers
        if http > 0:
            shp = suggest(http, per_poller=500, minimum=1)
            suggestions.append({
                "param": "StartHTTPPollers",
                "current_default": 1,
                "suggested": shp,
                "impact": "medium" if shp > 1 else "ok",
                "reason": f"{http} itens HTTP agent detectados.",
            })

        # StartIPMIPollers
        if ipmi > 0:
            sip = max(1, ipmi // 100)
            suggestions.append({
                "param": "StartIPMIPollers",
                "current_default": 0,
                "suggested": sip,
                "impact": "medium",
                "reason": f"{ipmi} itens IPMI detectados. Padrão é 0 (desabilitado).",
            })

        # StartJavaPollers
        if jmx > 0:
            sjp = max(5, jmx // 200)
            suggestions.append({
                "param": "StartJavaPollers",
                "current_default": 0,
                "suggested": sjp,
                "impact": "medium",
                "reason": f"{jmx} itens JMX detectados. Requer JavaGateway configurado.",
            })

        # CacheSize — estimativa grosseira
        cache_mb = max(8, total // 5000 * 8)
        suggestions.append({
            "param": "CacheSize",
            "current_default": "8M",
            "suggested": f"{cache_mb}M",
            "impact": "medium" if cache_mb > 8 else "ok",
            "reason": (
                f"{total} itens no ambiente. "
                "CacheSize insuficiente causa queda de performance e erros de inicialização."
            ),
        })

        # HistoryCacheSize
        hist_mb = max(16, total // 2000 * 16)
        suggestions.append({
            "param": "HistoryCacheSize",
            "current_default": "16M",
            "suggested": f"{hist_mb}M",
            "impact": "medium" if hist_mb > 16 else "ok",
            "reason": (
                f"Com {total} itens e coleta frequente, cache pequeno causa flush prematuro."
            ),
        })

        return suggestions

    def _build_proxy_tuning(self, item_types: dict, totals: dict) -> list[dict]:
        """
        Gera sugestões de zabbix_proxy.conf por proxy,
        estimando a carga de cada um com base nos hosts que gerencia.
        """
        if not self.proxies:
            return []

        total_hosts = max(totals.get("hosts", 1), 1)
        total_items = totals.get("items", 0)
        avg_items_per_host = total_items / total_hosts

        # Ratios de tipo de item para distribuição proporcional por proxy
        def ratio(key: str) -> float:
            return item_types.get(key, 0) / max(total_items, 1)

        r_passive = ratio("Zabbix agent") + ratio("Simple check") + ratio("External check") + ratio("Calculated")
        r_active  = ratio("Zabbix agent (active)") + ratio("Zabbix trapper")
        r_snmp    = totals.get("snmp_candidates", 0) / max(total_items, 1)
        r_http    = ratio("HTTP agent")
        r_ipmi    = ratio("IPMI agent")
        r_jmx     = ratio("JMX agent")

        def suggest(count: int, per_poller: int, minimum: int = 1) -> int:
            return max(minimum, round(count / per_poller))

        result = []
        for proxy in self.proxies:
            name = proxy.get("host") or proxy.get("name") or f"proxy-{proxy.get('proxyid','?')}"
            n_hosts = len(proxy.get("hosts") or [])
            # Se o proxy não retornou lista de hosts, faz estimativa proporcional
            est_items = int(avg_items_per_host * n_hosts) if n_hosts else int(total_items / len(self.proxies))

            passive = int(est_items * r_passive)
            active  = int(est_items * r_active)
            snmp    = int(est_items * r_snmp)
            http    = int(est_items * r_http)
            ipmi    = int(est_items * r_ipmi)
            jmx     = int(est_items * r_jmx)

            sug: list[dict] = []

            # StartPollers
            sp = suggest(passive, 800, 2)
            sug.append({"param": "StartPollers", "current_default": 5, "suggested": sp,
                        "impact": "high" if sp > 5 else "ok",
                        "reason": f"~{passive} itens passivos estimados ({n_hosts} hosts)."})

            # StartPollersUnreachable
            spu = max(1, n_hosts // 25)
            sug.append({"param": "StartPollersUnreachable", "current_default": 1, "suggested": spu,
                        "impact": "ok",
                        "reason": f"{n_hosts} hosts sob este proxy."})

            # StartTrappers
            st = suggest(active, 1000, 2)
            sug.append({"param": "StartTrappers", "current_default": 5, "suggested": st,
                        "impact": "ok" if st <= 5 else "medium",
                        "reason": f"~{active} itens ativos/trapper estimados."})

            # SNMP
            if snmp > 0:
                snmp_p = suggest(snmp, 300, 1)
                sug.append({"param": "StartPollers (SNMP)", "current_default": "incluso", "suggested": f"+{snmp_p}",
                            "impact": "high" if snmp > 300 else "medium",
                            "reason": f"~{snmp} itens SNMP estimados. Considere bulk walk no Zabbix 7+."})

            # HTTP
            if http > 0:
                shp = suggest(http, 500, 1)
                sug.append({"param": "StartHTTPPollers", "current_default": 1, "suggested": shp,
                            "impact": "medium" if shp > 1 else "ok",
                            "reason": f"~{http} itens HTTP estimados."})

            # IPMI
            if ipmi > 0:
                sug.append({"param": "StartIPMIPollers", "current_default": 0, "suggested": max(1, ipmi // 100),
                            "impact": "medium", "reason": f"~{ipmi} itens IPMI estimados."})

            # JMX
            if jmx > 0:
                sug.append({"param": "StartJavaPollers", "current_default": 0, "suggested": max(5, jmx // 200),
                            "impact": "medium", "reason": f"~{jmx} itens JMX. Requer JavaGateway configurado."})

            # ConfigFrequency — menos hosts = pode ser maior (menos mudanças)
            cfg = 3600 if n_hosts < 100 else (1800 if n_hosts < 500 else 900)
            sug.append({"param": "ConfigFrequency", "current_default": 3600, "suggested": cfg,
                        "impact": "medium" if cfg < 3600 else "ok",
                        "reason": f"Com {n_hosts} hosts, sincronização mais frequente reduz delay em mudanças."})

            # CacheSize
            cache_mb = max(8, est_items // 5000 * 8)
            sug.append({"param": "CacheSize", "current_default": "8M", "suggested": f"{cache_mb}M",
                        "impact": "medium" if cache_mb > 8 else "ok",
                        "reason": f"Cache de configuração para ~{est_items} itens."})

            # ProxyMemoryBufferSize (Zabbix 6.4+)
            buf_mb = max(16, est_items // 2000 * 16)
            sug.append({"param": "ProxyMemoryBufferSize", "current_default": "16M", "suggested": f"{buf_mb}M",
                        "impact": "medium" if buf_mb > 16 else "ok",
                        "reason": "Buffer de dados coletados aguardando envio ao servidor."})

            result.append({
                "proxy_name": name,
                "host_count": n_hosts,
                "estimated_items": est_items,
                "suggestions": sug,
            })

        return result

    def _build_chart_data(
        self,
        totals: dict,
        top_hosts: list,
        top_templates: list,
        item_types: dict,
        proxy_data: dict,
    ) -> dict:
        return {
            "kpi_donut": {
                "labels": ["Ativos", "Desabilitados", "Não Suportados"],
                "values": [
                    max(0, totals["items"] - totals["disabled_items"] - totals["unsupported_items"]),
                    totals["disabled_items"],
                    totals["unsupported_items"],
                ],
                "colors": ["#2ecc71", "#6ea8fe", "#ff6b6b"],
            },
            "top_hosts_bar": {
                "labels": [h["name"][:25] for h in top_hosts],
                "values": [h["value"] for h in top_hosts],
            },
            "top_templates_bar": {
                "labels": [t["name"][:25] for t in top_templates],
                "values": [t["value"] for t in top_templates],
            },
            "item_types_pie": {
                "labels": list(item_types.keys()),
                "values": list(item_types.values()),
            },
            "proxy_bar": {
                "labels": [p["name"][:20] for p in proxy_data.get("proxy_host_counts", [])],
                "values": [p["value"] for p in proxy_data.get("proxy_host_counts", [])],
            },
        }

    def _build_recommendations(
        self,
        totals: dict,
        trigger_data: dict,
        proxy_data: dict,
    ) -> list[dict[str, str | None]]:
        recs: list[dict[str, str | None]] = []
        u = totals["unsupported_items"]
        snmp = totals["snmp_candidates"]
        dis_items = totals["disabled_items"]
        dis_hosts = totals["disabled_hosts"]

        if u > 0:
            recs.append({
                "severity": "high",
                "title": "Itens não suportados detectados",
                "detail": f"{u} itens em estado unsupported. Causas comuns: chave inválida, permissão negada, timeout ou agente inacessível.",
                "action": "Revisar erros dos itens, validar credenciais e conectividade. Use a correção automática para desabilitar ou remover.",
                "fix_action": "disable_unsupported",
                "link": self.frontend_url,
            })

        if trigger_data.get("problem_triggers", 0) >= self.THRESHOLDS["trigger_problem_min"]:
            n = trigger_data["problem_triggers"]
            recs.append({
                "severity": "high",
                "title": f"{n} triggers em estado PROBLEM",
                "detail": f"Alto número de triggers disparados simultaneamente pode indicar problema sistêmico ou triggers mal calibrados.",
                "action": "Revisar triggers com alta frequência de disparo. Ajustar thresholds e hysteresis.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        if trigger_data.get("error_triggers", 0) > 0:
            recs.append({
                "severity": "high",
                "title": f"{trigger_data['error_triggers']} triggers com erro de expressão",
                "detail": "Triggers com erro não avaliam corretamente e podem mascarar problemas reais.",
                "action": "Corrigir expressões de triggers inválidas.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        if proxy_data.get("stale_proxies", 0) > 0:
            names = ", ".join(proxy_data.get("stale_proxy_names", [])[:3])
            recs.append({
                "severity": "high",
                "title": f"{proxy_data['stale_proxies']} proxy(s) sem resposta recente",
                "detail": f"Proxies inacessíveis: {names}. Hosts monitorados por eles podem não estar sendo coletados.",
                "action": "Verificar conectividade e serviço do proxy Zabbix.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        if snmp >= self.THRESHOLDS["snmp_min"]:
            recs.append({
                "severity": "medium",
                "title": f"Carga SNMP relevante ({snmp} itens)",
                "detail": "Alto volume de itens SNMP pode saturar pollers. Avaliar modelo assíncrono (Zabbix 7+).",
                "action": "Revisar distribuição de pollers SNMP e considerar coleta assíncrona.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        if trigger_data.get("disabled_triggers", 0) > 0:
            recs.append({
                "severity": "medium",
                "title": f"{trigger_data['disabled_triggers']} triggers desabilitados",
                "detail": "Triggers desabilitados podem ser lixo técnico ou indicar gaps de monitoramento.",
                "action": "Auditar triggers desabilitados: reativar os relevantes e remover os obsoletos.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        if dis_items > self.THRESHOLDS["disabled_items_min"]:
            recs.append({
                "severity": "low",
                "title": f"{dis_items} itens desabilitados",
                "detail": "Volume alto de itens desabilitados sugere templates mal aproveitados ou lixo acumulado.",
                "action": "Limpar itens obsoletos. Use a correção automática para removê-los.",
                "fix_action": "delete_disabled_items",
                "link": self.frontend_url,
            })

        if dis_hosts > 0:
            recs.append({
                "severity": "low",
                "title": f"{dis_hosts} hosts desabilitados",
                "detail": "Hosts desabilitados acumulam configuração sem utilidade e poluem relatórios.",
                "action": "Validar se são necessários. Use a correção automática para remover ou reativar.",
                "fix_action": "manage_disabled_hosts",
                "link": self.frontend_url,
            })

        if not recs:
            recs.append({
                "severity": "info",
                "title": "Ambiente sem alertas críticos",
                "detail": "Nenhum gap evidente nas regras atuais. Bom sinal — continue monitorando tendências.",
                "action": "Analise o histórico para verificar tendências de crescimento.",
                "fix_action": None,
                "link": self.frontend_url,
            })

        return recs

    # ── Main ──────────────────────────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:
        unsupported_items = [i for i in self.items if str(i.get("state", "0")) == "1"]
        disabled_items = [i for i in self.items if str(i.get("status", "0")) == "1"]
        disabled_hosts = [h for h in self.hosts if str(h.get("status", "0")) == "1"]
        unavailable_hosts = [h for h in self.hosts if str(h.get("available", "0")) == "2"]

        snmp_candidates = [
            i for i in self.items
            if any(tok in (i.get("key_") or "").lower() for tok in ["snmp", "walk[", ".1.3.6"])
        ]

        # Item type distribution
        item_types = self._analyze_item_types()

        # Top hosts by item count
        host_counter: Counter[str] = Counter()
        host_meta: dict[str, tuple[str, str]] = {}
        for item in self.items:
            hostid = str(item.get("hostid", ""))
            hosts = item.get("hosts") or []
            host_name = hosts[0].get("name") if hosts else hostid
            host_counter[hostid] += 1
            host_meta[hostid] = (host_name, hostid)

        top_hosts = [
            {"name": host_meta[hid][0], "value": cnt, "link": self._host_link(hid)}
            for hid, cnt in host_counter.most_common(10)
        ]

        # Top templates by score
        template_counter: Counter[str] = Counter()
        template_meta: dict[str, tuple[str, str]] = {}
        for template in self.templates:
            tid = str(template.get("templateid", ""))
            name = template.get("name") or template.get("host") or tid
            score = max(len(template.get("hosts") or []), len(template.get("items") or []))
            template_counter[tid] = score
            template_meta[tid] = (name, tid)

        top_templates = [
            {"name": template_meta[tid][0], "value": cnt, "link": self._template_link(tid)}
            for tid, cnt in template_counter.most_common(10)
        ]

        trigger_data = self._analyze_triggers()
        proxy_data = self._analyze_proxies()

        totals = {
            "hosts": len(self.hosts),
            "templates": len(self.templates),
            "items": len(self.items),
            "triggers": trigger_data["total_triggers"],
            "unsupported_items": len(unsupported_items),
            "disabled_items": len(disabled_items),
            "disabled_hosts": len(disabled_hosts),
            "unavailable_hosts": len(unavailable_hosts),
            "snmp_candidates": len(snmp_candidates),
            "problem_triggers": trigger_data["problem_triggers"],
            "proxies": proxy_data["total_proxies"],
        }

        recommendations = self._build_recommendations(totals, trigger_data, proxy_data)
        poller_tuning = self._build_poller_tuning(item_types, totals, proxy_data)
        proxy_tuning = self._build_proxy_tuning(item_types, totals)
        chart_data = self._build_chart_data(totals, top_hosts, top_templates, item_types, proxy_data)

        return {
            "totals": totals,
            "top_hosts": top_hosts,
            "top_templates": top_templates,
            "recommendations": recommendations,
            "poller_tuning": poller_tuning,
            "proxy_tuning": proxy_tuning,
            "chart_data": chart_data,
            "trigger_data": trigger_data,
            "proxy_data": proxy_data,
            "item_types": item_types,
        }
