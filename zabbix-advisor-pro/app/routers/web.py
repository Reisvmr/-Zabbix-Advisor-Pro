from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.clients.zabbix import ZabbixAPIError
from app.schemas.forms import HealthcheckRequest
from app.services.healthcheck import HealthcheckService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
service = HealthcheckService()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "error": None, "report": None})


@router.post("/", response_class=HTMLResponse)
def submit(
    request: Request,
    zabbix_url: str = Form(...),
    api_token: str = Form(...),
    frontend_url: str = Form(default=""),
):
    try:
        payload = HealthcheckRequest(
            zabbix_url=zabbix_url,
            api_token=api_token,
            frontend_url=frontend_url or zabbix_url,
        )
        result = service.run(payload)
        return templates.TemplateResponse(
            "report.html",
            {"request": request, "result": result, "error": None},
        )
    except ZabbixAPIError as exc:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": str(exc), "report": None},
            status_code=400,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Falha inesperada: {exc}", "report": None},
            status_code=500,
        )
