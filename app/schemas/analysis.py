from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="URL base do Zabbix")
    token: str = Field(..., description="Token da API do Zabbix")
    frontend_url: str | None = Field(default=None, description="URL do frontend do Zabbix")
    verify_ssl: bool = Field(default=True, description="Verificar certificado SSL")


class Recommendation(BaseModel):
    severity: str
    title: str
    detail: str
    action: str | None = None
    link: str | None = None


class RankedEntry(BaseModel):
    name: str
    value: int
    link: str | None = None


class AnalysisResponse(BaseModel):
    totals: dict
    top_hosts: list[RankedEntry]
    top_templates: list[RankedEntry]
    recommendations: list[Recommendation]
