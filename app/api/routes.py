from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.database import save_snapshot
from app.core.zabbix_client import ZabbixAPIError, ZabbixClient
from app.schemas.analysis import AnalyzeRequest
from app.services.export_service import generate_csv, generate_pdf
from app.services.health_service import HealthService

router = APIRouter(prefix="/api/v1", tags=["analysis"])


def _build_client(url: str, token: str, verify_ssl: bool | None = None) -> ZabbixClient:
    s = get_settings()
    ssl = verify_ssl if verify_ssl is not None else s.verify_ssl
    return ZabbixClient(base_url=url, token=token, timeout=s.request_timeout, verify_ssl=ssl)


@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    try:
        client = _build_client(payload.url, payload.token)
        service = HealthService(client)
        result = service.run(frontend_url=payload.frontend_url)
        snapshot_id = save_snapshot(payload.url, result)
        result["snapshot_id"] = snapshot_id
        return result
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}") from exc


@router.post("/debug/proxies")
def debug_proxies(payload: AnalyzeRequest):
    """Retorna dados brutos do proxy.get para diagnóstico de compatibilidade."""
    try:
        client = _build_client(payload.url, payload.token, payload.verify_ssl)
        raw = client.raw_proxy_get()
        normalized = client.get_proxies()
        return {
            "raw_count": len(raw),
            "raw_sample": raw[:3],
            "normalized_count": len(normalized),
            "normalized": normalized,
            "fields_found": list(raw[0].keys()) if raw else [],
        }
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export/csv")
def export_csv(payload: AnalyzeRequest):
    try:
        client = _build_client(payload.url, payload.token)
        result = HealthService(client).run(frontend_url=payload.frontend_url)
        csv_content = generate_csv(result)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=zabbix-advisor-report.csv"},
        )
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export/pdf")
def export_pdf(payload: AnalyzeRequest):
    try:
        client = _build_client(payload.url, payload.token)
        result = HealthService(client).run(frontend_url=payload.frontend_url)
        pdf_bytes = generate_pdf(result, zabbix_url=payload.url)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=zabbix-advisor-report.pdf"},
        )
    except ZabbixAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
