"""PDF report generation for monthly DNS resolver reports.

This module creates professional PDF reports in both English and Thai,
incorporating ML insights, graphs, and summary tables.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

log = logging.getLogger(__name__)

# ============================================================================
# THAI FONT REGISTRATION FOR PDF
# ============================================================================
THAI_FONT_REGISTERED = False

def _register_thai_fonts():
    """Register Thai fonts with ReportLab using system TTF fonts."""
    global THAI_FONT_REGISTERED
    if THAI_FONT_REGISTERED:
        return
    
    # Use system TLWG Loma TTF fonts (available on Ubuntu)
    font_files = {
        "Loma": "/usr/share/fonts/truetype/tlwg/Loma.ttf",
        "Loma-Bold": "/usr/share/fonts/truetype/tlwg/Loma-Bold.ttf",
        "Loma-Oblique": "/usr/share/fonts/truetype/tlwg/Loma-Oblique.ttf",
        "Loma-BoldOblique": "/usr/share/fonts/truetype/tlwg/Loma-BoldOblique.ttf",
    }
    
    try:
        for font_name, font_path in font_files.items():
            if Path(font_path).exists():
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                log.debug("Registered Thai font: %s from %s", font_name, font_path)
            else:
                log.warning("Thai font file not found: %s", font_path)
        THAI_FONT_REGISTERED = True
        log.info("Thai fonts registered successfully")
    except Exception as e:
        log.warning("Failed to register Thai fonts: %s", e)

# Register fonts at module load
_register_thai_fonts()

# Font names for use in styles
THAI_FONT_NAME = "Loma"
THAI_FONT_BOLD_NAME = "Loma-Bold"
THAI_FONT_OBLIQUE_NAME = "Loma-Oblique"
THAI_FONT_BOLD_OBLIQUE_NAME = "Loma-BoldOblique"

# Page setup
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm

# Colors
PRIMARY_COLOR = colors.HexColor("#2E86AB")
SECONDARY_COLOR = colors.HexColor("#A23B72")
SUCCESS_COLOR = colors.HexColor("#27AE60")
WARNING_COLOR = colors.HexColor("#F39C12")
DANGER_COLOR = colors.HexColor("#E74C3C")
LIGHT_GRAY = colors.HexColor("#ECF0F1")
DARK_GRAY = colors.HexColor("#2C3E50")
WHITE = colors.white
BLACK = colors.black


def _get_styles(lang: str = "en") -> dict[str, ParagraphStyle]:
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()
    
    # Choose font based on language
    if lang == "th" and THAI_FONT_REGISTERED:
        title_font = THAI_FONT_BOLD_NAME
        normal_font = THAI_FONT_NAME
        bold_font = THAI_FONT_BOLD_NAME
        oblique_font = THAI_FONT_OBLIQUE_NAME
        bold_oblique_font = THAI_FONT_BOLD_OBLIQUE_NAME
    else:
        title_font = "Helvetica-Bold"
        normal_font = "Helvetica"
        bold_font = "Helvetica-Bold"
        oblique_font = "Helvetica-Oblique"
        bold_oblique_font = "Helvetica-BoldOblique"

    custom = {
        "title": ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=28,
            textColor=PRIMARY_COLOR,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName=title_font,
        ),
        "subtitle": ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            textColor=SECONDARY_COLOR,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName=normal_font,
        ),
        "heading1": ParagraphStyle(
            "CustomHeading1",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=PRIMARY_COLOR,
            spaceBefore=18,
            spaceAfter=8,
            fontName=bold_font,
            borderWidth=0,
            borderPadding=0,
        ),
        "heading2": ParagraphStyle(
            "CustomHeading2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=SECONDARY_COLOR,
            spaceBefore=12,
            spaceAfter=6,
            fontName=bold_font,
        ),
        "body": ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=DARK_GRAY,
            spaceAfter=6,
            fontName=normal_font,
        ),
        "body_bold": ParagraphStyle(
            "CustomBodyBold",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=DARK_GRAY,
            spaceAfter=6,
            fontName=bold_font,
        ),
        "small": ParagraphStyle(
            "CustomSmall",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#7F8C8D"),
            spaceAfter=4,
            fontName=normal_font,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=WHITE,
            fontName=bold_font,
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=DARK_GRAY,
            fontName=normal_font,
            alignment=TA_CENTER,
        ),
        "table_cell_left": ParagraphStyle(
            "TableCellLeft",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=DARK_GRAY,
            fontName=normal_font,
            alignment=TA_LEFT,
        ),
        "footer": ParagraphStyle(
            "CustomFooter",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#95A5A6"),
            alignment=TA_CENTER,
            fontName=oblique_font,
        ),
    }
    return custom


def _create_header_footer(canvas, doc, title: str, lang: str = "en") -> None:
    """Add header and footer to each page."""
    canvas.saveState()

    # Choose font based on language
    if lang == "th" and THAI_FONT_REGISTERED:
        header_font = THAI_FONT_NAME
        footer_font = THAI_FONT_OBLIQUE_NAME
    else:
        header_font = "Helvetica"
        footer_font = "Helvetica-Oblique"

    # Header line
    canvas.setStrokeColor(PRIMARY_COLOR)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_HEIGHT - MARGIN + 5, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN + 5)

    # Header text
    canvas.setFont(header_font, 8)
    canvas.setFillColor(colors.HexColor("#7F8C8D"))
    if lang == "th":
        canvas.drawString(MARGIN, PAGE_HEIGHT - MARGIN + 8, "รายงานรายเดือน DNS Resolver")
    else:
        canvas.drawString(MARGIN, PAGE_HEIGHT - MARGIN + 8, "chk-a Monthly DNS Resolver Report")
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN + 8, datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # Footer
    canvas.setStrokeColor(colors.HexColor("#BDC3C7"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, MARGIN - 10, PAGE_WIDTH - MARGIN, MARGIN - 10)
    canvas.setFont(footer_font, 7)
    canvas.setFillColor(colors.HexColor("#95A5A6"))
    canvas.drawCentredString(
        PAGE_WIDTH / 2,
        MARGIN - 20,
        f"Page {doc.page} | Generated by chk-a DNS Monitor | Confidential",
    )

    canvas.restoreState()


def _create_cover_page(story: list, ml_insights: dict[str, Any], lang: str = "en") -> None:
    """Create the report cover page."""
    styles = _get_styles(lang)
    
    # Get font names for tables
    if lang == "th" and THAI_FONT_REGISTERED:
        table_header_font = THAI_FONT_BOLD_NAME
        table_cell_font = THAI_FONT_NAME
    else:
        table_header_font = "Helvetica-Bold"
        table_cell_font = "Helvetica"

    story.append(Spacer(1, 4 * cm))

    # Main title
    if lang == "th":
        story.append(Paragraph("รายงานรายเดือน DNS Resolver", styles["title"]))
        story.append(Paragraph("chk-a DNS Monitor", styles["subtitle"]))
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(
                f"ช่วงเวลา: {ml_insights.get('lookback_days', 30)} วันที่ผ่านมา", styles["body"]
            )
        )
        story.append(
            Paragraph(f"สร้างเมื่อ: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["body"])
        )
    else:
        story.append(Paragraph("Monthly DNS Resolver Report", styles["title"]))
        story.append(Paragraph("chk-a DNS Monitor", styles["subtitle"]))
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(f"Period: Last {ml_insights.get('lookback_days', 30)} days", styles["body"])
        )
        story.append(
            Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["body"])
        )

    story.append(Spacer(1, 2 * cm))

    # Summary box
    summary = ml_insights.get("summary", {})
    if lang == "th":
        summary_data = [
            ["เมตริก", "ค่า"],
            ["จำนวน Resolver ทั้งหมด", str(summary.get("total_resolvers", 0))],
            ["จำนวน Query ทั้งหมด", f"{summary.get('total_queries', 0):,}"],
            ["ความพร้อมใช้งานโดยรวม", f"{summary.get('overall_availability_pct', 0):.2f}%"],
            ["Resolver ที่ดีที่สุด", summary.get("best_resolver", "N/A")],
            ["Resolver ที่ต้องปรับปรุง", summary.get("worst_resolver", "N/A")],
            ["Resolver 異常 (Anomaly)", str(len(summary.get("anomalous_resolvers", [])))],
        ]
    else:
        summary_data = [
            ["Metric", "Value"],
            ["Total Resolvers", str(summary.get("total_resolvers", 0))],
            ["Total Queries", f"{summary.get('total_queries', 0):,}"],
            ["Overall Availability", f"{summary.get('overall_availability_pct', 0):.2f}%"],
            ["Best Resolver", summary.get("best_resolver", "N/A")],
            ["Worst Resolver", summary.get("worst_resolver", "N/A")],
            ["Anomalous Resolvers", str(len(summary.get("anomalous_resolvers", [])))],
        ]

    table = Table(summary_data, colWidths=[8 * cm, 6 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), table_header_font),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GRAY),
                ("TEXTCOLOR", (0, 1), (-1, -1), DARK_GRAY),
                ("FONTNAME", (0, 1), (-1, -1), table_cell_font),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    story.append(PageBreak())


def _create_availability_section(
    story: list,
    availability: dict[str, dict[str, Any]],
    graph_paths: list[Path],
    lang: str = "en",
) -> None:
    """Create availability analysis section with graphs."""
    styles = _get_styles(lang)

    if lang == "th":
        story.append(Paragraph("1. การวิเคราะห์ความพร้อมใช้งาน (Availability)", styles["heading1"]))
        story.append(
            Paragraph(
                "ส่วนนี้แสดงสัดส่วนของการตอบสนองที่สำเร็จของแต่ละ Resolver ตลอดช่วงเวลาที่กำหนด",
                styles["body"],
            )
        )
    else:
        story.append(Paragraph("1. Availability Analysis", styles["heading1"]))
        story.append(
            Paragraph(
                "This section shows the proportion of successful responses for each resolver "
                "over the reporting period.",
                styles["body"],
            )
        )

    # Availability table
    if lang == "th":
        headers = [
            "Resolver",
            "Query ทั้งหมด",
            "สำเร็จ",
            "ล้มเหลว",
            "ความพร้อมใช้งาน (%)",
            "Latency เฉลี่ย (ms)",
            "Median (ms)",
            "P95 (ms)",
            "P99 (ms)",
        ]
    else:
        headers = [
            "Resolver",
            "Total Queries",
            "Success",
            "Failed",
            "Availability (%)",
            "Avg Latency (ms)",
            "Median (ms)",
            "P95 (ms)",
            "P99 (ms)",
        ]

    table_data = [headers]
    for resolver, data in sorted(
        availability.items(), key=lambda x: x[1]["availability_pct"], reverse=True
    ):
        row = [
            resolver,
            str(data.get("total_queries", 0)),
            str(data.get("successful_queries", 0)),
            str(data.get("failed_queries", 0)),
            f"{data.get('availability_pct', 0):.2f}",
            f"{data.get('avg_latency_ms', 0):.1f}" if "avg_latency_ms" in data else "N/A",
            f"{data.get('median_latency_ms', 0):.1f}" if "median_latency_ms" in data else "N/A",
            f"{data.get('p95_latency_ms', 0):.1f}" if "p95_latency_ms" in data else "N/A",
            f"{data.get('p99_latency_ms', 0):.1f}" if "p99_latency_ms" in data else "N/A",
        ]
        table_data.append(row)

    col_widths = [3.2 * cm, 2 * cm, 1.5 * cm, 1.5 * cm, 2.5 * cm, 2.2 * cm, 2 * cm, 2 * cm, 2 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Get font names for tables
    if lang == "th" and THAI_FONT_REGISTERED:
        table_header_font = THAI_FONT_BOLD_NAME
        table_cell_font = THAI_FONT_NAME
    else:
        table_header_font = "Helvetica-Bold"
        table_cell_font = "Helvetica"
    
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), table_header_font),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), table_cell_font),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    # Add availability graphs
    for graph_path in graph_paths:
        if "availability-bar" in graph_path.name or "availability-heatmap" in graph_path.name:
            try:
                img = Image(str(graph_path), width=16 * cm, height=10 * cm)
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                log.warning("Failed to embed graph %s: %s", graph_path, e)

    story.append(PageBreak())


def _create_integrity_section(
    story: list,
    integrity: dict[str, dict[str, Any]],
    graph_paths: list[Path],
    lang: str = "en",
) -> None:
    """Create integrity analysis section with graphs."""
    styles = _get_styles(lang)

    if lang == "th":
        story.append(
            Paragraph("2. การวิเคราะห์ความสมบูรณ์ (Integrity) - ML-based", styles["heading1"])
        )
        story.append(
            Paragraph(
                "ส่วนนี้ใช้ Machine Learning (Isolation Forest) "
                "เพื่อตรวจจับความผิดปกติของคำตอบจาก Resolver แต่ละตัว "
                "โดยพิจารณาจากอัตราสำเร็จ Latency ความหลากหลายของ IP "
                "และความเสถียรของคำตอบ",
                styles["body"],
            )
        )
    else:
        story.append(Paragraph("2. Integrity Analysis - ML-based", styles["heading1"]))
        story.append(
            Paragraph(
                "This section uses Machine Learning (Isolation Forest) "
                "to detect anomalies in resolver responses, "
                "considering success rate, latency, IP diversity, "
                "and answer stability.",
                styles["body"],
            )
        )

    # Integrity table
    if lang == "th":
        headers = [
            "Resolver",
            "Integrity Score",
            "Anomaly Score",
            "สถานะ",
            "Top Contributing Features",
        ]
    else:
        headers = [
            "Resolver",
            "Integrity Score",
            "Anomaly Score",
            "Status",
            "Top Contributing Features",
        ]

    table_data = [headers]
    for resolver, data in sorted(
        integrity.items(), key=lambda x: x[1]["integrity_score"], reverse=True
    ):
        is_anomaly = data.get("is_anomaly", False)
        status = "⚠ Anomaly" if is_anomaly else "✓ Normal"
        top_features = data.get("top_contributing_features", [])
        features_str = ", ".join([f"{f['feature']} (z={f['z_score']})" for f in top_features[:2]])

        row = [
            resolver,
            f"{data.get('integrity_score', 0):.1f}",
            f"{data.get('anomaly_score', 0):.4f}",
            status,
            features_str,
        ]
        table_data.append(row)

    col_widths = [3.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 6 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Get font names for tables
    if lang == "th" and THAI_FONT_REGISTERED:
        table_header_font = THAI_FONT_BOLD_NAME
        table_cell_font = THAI_FONT_NAME
    else:
        table_header_font = "Helvetica-Bold"
        table_cell_font = "Helvetica"
    
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), table_header_font),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), table_cell_font),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                # Highlight anomaly rows
                *[
                    ("TEXTCOLOR", (0, i), (-1, i), DANGER_COLOR)
                    for i, (_, data) in enumerate(
                        sorted(
                            integrity.items(), key=lambda x: x[1]["integrity_score"], reverse=True
                        ),
                        1,
                    )
                    if data.get("is_anomaly", False)
                ],
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    # Add integrity graphs
    for graph_path in graph_paths:
        if (
            "integrity-score" in graph_path.name
            or "ip-stability" in graph_path.name
            or "latency-boxplot" in graph_path.name
        ):
            try:
                img = Image(str(graph_path), width=16 * cm, height=10 * cm)
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                log.warning("Failed to embed graph %s: %s", graph_path, e)

    story.append(PageBreak())


def _create_path_availability_section(
    story: list,
    path_availability: dict[str, dict[str, Any]],
    graph_paths: list[Path],
    lang: str = "en",
) -> None:
    """Create path availability section with ML-based health scores."""
    styles = _get_styles(lang)

    if lang == "th":
        story.append(
            Paragraph(
                "3. การวิเคราะห์ความพร้อมใช้งานของเส้นทางเครือข่าย (Path Availability) - ML-based",
                styles["heading1"],
            )
        )
        story.append(
            Paragraph(
                "ส่วนนี้วิเคราะห์ความพร้อมใช้งานของเส้นทางเครือข่ายจาก Host ไปยัง "
                "Resolver แต่ละตัว โดยใช้ข้อมูล MTR (My Traceroute) และ Machine Learning "
                "(Isolation Forest) เพื่อคำนวณคะแนนสุขภาพเส้นทาง "
                "(Path Health Score 0-100) และระบุจุดคอขวด (Bottleneck) "
                "ที่มี Packet Loss สูงสุด",
                styles["body"],
            )
        )
    else:
        story.append(
            Paragraph(
                "3. Network Path Availability Analysis - ML-based",
                styles["heading1"],
            )
        )
        story.append(
            Paragraph(
                "This section analyzes network path availability from the host to each resolver "
                "using MTR (My Traceroute) data and Machine Learning (Isolation Forest) "
                "to compute Path Health Score (0-100) "
                "and identify bottleneck hops with highest packet loss.",
                styles["body"],
            )
        )

    if not path_availability:
        if lang == "th":
            story.append(Paragraph("ไม่มีข้อมูล MTR สำหรับการวิเคราะห์", styles["body"]))
        else:
            story.append(Paragraph("No MTR data available for path analysis.", styles["body"]))
        story.append(PageBreak())
        return

    # Path availability table
    if lang == "th":
        headers = [
            "Resolver",
            "Path Availability (%)",
            "Health Score",
            "Total Hops",
            "Healthy Hops",
            "Degraded Hops",
            "Critical Hops",
            "Avg Latency (ms)",
            "Bottleneck Hop",
        ]
    else:
        headers = [
            "Resolver",
            "Path Availability (%)",
            "Health Score",
            "Total Hops",
            "Healthy Hops",
            "Degraded Hops",
            "Critical Hops",
            "Avg Latency (ms)",
            "Bottleneck Hop",
        ]

    table_data = [headers]
    for resolver, data in sorted(
        path_availability.items(), key=lambda x: x[1]["path_availability_pct"], reverse=True
    ):
        bn = data.get("bottleneck_hop")
        bottleneck_str = f"Hop {bn['hop_num']}: {bn['loss_pct']:.1f}% loss" if bn else "N/A"

        row = [
            resolver,
            f"{data.get('path_availability_pct', 0):.1f}",
            f"{data.get('path_health_score', 0):.0f}",
            str(data.get("total_hops", 0)),
            str(data.get("healthy_hops", 0)),
            str(data.get("degraded_hops", 0)),
            str(data.get("critical_hops", 0)),
            f"{data.get('avg_latency_ms', 0):.1f}",
            bottleneck_str,
        ]
        table_data.append(row)

    col_widths = [
        2.5 * cm,
        2.5 * cm,
        2 * cm,
        1.5 * cm,
        1.5 * cm,
        1.5 * cm,
        1.5 * cm,
        2 * cm,
        4 * cm,
    ]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Get font names for tables
    if lang == "th" and THAI_FONT_REGISTERED:
        table_header_font = THAI_FONT_BOLD_NAME
        table_cell_font = THAI_FONT_NAME
    else:
        table_header_font = "Helvetica-Bold"
        table_cell_font = "Helvetica"
    
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8E44AD")),  # Purple for path
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), table_header_font),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("FONTNAME", (0, 1), (-1, -1), table_cell_font),
                ("FONTSIZE", (0, 1), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                # Highlight critical path rows
                *[
                    ("TEXTCOLOR", (0, i), (-1, i), DANGER_COLOR)
                    for i, (_, data) in enumerate(
                        sorted(
                            path_availability.items(),
                            key=lambda x: x[1]["path_availability_pct"],
                            reverse=True,
                        ),
                        1,
                    )
                    if data.get("path_availability_pct", 0) < 70
                ],
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    # Add path availability graphs
    for graph_path in graph_paths:
        if "path-availability" in graph_path.name or "mtr-path" in graph_path.name:
            try:
                img = Image(str(graph_path), width=16 * cm, height=10 * cm)
                story.append(img)
                story.append(Spacer(1, 8))
            except Exception as e:
                log.warning("Failed to embed graph %s: %s", graph_path, e)

    story.append(PageBreak())


def _create_ml_insights_section(
    story: list,
    ml_insights: dict[str, Any],
    lang: str = "en",
) -> None:
    """Create ML insights and recommendations section."""
    styles = _get_styles(lang)
    summary = ml_insights.get("summary", {})

    if lang == "th":
        story.append(
            Paragraph("3. ข้อมูลเชิงลึกจาก Machine Learning และคำแนะนำ", styles["heading1"])
        )
    else:
        story.append(Paragraph("3. ML Insights & Recommendations", styles["heading1"]))

    # Anomalous resolvers
    anomalous = summary.get("anomalous_resolvers", [])
    if anomalous:
        if lang == "th":
            story.append(
                Paragraph("⚠ Resolver ที่ตรวจพบความผิดปกติ (Anomalies)", styles["heading2"])
            )
            story.append(
                Paragraph(
                    "Resolver ต่อไปนี้แสดงพฤติกรรมที่แตกต่างจากปกติ อาจบ่งชี้ปัญหาเครือข่าย "
                    "การตั้งค่า หรือการโจมตี:",
                    styles["body"],
                )
            )
            for r in anomalous:
                story.append(Paragraph(f"• <b>{r}</b>", styles["body"]))
        else:
            story.append(Paragraph("⚠ Anomalous Resolvers Detected", styles["heading2"]))
            story.append(
                Paragraph(
                    "The following resolvers exhibit anomalous behavior, which may indicate "
                    "network issues, misconfiguration, or potential attacks:",
                    styles["body"],
                )
            )
            for r in anomalous:
                story.append(Paragraph(f"• <b>{r}</b>", styles["body"]))
    else:
        if lang == "th":
            story.append(Paragraph("✓ ไม่พบ Resolver ที่มีความผิดปกติ", styles["heading2"]))
            story.append(Paragraph("Resolver ทั้งหมดทำงานในขอบเขตที่คาดหวัง", styles["body"]))
        else:
            story.append(Paragraph("✓ No Anomalous Resolvers Detected", styles["heading2"]))
            story.append(
                Paragraph("All resolvers are operating within expected parameters.", styles["body"])
            )

    story.append(Spacer(1, 12))

    # Recommendations
    if lang == "th":
        story.append(Paragraph("คำแนะนำ", styles["heading2"]))
        story.append(
            Paragraph("1. ตรวจสอบ Resolver ที่มี Availability ต่ำกว่า 95%", styles["body"])
        )
        story.append(
            Paragraph(
                "2. ตรวจสอบ Resolver ที่ถูกจัดเป็น Anomaly เพื่อหาสาเหตุรากฐาน", styles["body"]
            )
        )
        story.append(Paragraph("3. พิจารณาเพิ่ม Resolver สำรองสำหรับ FQDN สำคัญ", styles["body"]))
        story.append(
            Paragraph(
                "4. ตรวจสอบ Latency ที่สูงผิดปกติ อาจบ่งชี้ปัญหา Routing หรือ Load", styles["body"]
            )
        )
    else:
        story.append(Paragraph("Recommendations", styles["heading2"]))
        story.append(
            Paragraph("1. Investigate resolvers with availability below 95%", styles["body"])
        )
        story.append(
            Paragraph("2. Root-cause analyze resolvers flagged as anomalies", styles["body"])
        )
        story.append(
            Paragraph("3. Consider adding backup resolvers for critical FQDNs", styles["body"])
        )
        story.append(
            Paragraph(
                "4. Review unusually high latency - may indicate routing or load issues",
                styles["body"],
            )
        )

    story.append(PageBreak())


def _create_methodology_section(story: list, lang: str = "en") -> None:
    """Create methodology appendix."""
    styles = _get_styles(lang)

    if lang == "th":
        story.append(Paragraph("ภาคผนวก: วิธีการคำนวณและอัลกอริทึม", styles["heading1"]))
        story.append(Paragraph("Availability (ความพร้อมใช้งาน)", styles["heading2"]))
        story.append(
            Paragraph(
                "คำนวณจากอัตราส่วนของ Query ที่สำเร็จต่อ Query ทั้งหมดของแต่ละ Resolver "
                "ในช่วงเวลาย้อนหลัง (lookback window) ที่กำหนด",
                styles["body"],
            )
        )
        story.append(Paragraph("Integrity (ความสมบูรณ์) - ML-based", styles["heading2"]))
        story.append(
            Paragraph(
                "ใช้ Isolation Forest (Unsupervised Learning) บน Feature Vector ที่ประกอบด้วย: "
                "Success Rate, Average Latency, Latency Std Dev, Unique IP Count, "
                "IP Stability, Error Rate, NXDOMAIN Rate. คะแนน 0-100 คะแนนสูง = ปกติ/เสถียร",
                styles["body"],
            )
        )
        story.append(Paragraph("Latency Statistics", styles["heading2"]))
        story.append(
            Paragraph(
                "คำนวณจาก Query ที่สำเร็จเท่านั้น รวมถึง Mean, Median, P95, P99, Min, Max",
                styles["body"],
            )
        )
    else:
        story.append(Paragraph("Appendix: Methodology & Algorithms", styles["heading1"]))
        story.append(Paragraph("Availability", styles["heading2"]))
        story.append(
            Paragraph(
                "Calculated as the ratio of successful queries to total queries per resolver "
                "over the configured lookback window.",
                styles["body"],
            )
        )
        story.append(Paragraph("Integrity - ML-based", styles["heading2"]))
        story.append(
            Paragraph(
                "Uses Isolation Forest (unsupervised learning) on a feature vector "
                "comprising: Success Rate, Average Latency, Latency Std Dev, "
                "Unique IP Count, IP Stability, Error Rate, NXDOMAIN Rate. "
                "Score 0-100, higher = more consistent/normal.",
                styles["body"],
            )
        )
        story.append(Paragraph("Latency Statistics", styles["heading2"]))
        story.append(
            Paragraph(
                "Computed from successful queries only. Includes Mean, Median, P95, P99, Min, Max.",
                styles["body"],
            )
        )
        story.append(Paragraph("Path Availability - ML-based", styles["heading2"]))
        story.append(
            Paragraph(
                "Analyzes MTR (My Traceroute) hop data from host to each resolver. "
                "Path Availability = % of hops with <10% packet loss. "
                "ML: Isolation Forest on daily path availability rates. "
                "Path Health Score 0-100, higher = more reliable path. "
                "Bottleneck = hop with highest loss%.",
                styles["body"],
            )
        )


def generate_pdf_report(
    ml_insights: dict[str, Any],
    graph_paths: list[Path],
    output_path: Path,
    lang: str = "en",
    hostname: str = "",
) -> None:
    """Generate a complete PDF report (English or Thai)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story = []

    # Cover page
    _create_cover_page(story, ml_insights, lang)

    # Availability section
    availability = ml_insights.get("availability", {})
    _create_availability_section(story, availability, graph_paths, lang)

    # Integrity section
    integrity = ml_insights.get("integrity", {})
    _create_integrity_section(story, integrity, graph_paths, lang)

    # Path Availability section
    path_availability = ml_insights.get("path_availability", {})
    _create_path_availability_section(story, path_availability, graph_paths, lang)

    # ML Insights section
    _create_ml_insights_section(story, ml_insights, lang)

    # Methodology
    _create_methodology_section(story, lang)

    # Build PDF with header/footer
    def _header_footer(canvas, doc):
        _create_header_footer(canvas, doc, "Monthly DNS Report", lang)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    log.info("Generated PDF report: %s", output_path)


def generate_pdf_report_en(
    ml_insights: dict[str, Any],
    graph_paths: list[Path],
    output_path: Path,
    hostname: str = "",
) -> None:
    """Generate English PDF report."""
    generate_pdf_report(ml_insights, graph_paths, output_path, lang="en", hostname=hostname)


def generate_pdf_report_th(
    ml_insights: dict[str, Any],
    graph_paths: list[Path],
    output_path: Path,
    hostname: str = "",
) -> None:
    """Generate Thai PDF report."""
    generate_pdf_report(ml_insights, graph_paths, output_path, lang="th", hostname=hostname)
