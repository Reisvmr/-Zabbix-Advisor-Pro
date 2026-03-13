import pytest
from app.analyzers.environment_analyzer import EnvironmentAnalyzer


HOSTS = [
    {"hostid": "1", "name": "srv-01", "status": "0", "available": "1"},
    {"hostid": "2", "name": "srv-02", "status": "1", "available": "0"},  # disabled
    {"hostid": "3", "name": "srv-03", "status": "0", "available": "2"},  # unavailable
]
TEMPLATES = [
    {"templateid": "10", "name": "Linux", "hosts": [{"hostid": "1"}], "items": [{"itemid": "100"}, {"itemid": "101"}]},
    {"templateid": "11", "name": "Network", "hosts": [], "items": []},
]
ITEMS = [
    {"itemid": "100", "hostid": "1", "state": "0", "status": "0", "key_": "system.cpu.load", "type": "0", "hosts": [{"name": "srv-01"}]},
    {"itemid": "101", "hostid": "1", "state": "1", "status": "0", "key_": "snmp.get[1.3.6.1]", "type": "20", "hosts": [{"name": "srv-01"}]},
    {"itemid": "102", "hostid": "2", "state": "0", "status": "1", "key_": "system.cpu.load", "type": "0", "hosts": [{"name": "srv-02"}]},
]
TRIGGERS = [
    {"triggerid": "1", "description": "CPU high", "status": "0", "value": "1", "priority": "3", "error": ""},
    {"triggerid": "2", "description": "Disk low", "status": "1", "value": "0", "priority": "2", "error": ""},
    {"triggerid": "3", "description": "Bad expr", "status": "0", "value": "0", "priority": "1", "error": "invalid expression"},
]


def make_analyzer(**kwargs):
    defaults = dict(hosts=HOSTS, templates=TEMPLATES, items=ITEMS, triggers=TRIGGERS)
    defaults.update(kwargs)
    return EnvironmentAnalyzer(**defaults)


def test_totals_basic():
    result = make_analyzer().analyze()
    assert result["totals"]["hosts"] == 3
    assert result["totals"]["templates"] == 2
    assert result["totals"]["items"] == 3


def test_unsupported_items():
    result = make_analyzer().analyze()
    assert result["totals"]["unsupported_items"] == 1


def test_disabled_items():
    result = make_analyzer().analyze()
    assert result["totals"]["disabled_items"] == 1


def test_disabled_hosts():
    result = make_analyzer().analyze()
    assert result["totals"]["disabled_hosts"] == 1


def test_unavailable_hosts():
    result = make_analyzer().analyze()
    assert result["totals"]["unavailable_hosts"] == 1


def test_trigger_analysis():
    result = make_analyzer().analyze()
    td = result["trigger_data"]
    assert td["total_triggers"] == 3
    assert td["disabled_triggers"] == 1
    assert td["problem_triggers"] == 1
    assert td["error_triggers"] == 1


def test_snmp_detection():
    result = make_analyzer().analyze()
    assert result["totals"]["snmp_candidates"] >= 1


def test_recommendations_not_empty():
    result = make_analyzer().analyze()
    assert len(result["recommendations"]) >= 1


def test_high_severity_for_unsupported():
    result = make_analyzer().analyze()
    severities = [r["severity"] for r in result["recommendations"]]
    assert "high" in severities


def test_top_hosts():
    result = make_analyzer().analyze()
    assert len(result["top_hosts"]) >= 1


def test_top_templates():
    result = make_analyzer().analyze()
    assert len(result["top_templates"]) >= 1


def test_chart_data_present():
    result = make_analyzer().analyze()
    cd = result["chart_data"]
    assert "kpi_donut" in cd
    assert "top_hosts_bar" in cd
    assert "item_types_pie" in cd


def test_frontend_links():
    result = make_analyzer(frontend_url="https://zbx.local").analyze()
    for h in result["top_hosts"]:
        if h["link"]:
            assert "zbx.local" in h["link"]


def test_no_triggers_no_crash():
    result = make_analyzer(triggers=[]).analyze()
    assert result["trigger_data"]["total_triggers"] == 0


def test_empty_environment():
    result = EnvironmentAnalyzer(hosts=[], templates=[], items=[]).analyze()
    assert result["totals"]["hosts"] == 0
    assert result["totals"]["items"] == 0
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["severity"] == "info"
