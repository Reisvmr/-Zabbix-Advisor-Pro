from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.corrections import router as corrections_router
from app.api.history import router as history_router
from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.database import get_snapshot, get_trend_data, init_db, list_snapshots, save_snapshot
from app.core.logger import setup_logging
from app.core.zabbix_client import ZabbixAPIError, ZabbixClient
from app.services.export_service import generate_csv, generate_pdf
from app.services.health_service import HealthService

settings = get_settings()
setup_logging(debug=settings.app_debug)
logger = logging.getLogger("zabbix_advisor")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(api_router)
app.include_router(corrections_router)
app.include_router(history_router)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup():
    init_db()
    logger.info("Zabbix Advisor Pro started — env=%s", settings.app_env)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    recent = list_snapshots(limit=5)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name, "recent_snapshots": recent},
    )


@app.post("/report", response_class=HTMLResponse)
@limiter.limit("10/minute")
def report(
    request: Request,
    url: str = Form(...),
    token: str = Form(...),
    frontend_url: str = Form(""),
    verify_ssl: str = Form("true"),
):
    ssl_ok = verify_ssl.lower() not in ("false", "0", "off")
    try:
        client = ZabbixClient(
            base_url=url,
            token=token,
            timeout=settings.request_timeout,
            verify_ssl=ssl_ok,
        )
        service = HealthService(client)
        report_data = service.run(frontend_url=frontend_url or None)
        snapshot_id = save_snapshot(url, report_data)

        trend_data = get_trend_data(url)

        return templates.TemplateResponse(
            "report.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "data": report_data,
                "frontend_url": frontend_url,
                "snapshot_id": snapshot_id,
                "zabbix_url": url,
                "zabbix_token": token,
                "verify_ssl": ssl_ok,
                "trend_data_json": json.dumps(trend_data),
                "chart_data_json": json.dumps(report_data.get("chart_data", {})),
            },
        )
    except ZabbixAPIError as exc:
        logger.warning("ZabbixAPIError: %s", exc)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "error": str(exc),
                "recent_snapshots": list_snapshots(limit=5),
            },
            status_code=400,
        )
    except Exception as exc:
        logger.exception("Unexpected error during report generation")
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.") from exc


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    snapshots = list_snapshots(limit=50)
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "app_name": settings.app_name, "snapshots": snapshots},
    )


@app.get("/history/{snapshot_id}", response_class=HTMLResponse)
def history_detail(request: Request, snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    trend_data = get_trend_data(snap["zabbix_url"])
    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "data": snap,
            "frontend_url": "",
            "snapshot_id": snap["id"],
            "zabbix_url": snap["zabbix_url"],
            "zabbix_token": "",
            "trend_data_json": json.dumps(trend_data),
            "chart_data_json": json.dumps(snap.get("chart_data", {})),
            "readonly": True,
        },
    )


@app.get("/history/{snapshot_id}/export/csv")
def export_csv_snapshot(snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    csv_content = generate_csv(snap)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=zabbix-advisor-{snapshot_id}.csv"},
    )


@app.get("/history/{snapshot_id}/export/pdf")
def export_pdf_snapshot(snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    pdf_bytes = generate_pdf(snap, zabbix_url=snap["zabbix_url"], created_at=snap["created_at"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=zabbix-advisor-{snapshot_id}.pdf"},
    )
