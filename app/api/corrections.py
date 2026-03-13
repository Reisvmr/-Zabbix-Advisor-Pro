from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.zabbix_client import ZabbixAPIError, ZabbixClient
from app.services.correction_service import SUPPORTED_ACTIONS, execute_correction, preview_correction

router = APIRouter(prefix="/api/v1/corrections", tags=["corrections"])


class CorrectionRequest(BaseModel):
    url: str
    token: str
    action: str
    verify_ssl: bool = True


def _make_client(url: str, token: str, verify_ssl: bool = True) -> ZabbixClient:
    settings = get_settings()
    # Usa timeout maior para operações em massa (massupdate pode demorar em ambientes grandes)
    timeout = max(settings.request_timeout, 120)
    return ZabbixClient(base_url=url, token=token, timeout=timeout, verify_ssl=verify_ssl)


@router.get("/actions")
def list_actions():
    return [{"action": k, "label": v} for k, v in SUPPORTED_ACTIONS.items()]


@router.post("/preview")
def preview(payload: CorrectionRequest):
    if payload.action not in SUPPORTED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Ação inválida: {payload.action}")
    try:
        client = _make_client(payload.url, payload.token, payload.verify_ssl)
        return preview_correction(client, payload.action)
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


@router.post("/execute")
def execute(payload: CorrectionRequest):
    if payload.action not in SUPPORTED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Ação inválida: {payload.action}")
    try:
        client = _make_client(payload.url, payload.token, payload.verify_ssl)
        return execute_correction(client, payload.action)
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc
