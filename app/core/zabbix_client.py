from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("zabbix_advisor")


class ZabbixAPIError(Exception):
    pass


class ZabbixClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api_jsonrpc.php"
        self.token = token.strip()
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "auth": self.token,
            "id": 1,
        }
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={"Content-Type": "application/json-rpc"},
            )
            response.raise_for_status()
        except requests.exceptions.SSLError as exc:
            raise ZabbixAPIError("Erro SSL: verifique o certificado ou desative VERIFY_SSL") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ZabbixAPIError(f"Não foi possível conectar: {self.base_url}") from exc
        except requests.exceptions.Timeout as exc:
            raise ZabbixAPIError(f"Timeout ao conectar (>{self.timeout}s)") from exc

        data = response.json()
        if "error" in data:
            msg = data["error"].get("data") or data["error"].get("message") or "Erro na API do Zabbix"
            raise ZabbixAPIError(msg)
        return data.get("result", [])

    # ── Read methods ──────────────────────────────────────────────────────────

    def get_hosts(self) -> list[dict[str, Any]]:
        return self.call(
            "host.get",
            {
                "output": ["hostid", "host", "name", "status", "available", "error"],
                "selectItems": ["itemid"],
                "selectParentTemplates": ["templateid", "name"],
                "selectInterfaces": ["type", "ip", "dns"],
            },
        )

    def get_templates(self) -> list[dict[str, Any]]:
        return self.call(
            "template.get",
            {
                "output": ["templateid", "host", "name"],
                "selectHosts": ["hostid"],
                "selectItems": ["itemid"],
            },
        )

    def get_items(self) -> list[dict[str, Any]]:
        return self.call(
            "item.get",
            {
                "output": [
                    "itemid", "hostid", "name", "key_", "type",
                    "value_type", "state", "status", "delay", "error",
                ],
                "selectHosts": ["hostid", "name", "host"],
            },
        )

    def get_triggers(self) -> list[dict[str, Any]]:
        return self.call(
            "trigger.get",
            {
                "output": ["triggerid", "description", "status", "value", "priority", "error"],
                "selectHosts": ["hostid", "name"],
            },
        )

    def get_proxies(self) -> list[dict[str, Any]]:
        # Usa "extend" para não causar erro com campos inexistentes na versão
        # Zabbix 6.x: campo 'host' e 'status'
        # Zabbix 7.x: campo 'name' e 'operating_mode'
        try:
            result = self.call(
                "proxy.get",
                {"output": "extend", "selectHosts": ["hostid"]},
            )
        except ZabbixAPIError:
            # selectHosts pode não funcionar em algumas versões — tenta sem
            try:
                result = self.call("proxy.get", {"output": "extend"})
            except ZabbixAPIError as exc:
                logger.warning("proxy.get falhou: %s", exc)
                return []

        # Normaliza nome para garantir campo 'host' sempre preenchido
        for p in result:
            name = p.get("host") or p.get("name") or f"proxy-{p.get('proxyid', '?')}"
            p["host"] = name
            p["name"] = name

        logger.info("proxy.get retornou %d proxies: %s", len(result), [p["host"] for p in result])
        return result

    def raw_proxy_get(self) -> list[dict[str, Any]]:
        """Retorna dados brutos do proxy.get para diagnóstico."""
        return self.call("proxy.get", {"output": "extend"})

    def get_internal_metrics(self) -> list[dict[str, Any]]:
        try:
            return self.call(
                "item.get",
                {
                    "output": ["itemid", "name", "key_", "lastvalue", "lastclock"],
                    "search": {"key_": "zabbix["},
                },
            )
        except ZabbixAPIError:
            return []

    # ── Write / correction methods ────────────────────────────────────────────

    def get_disabled_item_ids(self) -> list[str]:
        items = self.call("item.get", {"output": ["itemid"], "filter": {"status": "1"}})
        return [i["itemid"] for i in items]

    def get_unsupported_item_ids(self) -> list[str]:
        items = self.call("item.get", {"output": ["itemid"], "filter": {"state": "1"}})
        return [i["itemid"] for i in items]

    def get_disabled_host_ids(self) -> list[str]:
        hosts = self.call("host.get", {"output": ["hostid"], "filter": {"status": "1"}})
        return [h["hostid"] for h in hosts]

    def delete_items(self, item_ids: list[str]) -> dict:
        if not item_ids:
            return {"deleted": 0}
        result = self.call("item.delete", item_ids)
        logger.info("Deleted %d items", len(item_ids))
        return result

    def disable_items(self, item_ids: list[str]) -> dict:
        if not item_ids:
            return {"updated": 0}
        # item.update aceita array — uma única chamada para todos os itens
        self.call("item.update", [{"itemid": iid, "status": "1"} for iid in item_ids])
        logger.info("Disabled %d items in one call", len(item_ids))
        return {"updated": len(item_ids)}

    def delete_hosts(self, host_ids: list[str]) -> dict:
        if not host_ids:
            return {"deleted": 0}
        result = self.call("host.delete", host_ids)
        logger.info("Deleted %d hosts", len(host_ids))
        return result

    def enable_hosts(self, host_ids: list[str]) -> dict:
        if not host_ids:
            return {"updated": 0}
        # host.update aceita array — uma única chamada para todos os hosts
        self.call("host.update", [{"hostid": hid, "status": "0"} for hid in host_ids])
        logger.info("Enabled %d hosts in one call", len(host_ids))
        return {"updated": len(host_ids)}
