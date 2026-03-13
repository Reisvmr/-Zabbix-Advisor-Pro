from pydantic import BaseModel


class Recommendation(BaseModel):
    severity: str
    title: str
    detail: str
    action: str


class HostSummary(BaseModel):
    hostid: str
    host: str
    item_count: int
    unsupported_count: int


class TemplateSummary(BaseModel):
    templateid: str
    name: str
    item_count: int


class EnvironmentKPIs(BaseModel):
    total_hosts: int
    enabled_hosts: int
    disabled_hosts: int
    total_templates: int
    total_items: int
    unsupported_items: int
    snmp_items: int
    async_snmp_candidates: int
    triggers_enabled: int


class HealthcheckReport(BaseModel):
    kpis: EnvironmentKPIs
    recommendations: list[Recommendation]
    top_hosts: list[HostSummary]
    top_templates: list[TemplateSummary]
    links: dict[str, str]
