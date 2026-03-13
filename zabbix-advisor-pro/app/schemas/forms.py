from pydantic import BaseModel, Field


class HealthcheckRequest(BaseModel):
    zabbix_url: str = Field(..., description="URL base do Zabbix sem /api_jsonrpc.php")
    api_token: str = Field(..., description="Token da API")
    frontend_url: str | None = Field(default=None, description="URL do frontend para links diretos")
