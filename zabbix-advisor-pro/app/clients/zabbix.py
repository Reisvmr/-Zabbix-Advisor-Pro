from __future__ import annotations

import requests
from app.core.config import settings


class ZabbixAPIError(Exception):
    pass


class ZabbixClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api_jsonrpc.php"
        self.token = token
        self.session = requests.Session()

    def call(self, method: str, params: dict | None = None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "auth": self.token,
            "id": 1,
        }
        response = self.session.post(self.api_url, json=payload, timeout=settings.request_timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            err = data["error"]
            raise ZabbixAPIError(f"{err.get('message')}: {err.get('data')}")
        return data["result"]

    def version(self) -> str:
        return self.call("apiinfo.version")

    def hosts(self):
        return self.call(
            "host.get",
            {
                "output": ["hostid", "host", "status", "name"],
                "selectInterfaces": ["type", "ip", "dns", "port", "main"],
                "selectParentTemplates": ["templateid", "name"],
            },
        )

    def templates(self):
        return self.call("template.get", {"output": ["templateid", "host", "name"]})

    def items(self):
        return self.call(
            "item.get",
            {
                "output": [
                    "itemid",
                    "hostid",
                    "name",
                    "key_",
                    "type",
                    "status",
                    "state",
                    "delay",
                    "interfaceid",
                ],
                "selectHosts": ["hostid", "host", "name"],
                "selectValueMap": "extend",
            },
        )

    def triggers(self):
        return self.call("trigger.get", {"output": ["triggerid", "status", "priority"]})
