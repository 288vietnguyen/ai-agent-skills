#!/usr/bin/env python3
"""
Generate TFE Test Plan and Test Report PDFs following template layouts using ReportLab.

Usage:
    python3 generate_report_pdf.py --input report_data.json \
        --output-plan TFE_Test_Plan.pdf \
        --output-report TFE_Test_Report.pdf

Exit codes:
    0 - PDFs generated successfully
    1 - Failed to generate PDFs
"""

import argparse
import json
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Page dimensions
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_LEFT = 2.5 * cm
MARGIN_RIGHT = 2.5 * cm
MARGIN_TOP = 2.5 * cm
MARGIN_BOTTOM = 2.5 * cm
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def get_styles():
    """Define all paragraph styles matching the templates."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        alignment=TA_LEFT,
        spaceAfter=20,
    ))

    styles.add(ParagraphStyle(
        name="SectionTitle",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=22,
        alignment=TA_LEFT,
        spaceBefore=16,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="SubSectionTitle",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="SubSubSectionTitle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=10,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="BodyText2",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name="TableCellLeft",
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name="BulletText",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=20,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="SubBulletText",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=40,
        spaceAfter=2,
    ))

    return styles


# ---------------------------------------------------------------------------
# Common table styles
# ---------------------------------------------------------------------------

COMMON_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
])

INFO_TABLE_STYLE = TableStyle([
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
])


# ---------------------------------------------------------------------------
# Shared: cover page (used by both Plan and Report)
# ---------------------------------------------------------------------------

def build_cover_page(data: dict, styles, title: str) -> list:
    """Build cover page with title, description, ITSM ID, sign-off table."""
    elements = []

    elements.append(Paragraph(title, styles["ReportTitle"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(
        f"Request Description: {data['action_change']}",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 4))

    elements.append(Paragraph(
        f"ID: ITSM - {data['itsm_request_id']}",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 20))

    sign_data = [
        ["STT", "Unit", "Sign"],
        ["1", "DevSecOps", ""],
        ["2", "IT PM / DL", ""],
        ["3", "SOS", ""],
        ["4", "IT QE", ""],
    ]
    sign_table = Table(sign_data, colWidths=[60, 200, 200])
    sign_table.setStyle(COMMON_TABLE_STYLE)
    elements.append(sign_table)

    return elements


# ---------------------------------------------------------------------------
# Helper: build a document
# ---------------------------------------------------------------------------

def _build_pdf(output_path: str, elements: list):
    """Create and build a PDF document from elements."""
    frame = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        CONTENT_WIDTH, PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        id="normal",
    )
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        pageTemplates=[PageTemplate(id="main", frames=[frame])],
    )
    doc.build(elements)


# ===========================================================================
# TEST PLAN PDF
# ===========================================================================

def _collect_all_resource_changes(data: dict) -> list:
    """Collect all resource changes from rollout runs across all workspaces."""
    all_changes = []
    for ws in data["workspaces"]:
        for rc in ws.get("rollout", {}).get("resource_changes", []):
            all_changes.append(rc)
    return all_changes


def build_plan_scope(data: dict, styles) -> list:
    """Build section 1: Scope of Testing."""
    elements = []

    elements.append(Paragraph("1. Scope of Testing", styles["SectionTitle"]))
    elements.append(Paragraph(
        "- Detail scope of change request (Create new, Update, Delete AWS resource).",
        styles["BodyText2"],
    ))

    all_changes = _collect_all_resource_changes(data)
    for rc in all_changes:
        objective = rc.get("test_objective", rc.get("aws_service", ""))
        elements.append(Paragraph(f"o  {objective}", styles["SubBulletText"]))

    if not all_changes:
        elements.append(Paragraph("o  (No resource changes detected)", styles["SubBulletText"]))

    elements.append(Spacer(1, 8))
    return elements


def build_plan_preparation(data: dict, styles) -> list:
    """Build section 2: Test Preparation."""
    elements = []

    elements.append(Paragraph("2. Test Preparation", styles["SectionTitle"]))

    # Collect workspace names
    ws_names = ", ".join(ws["name"] for ws in data["workspaces"])

    prep_data = [
        ["AWS Account", data["aws_account_id"]],
        ["Environment", data["environment"]],
        ["TFE Workspace", ws_names],
    ]
    prep_table = Table(prep_data, colWidths=[CONTENT_WIDTH * 0.3, CONTENT_WIDTH * 0.7])
    prep_table.setStyle(INFO_TABLE_STYLE)
    elements.append(prep_table)
    elements.append(Spacer(1, 8))

    return elements


def build_plan_test_approach(data: dict, styles) -> list:
    """Build section 3: Test Approach."""
    elements = []

    elements.append(Paragraph("3. Test Approach", styles["SectionTitle"]))

    all_changes = _collect_all_resource_changes(data)

    # Header row
    table_data = [
        [
            Paragraph("<b>STT</b>", styles["TableCellLeft"]),
            Paragraph("<b>Test Objective</b>", styles["TableCellLeft"]),
            Paragraph("<b>Objective Attributes</b>", styles["TableCellLeft"]),
            Paragraph("<b>Actual Result</b>", styles["TableCellLeft"]),
        ],
    ]

    if all_changes:
        for i, rc in enumerate(all_changes, 1):
            objective = rc.get("test_objective", rc.get("aws_service", ""))
            attrs = rc.get("attributes", [])
            attrs_str = "\n".join(f"- {a}" for a in attrs[:8])  # limit to 8 attrs
            if len(attrs) > 8:
                attrs_str += "\n- ..."
            result = rc.get("action_summary", "N/A")

            table_data.append([
                f"UC{i}",
                Paragraph(f"- {objective}", styles["TableCellLeft"]),
                Paragraph(attrs_str.replace("\n", "<br/>"), styles["TableCellLeft"]),
                Paragraph(result, styles["TableCellLeft"]),
            ])
    else:
        table_data.append(["UC1", "", "", ""])

    table = Table(table_data, colWidths=[
        CONTENT_WIDTH * 0.08,
        CONTENT_WIDTH * 0.27,
        CONTENT_WIDTH * 0.35,
        CONTENT_WIDTH * 0.30,
    ])

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    table.setStyle(TableStyle(style_commands))
    elements.append(table)
    elements.append(Spacer(1, 8))

    return elements


def build_plan_timeline(data: dict, styles) -> list:
    """Build section 4: Timeline."""
    elements = []

    elements.append(Paragraph("4. Timeline", styles["SectionTitle"]))

    time_data = [
        ["Type of Testing", "From Date", "To Date"],
        ["System Testing (ST)", data["day_start"], data["day_end"]],
    ]
    time_table = Table(time_data, colWidths=[CONTENT_WIDTH * 0.4, CONTENT_WIDTH * 0.3, CONTENT_WIDTH * 0.3])
    time_table.setStyle(COMMON_TABLE_STYLE)
    elements.append(time_table)

    return elements


def generate_test_plan_pdf(data: dict, output_path: str):
    """Generate the TFE Test Plan PDF."""
    styles = get_styles()
    elements = []

    # Page 1: Cover page
    elements.extend(build_cover_page(data, styles, "TFE Test Plan"))

    # Page 2: Scope, Preparation, Test Approach, Timeline
    elements.extend(build_plan_scope(data, styles))
    elements.extend(build_plan_preparation(data, styles))
    elements.extend(build_plan_test_approach(data, styles))
    elements.extend(build_plan_timeline(data, styles))

    _build_pdf(output_path, elements)


# ===========================================================================
# TEST REPORT PDF
# ===========================================================================

def build_report_summary(data: dict, styles) -> list:
    """Build Summary of Testing Process for Test Report."""
    elements = []

    elements.append(Paragraph("1. Summary of Testing Process", styles["SectionTitle"]))

    # 1.1 Testing execution Time
    elements.append(Paragraph("1.1. Testing execution Time", styles["SubSectionTitle"]))
    time_data = [
        ["Type of Testing", "From Date", "To Date"],
        ["System Testing (ST)", data["day_start"], data["day_end"]],
    ]
    time_table = Table(time_data, colWidths=[CONTENT_WIDTH * 0.4, CONTENT_WIDTH * 0.3, CONTENT_WIDTH * 0.3])
    time_table.setStyle(COMMON_TABLE_STYLE)
    elements.append(time_table)
    elements.append(Spacer(1, 10))

    # 1.2 Test Participants
    elements.append(Paragraph("1.2. Test Participants", styles["SubSectionTitle"]))
    participant_data = [
        ["Full Name", "User ID", "Division", "Type of User", "Participate"],
        ["", "", "DSO", "System User", "OAT"],
    ]
    participant_table = Table(participant_data, colWidths=[
        CONTENT_WIDTH * 0.2, CONTENT_WIDTH * 0.15, CONTENT_WIDTH * 0.2,
        CONTENT_WIDTH * 0.2, CONTENT_WIDTH * 0.25,
    ])
    participant_table.setStyle(COMMON_TABLE_STYLE)
    elements.append(participant_table)
    elements.append(Spacer(1, 10))

    # 1.3 Environment and Testing Tool
    elements.append(Paragraph("1.3. Environment and Testing Tool", styles["SubSectionTitle"]))
    env_data = [
        ["AWS Account", f"Name: {data['aws_account_name']}\nID: {data['aws_account_id']}"],
        ["Detail Workload", data["detail_workload"]],
    ]
    env_table = Table(env_data, colWidths=[CONTENT_WIDTH * 0.3, CONTENT_WIDTH * 0.7])
    env_table.setStyle(INFO_TABLE_STYLE)
    elements.append(env_table)
    elements.append(Spacer(1, 10))

    # 1.4 Purpose and scope of testing
    elements.append(Paragraph("1.4. Purpose and scope of testing", styles["SubSectionTitle"]))
    elements.append(Paragraph(
        "Purpose: Testing deploy infrastructure by Terraform",
        styles["BodyText2"],
    ))

    return elements


def build_workspace_summary_table(data: dict, styles) -> list:
    """Build the TFE Workspace result summary table for section 2.2."""
    workspaces = data["workspaces"]

    table_data = [
        [Paragraph("<b>TFE Workspace result</b>", styles["TableCellLeft"]), ""],
    ]

    for i, ws in enumerate(workspaces, 1):
        rollout = ws.get("rollout", {})
        table_data.append([
            f"TFE run deploy workspace{f' {i}' if len(workspaces) > 1 else ''}",
            f"{ws['name']}\nTFE run : {rollout.get('run_url', 'N/A')}",
        ])

    table_data.append([
        Paragraph("<b>Verify resources created</b>", styles["TableCellLeft"]),
        "",
    ])

    seen_services = set()
    for ws in workspaces:
        for rc in ws.get("rollout", {}).get("resource_changes", []):
            service = rc["aws_service"]
            if service not in seen_services:
                seen_services.add(service)
                table_data.append([service, rc["action_summary"]])

    if not seen_services:
        table_data.append(["No resource changes", "N/A"])

    table = Table(table_data, colWidths=[CONTENT_WIDTH * 0.4, CONTENT_WIDTH * 0.6])

    style_commands = [
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
    ]

    verify_row = 1 + len(workspaces)
    style_commands.append(("SPAN", (0, verify_row), (1, verify_row)))
    style_commands.append(("BACKGROUND", (0, verify_row), (-1, verify_row), colors.Color(0.9, 0.9, 0.9)))

    table.setStyle(TableStyle(style_commands))
    return [table]


def build_workspace_detail_table(ws: dict, ws_index: int, run_type: str, styles) -> list:
    """Build a workspace detail table for rollout or rollback."""
    elements = []
    run_data = ws.get(run_type, {})
    run_url = run_data.get("run_url", "N/A")
    resource_changes = run_data.get("resource_changes", [])

    label = "rollout" if run_type == "rollout" else "rollback"

    table_data = [
        [Paragraph(f"<b>{ws_index}. {ws['name']}</b>", styles["TableCellLeft"]), ""],
        [f"TFE run {label}: {run_url}", ""],
        [Paragraph("<b>Overview</b>", styles["TableCellLeft"]),
         Paragraph("<b>Resource change</b>", styles["TableCellLeft"])],
    ]

    if resource_changes:
        for rc in resource_changes:
            table_data.append([rc["aws_service"], rc["action_summary"]])
    else:
        table_data.append(["No resource changes", "N/A"])

    table = Table(table_data, colWidths=[CONTENT_WIDTH * 0.35, CONTENT_WIDTH * 0.65])

    style_commands = [
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.95, 0.95, 0.95)),
        ("SPAN", (0, 1), (1, 1)),
        ("BACKGROUND", (0, 2), (-1, 2), colors.Color(0.9, 0.9, 0.9)),
    ]

    table.setStyle(TableStyle(style_commands))
    elements.append(table)
    return elements


def build_test_result_pages(data: dict, styles) -> list:
    """Build Test Result section for Test Report."""
    elements = []
    workspaces = data["workspaces"]

    elements.append(Paragraph("2. Test Result", styles["SectionTitle"]))

    # 2.1 General Test result
    elements.append(Paragraph("2.1. General Test result", styles["SubSectionTitle"]))
    result_text = "<b>Accepted</b>" if data["test_result"] == "Accepted" else "<b>Not Accepted</b>"
    elements.append(Paragraph(
        f"&bull; {data['environment']} report: {result_text}",
        styles["BulletText"],
    ))
    elements.append(Spacer(1, 8))

    # 2.2 Summary table
    elements.append(Paragraph("2.2. Summary table of test results", styles["SubSectionTitle"]))
    elements.append(Paragraph(
        f"- {data['environment'].capitalize()} Report result",
        styles["BodyText2"],
    ))
    elements.append(Spacer(1, 4))
    elements.extend(build_workspace_summary_table(data, styles))
    elements.append(Spacer(1, 12))

    # 2.3 Infrastructure Testing
    elements.append(Paragraph("2.3. Infrastructure Testing", styles["SubSectionTitle"]))

    # A. TFE Rollout
    elements.append(Paragraph("A. TFE Rollout", styles["SubSubSectionTitle"]))
    for i, ws in enumerate(workspaces, 1):
        elements.extend(build_workspace_detail_table(ws, i, "rollout", styles))
        elements.append(Spacer(1, 8))

    # B. TFE Rollback
    elements.append(Paragraph("B. TFE Rollback", styles["SubSubSectionTitle"]))
    for i, ws in enumerate(workspaces, 1):
        elements.extend(build_workspace_detail_table(ws, i, "rollback", styles))
        elements.append(Spacer(1, 8))

    return elements


def generate_test_report_pdf(data: dict, output_path: str):
    """Generate the TFE Test Report PDF."""
    styles = get_styles()
    elements = []

    # Page 1: Cover page
    elements.extend(build_cover_page(data, styles, "TFE Test Report"))

    # Page 2: Summary of Testing Process
    elements.extend(build_report_summary(data, styles))

    # Pages 3+: Test Result
    elements.extend(build_test_result_pages(data, styles))

    _build_pdf(output_path, elements)


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate TFE Test Plan and Test Report PDFs")
    parser.add_argument("--input", required=True, help="Input JSON file from collect_report_data.py")
    parser.add_argument("--output-plan", default="TFE_Test_Plan.pdf", help="Output Test Plan PDF path")
    parser.add_argument("--output-report", default="TFE_Test_Report.pdf", help="Output Test Report PDF path")
    args = parser.parse_args()

    try:
        with open(args.input, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    try:
        generate_test_plan_pdf(data, args.output_plan)
        print(f"SUCCESS: Test Plan PDF generated at {args.output_plan}")

        generate_test_report_pdf(data, args.output_report)
        print(f"SUCCESS: Test Report PDF generated at {args.output_report}")
    except Exception as e:
        print(f"ERROR: Failed to generate PDFs: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
