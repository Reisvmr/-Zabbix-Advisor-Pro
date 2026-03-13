from app.clients.zabbix import ZabbixClient
from app.schemas.forms import HealthcheckRequest
from app.services.analyzer import HealthcheckAnalyzer


class HealthcheckService:
    def run(self, payload: HealthcheckRequest):
        client = ZabbixClient(payload.zabbix_url, payload.api_token)
        hosts = client.hosts()
        templates = client.templates()
        items = client.items()
        triggers = client.triggers()

        analyzer = HealthcheckAnalyzer(frontend_url=payload.frontend_url or payload.zabbix_url)
        report = analyzer.generate(hosts=hosts, templates=templates, items=items, triggers=triggers)
        return {
            "version": client.version(),
            "report": report,
        }
