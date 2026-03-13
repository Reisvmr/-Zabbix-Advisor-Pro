from __future__ import annotations

from collections import Counter, defaultdict
from urllib.parse import quote

from app.schemas.report import (
    EnvironmentKPIs,
    HealthcheckReport,
    HostSummary,
    Recommendation,
    TemplateSummary,
)

SNMP_TYPES = {1, 4}


class HealthcheckAnalyzer:
    def __init__(self, frontend_url: str | None = None):
        self.frontend_url = frontend_url.rstrip("/") if frontend_url else None

    def _build_links(self) -> dict[str, str]:
        if not self.frontend_url:
            return {}
        return {
            "hosts": f"{self.frontend_url}/zabbix.php?action=host.list",
            "templates": f"{self.frontend_url}/zabbix.php?action=template.list",
            "items": f"{self.frontend_url}/zabbix.php?action=item.list",
            "unsupported": f"{self.frontend_url}/zabbix.php?action=problem.view",
            "search_snmp": f"{self.frontend_url}/zabbix.php?action=item.list&filter_key={quote('snmp')}",
        }

    def generate(self, hosts: list[dict], templates: list[dict], items: list[dict], triggers: list[dict]) -> HealthcheckReport:
        total_hosts = len(hosts)
        enabled_hosts = sum(1 for h in hosts if h.get("status") == "0")
        disabled_hosts = total_hosts - enabled_hosts
        total_templates = len(templates)
        total_items = len(items)
        unsupported_items = [i for i in items if i.get("state") == "1"]
        snmp_items = [i for i in items if int(i.get("type", -1)) in SNMP_TYPES or "snmp" in str(i.get("key_", "")).lower()]
        async_candidates = [
            i for i in snmp_items if "walk[" in str(i.get("key_", "")).lower() or "get[" in str(i.get("key_", "")).lower()
        ]
        triggers_enabled = sum(1 for t in triggers if t.get("status") == "0")

        host_item_counter = Counter()
        host_unsupported_counter = Counter()
        template_item_counter = Counter()

        host_templates = defaultdict(list)
        for host in hosts:
            for template in host.get("parentTemplates", []) or []:
                template_name = template.get("name") or template.get("host") or template.get("templateid")
                host_templates[host["hostid"]].append((template.get("templateid", ""), template_name))

        for item in items:
            hostid = item.get("hostid")
            host_item_counter[hostid] += 1
            if item.get("state") == "1":
                host_unsupported_counter[hostid] += 1
            for templateid, template_name in host_templates.get(hostid, []):
                template_item_counter[(templateid, template_name)] += 1

        host_index = {h["hostid"]: h for h in hosts}
        top_hosts = [
            HostSummary(
                hostid=hostid,
                host=host_index.get(hostid, {}).get("host", hostid),
                item_count=item_count,
                unsupported_count=host_unsupported_counter.get(hostid, 0),
            )
            for hostid, item_count in host_item_counter.most_common(10)
        ]

        top_templates = [
            TemplateSummary(templateid=templateid, name=name, item_count=count)
            for (templateid, name), count in template_item_counter.most_common(10)
        ]

        recommendations: list[Recommendation] = []

        unsupported_ratio = (len(unsupported_items) / total_items * 100) if total_items else 0
        if unsupported_items:
            severity = "high" if unsupported_ratio >= 5 else "medium"
            recommendations.append(
                Recommendation(
                    severity=severity,
                    title="Itens unsupported detectados",
                    detail=f"Foram encontrados {len(unsupported_items)} itens unsupported ({unsupported_ratio:.2f}% do total).",
                    action="Revise credenciais, chaves, OIDs, conectividade e itens órfãos. Unsupported é ruído caro e costuma esconder problema real.",
                )
            )

        if disabled_hosts > 0:
            recommendations.append(
                Recommendation(
                    severity="low",
                    title="Hosts desabilitados no ambiente",
                    detail=f"Há {disabled_hosts} hosts desabilitados. Isso pode indicar inventário antigo ou ambiente sem higiene operacional.",
                    action="Revise hosts legados e remova o que não agrega mais valor. Monitoramento não é museu.",
                )
            )

        if len(async_candidates) > 0:
            recommendations.append(
                Recommendation(
                    severity="medium",
                    title="Candidatos a SNMP assíncrono",
                    detail=f"Foram encontrados {len(async_candidates)} itens com padrão get[OID] ou walk[OID].",
                    action="Avalie tuning de StartSNMPPollers e priorize desenho SNMP assíncrono no Zabbix 7 para reduzir contenção e melhorar escala.",
                )
            )

        if total_hosts and total_items / total_hosts > 300:
            recommendations.append(
                Recommendation(
                    severity="medium",
                    title="Alta densidade de itens por host",
                    detail=f"A média atual é de {total_items / total_hosts:.1f} itens por host.",
                    action="Revise templates muito pesados, LLD excessiva e intervalos agressivos. Host inchado costuma virar boleto de performance.",
                )
            )

        if total_templates == 0:
            recommendations.append(
                Recommendation(
                    severity="high",
                    title="Nenhum template encontrado",
                    detail="O ambiente não retornou templates pela API.",
                    action="Valide permissão do token e integridade do ambiente. Sem template, a conversa com o monitoramento fica bem deprimente.",
                )
            )

        report = HealthcheckReport(
            kpis=EnvironmentKPIs(
                total_hosts=total_hosts,
                enabled_hosts=enabled_hosts,
                disabled_hosts=disabled_hosts,
                total_templates=total_templates,
                total_items=total_items,
                unsupported_items=len(unsupported_items),
                snmp_items=len(snmp_items),
                async_snmp_candidates=len(async_candidates),
                triggers_enabled=triggers_enabled,
            ),
            recommendations=recommendations,
            top_hosts=top_hosts,
            top_templates=top_templates,
            links=self._build_links(),
        )
        return report
