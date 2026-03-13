from app.services.analyzer import HealthcheckAnalyzer


def test_generate_report_basic():
    analyzer = HealthcheckAnalyzer(frontend_url="https://zbx.local")
    hosts = [
        {"hostid": "101", "host": "srv-01", "status": "0", "parentTemplates": [{"templateid": "201", "name": "Linux by Zabbix agent"}]},
        {"hostid": "102", "host": "srv-02", "status": "1", "parentTemplates": []},
    ]
    templates = [{"templateid": "201", "name": "Linux by Zabbix agent"}]
    items = [
        {"hostid": "101", "state": "0", "type": "7", "key_": "agent.ping"},
        {"hostid": "101", "state": "1", "type": "4", "key_": "walk[1.3.6.1.2]"},
        {"hostid": "102", "state": "0", "type": "4", "key_": "get[1.3.6.1.2]"},
    ]
    triggers = [{"status": "0"}, {"status": "1"}]

    report = analyzer.generate(hosts, templates, items, triggers)

    assert report.kpis.total_hosts == 2
    assert report.kpis.unsupported_items == 1
    assert report.kpis.async_snmp_candidates == 2
    assert len(report.recommendations) >= 1
