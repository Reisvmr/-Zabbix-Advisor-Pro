from __future__ import annotations

from app.analyzers.environment_analyzer import EnvironmentAnalyzer
from app.core.zabbix_client import ZabbixClient


class HealthService:
    def __init__(self, client: ZabbixClient):
        self.client = client

    def run(self, frontend_url: str | None = None) -> dict:
        hosts = self.client.get_hosts()
        templates = self.client.get_templates()
        items = self.client.get_items()
        triggers = self.client.get_triggers()
        proxies = self.client.get_proxies()
        analyzer = EnvironmentAnalyzer(
            hosts=hosts,
            templates=templates,
            items=items,
            triggers=triggers,
            proxies=proxies,
            frontend_url=frontend_url,
        )
        return analyzer.analyze()
