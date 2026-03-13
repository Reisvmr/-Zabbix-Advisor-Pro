from fastapi import APIRouter, HTTPException

from app.clients.zabbix import ZabbixAPIError
from app.schemas.forms import HealthcheckRequest
from app.services.healthcheck import HealthcheckService

router = APIRouter()
service = HealthcheckService()


@router.post("/healthcheck")
def run_healthcheck(payload: HealthcheckRequest):
    try:
        return service.run(payload)
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha inesperada: {exc}") from exc
