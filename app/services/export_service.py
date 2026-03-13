from __future__ import annotations

import csv
import io
from typing import Any


def generate_csv(data: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== KPIs ==="])
    writer.writerow(["Métrica", "Valor"])
    for k, v in data.get("totals", {}).items():
        writer.writerow([k.replace("_", " ").title(), v])

    writer.writerow([])
    writer.writerow(["=== Top Hosts (por itens) ==="])
    writer.writerow(["Host", "Itens"])
    for h in data.get("top_hosts", []):
        writer.writerow([h["name"], h["value"]])

    writer.writerow([])
    writer.writerow(["=== Top Templates ==="])
    writer.writerow(["Template", "Score"])
    for t in data.get("top_templates", []):
        writer.writerow([t["name"], t["value"]])

    writer.writerow([])
    writer.writerow(["=== Recomendações ==="])
    writer.writerow(["Severidade", "Título", "Detalhe", "Ação"])
    for r in data.get("recommendations", []):
        writer.writerow([r.get("severity", ""), r.get("title", ""), r.get("detail", ""), r.get("action", "")])

    return output.getvalue()


def generate_pdf(data: dict[str, Any], zabbix_url: str = "", created_at: str = "") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#1a1a2e"))
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666666"))
    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#1a1a2e"), spaceBefore=14)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=14)

    SEV_COLORS = {
        "high": colors.HexColor("#ff6b6b"),
        "medium": colors.HexColor("#f1c40f"),
        "low": colors.HexColor("#6ea8fe"),
        "info": colors.HexColor("#2ecc71"),
    }

    story.append(Paragraph("Zabbix Advisor Pro", title_style))
    story.append(Paragraph(f"Relatório de healthcheck — {zabbix_url}", sub_style))
    if created_at:
        story.append(Paragraph(f"Gerado em: {created_at}", sub_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.3 * cm))

    # KPIs table
    story.append(Paragraph("KPIs do Ambiente", h2_style))
    totals = data.get("totals", {})
    kpi_data = [["Métrica", "Valor"]] + [[k.replace("_", " ").title(), str(v)] for k, v in totals.items()]
    kpi_table = Table(kpi_data, colWidths=[10 * cm, 5 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9f9f9"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # Top Hosts
    story.append(Paragraph("Top Hosts por Volume de Itens", h2_style))
    top_hosts = data.get("top_hosts", [])
    if top_hosts:
        h_data = [["Host", "Itens"]] + [[h["name"], str(h["value"])] for h in top_hosts[:10]]
        h_table = Table(h_data, colWidths=[12 * cm, 3 * cm])
        h_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3561")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9f9f9"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(h_table)
    story.append(Spacer(1, 0.4 * cm))

    # Recommendations
    story.append(Paragraph("Recomendações", h2_style))
    for rec in data.get("recommendations", []):
        sev = rec.get("severity", "info")
        sev_color = SEV_COLORS.get(sev, colors.grey)
        badge_style = ParagraphStyle("badge", parent=body_style, textColor=sev_color, fontName="Helvetica-Bold")
        story.append(Paragraph(f"[{sev.upper()}] {rec.get('title', '')}", badge_style))
        story.append(Paragraph(rec.get("detail", ""), body_style))
        if rec.get("action"):
            story.append(Paragraph(f"<b>Ação:</b> {rec['action']}", body_style))
        story.append(Spacer(1, 0.25 * cm))

    doc.build(story)
    return buf.getvalue()
