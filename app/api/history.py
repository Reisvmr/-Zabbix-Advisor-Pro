from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.database import get_snapshot, get_trend_data, list_snapshots

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
def list_history(limit: int = 30):
    return list_snapshots(limit=limit)


@router.get("/{snapshot_id}")
def get_history_item(snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    return snap


@router.get("/{snapshot_id}/trend")
def get_trend(snapshot_id: int):
    snap = get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")
    return get_trend_data(snap["zabbix_url"])
