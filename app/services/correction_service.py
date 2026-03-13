from __future__ import annotations

import logging
from typing import Any

from app.core.zabbix_client import ZabbixClient

logger = logging.getLogger("zabbix_advisor")

SUPPORTED_ACTIONS = {
    "disable_unsupported": "Desabilitar itens não suportados",
    "delete_disabled_items": "Remover itens desabilitados",
    "delete_disabled_hosts": "Remover hosts desabilitados",
    "enable_disabled_hosts": "Habilitar hosts desabilitados",
}


def preview_correction(client: ZabbixClient, action: str) -> dict[str, Any]:
    """Return what would be affected without executing."""
    if action == "disable_unsupported":
        ids = client.get_unsupported_item_ids()
        return {"action": action, "label": SUPPORTED_ACTIONS[action], "count": len(ids), "ids": ids[:20]}

    if action == "delete_disabled_items":
        ids = client.get_disabled_item_ids()
        return {"action": action, "label": SUPPORTED_ACTIONS[action], "count": len(ids), "ids": ids[:20]}

    if action in ("delete_disabled_hosts", "enable_disabled_hosts"):
        ids = client.get_disabled_host_ids()
        return {"action": action, "label": SUPPORTED_ACTIONS[action], "count": len(ids), "ids": ids[:20]}

    raise ValueError(f"Ação desconhecida: {action}")


def execute_correction(client: ZabbixClient, action: str) -> dict[str, Any]:
    """Execute the correction and return result."""
    if action == "disable_unsupported":
        ids = client.get_unsupported_item_ids()
        if not ids:
            return {"action": action, "affected": 0, "message": "Nenhum item não suportado encontrado."}
        result = client.disable_items(ids)
        return {"action": action, "affected": len(ids), "message": f"{len(ids)} itens desabilitados com sucesso."}

    if action == "delete_disabled_items":
        ids = client.get_disabled_item_ids()
        if not ids:
            return {"action": action, "affected": 0, "message": "Nenhum item desabilitado encontrado."}
        client.delete_items(ids)
        return {"action": action, "affected": len(ids), "message": f"{len(ids)} itens removidos com sucesso."}

    if action == "delete_disabled_hosts":
        ids = client.get_disabled_host_ids()
        if not ids:
            return {"action": action, "affected": 0, "message": "Nenhum host desabilitado encontrado."}
        client.delete_hosts(ids)
        return {"action": action, "affected": len(ids), "message": f"{len(ids)} hosts removidos com sucesso."}

    if action == "enable_disabled_hosts":
        ids = client.get_disabled_host_ids()
        if not ids:
            return {"action": action, "affected": 0, "message": "Nenhum host desabilitado encontrado."}
        client.enable_hosts(ids)
        return {"action": action, "affected": len(ids), "message": f"{len(ids)} hosts habilitados com sucesso."}

    raise ValueError(f"Ação desconhecida: {action}")
