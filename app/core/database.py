from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/advisor.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      TEXT    NOT NULL,
            zabbix_url      TEXT    NOT NULL,
            totals          TEXT    NOT NULL,
            top_hosts       TEXT    NOT NULL,
            top_templates   TEXT    NOT NULL,
            recommendations TEXT    NOT NULL,
            chart_data      TEXT    NOT NULL DEFAULT '{}',
            poller_tuning   TEXT    NOT NULL DEFAULT '[]',
            proxy_tuning    TEXT    NOT NULL DEFAULT '[]',
            item_types      TEXT    NOT NULL DEFAULT '{}'
        )
        """
    )
    # Migração não-destrutiva: adiciona colunas novas em bancos existentes
    for col, default in [("poller_tuning", "[]"), ("proxy_tuning", "[]"), ("item_types", "{}")]:
        try:
            conn.execute(f"ALTER TABLE snapshots ADD COLUMN {col} TEXT NOT NULL DEFAULT '{default}'")
        except Exception:
            pass
    conn.commit()
    conn.close()


def save_snapshot(zabbix_url: str, data: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO snapshots
            (created_at, zabbix_url, totals, top_hosts, top_templates,
             recommendations, chart_data, poller_tuning, proxy_tuning, item_types)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(),
            zabbix_url,
            json.dumps(data.get("totals", {})),
            json.dumps(data.get("top_hosts", [])),
            json.dumps(data.get("top_templates", [])),
            json.dumps(data.get("recommendations", [])),
            json.dumps(data.get("chart_data", {})),
            json.dumps(data.get("poller_tuning", [])),
            json.dumps(data.get("proxy_tuning", [])),
            json.dumps(data.get("item_types", {})),
        ),
    )
    conn.commit()
    snapshot_id = cur.lastrowid
    conn.close()
    return snapshot_id


def list_snapshots(limit: int = 30) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, created_at, zabbix_url, totals FROM snapshots ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "zabbix_url": r["zabbix_url"],
            "totals": json.loads(r["totals"]),
        }
        for r in rows
    ]


def get_snapshot(snapshot_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "zabbix_url": row["zabbix_url"],
        "totals": json.loads(row["totals"]),
        "top_hosts": json.loads(row["top_hosts"]),
        "top_templates": json.loads(row["top_templates"]),
        "recommendations": json.loads(row["recommendations"]),
        "chart_data": json.loads(row["chart_data"]),
        "poller_tuning": json.loads(row["poller_tuning"] if row["poller_tuning"] else "[]"),
        "proxy_tuning": json.loads(row["proxy_tuning"] if row["proxy_tuning"] else "[]"),
        "item_types": json.loads(row["item_types"] if row["item_types"] else "{}"),
    }


def get_trend_data(zabbix_url: str, limit: int = 10) -> list[dict]:
    """Return last N snapshots totals for trend charts."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT created_at, totals FROM snapshots
           WHERE zabbix_url = ? ORDER BY created_at DESC LIMIT ?""",
        (zabbix_url, limit),
    ).fetchall()
    conn.close()
    return [
        {"created_at": r["created_at"], "totals": json.loads(r["totals"])}
        for r in reversed(rows)
    ]
