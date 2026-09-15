"""PDF report generation for completed detection tasks."""

from __future__ import annotations

import html
import os
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from ..rules.contracts import RuleSet
from ..services.rule_summary import (
    clauses_by_rule_id,
    rule_basis_text,
    summarize_rule_source,
)
from ..services.task_store import TaskRecord


REPORT_DIR = Path(os.getenv("REPORT_DIR", "reports"))
REPORT_FONT_NAME = "PaperCheckerChinese"
REPORT_FONT_PATH = Path(os.getenv("REPORT_FONT_PATH", r"C:\Windows\Fonts\simhei.ttf"))


def report_id_for(task_id: str) -> str:
    return f"R{task_id}"


def report_path(report_id: str) -> Path:
    return REPORT_DIR / f"{report_id}.pdf"


def ensure_report_font() -> str:
    if REPORT_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        if not REPORT_FONT_PATH.exists():
            raise RuntimeError("中文 PDF 字体不存在")
        pdfmetrics.registerFont(TTFont(REPORT_FONT_NAME, str(REPORT_FONT_PATH)))
    return REPORT_FONT_NAME


ERROR_TYPE_LABELS = {
    "font_error": "字体",
    "size_error": "字号",
    "bold_error": "加粗",
    "alignment_error": "对齐方式",
    "line_spacing_error": "行距",
    "paragraph_indent_error": "段落缩进",
    "paragraph_spacing_error": "段间距",
    "page_margin_error": "页边距",
    "heading_numbering_error": "章节编号",
    "toc_consistency_error": "目录一致性",
    "required_sections_error": "必备结构",
    "keyword_format_error": "关键词格式",
    "caption_format_error": "图/表题格式",
    "header_text_error": "页眉文本",
    "reference_baseline_error": "参考文献序号",
    "table_figure_format_error": "图/表格式",
    "caption_position_error": "题注位置",
    "page_number_error": "页码",
}


def _text(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def _error_type_label(error_type: str) -> str:
    return ERROR_TYPE_LABELS.get(error_type, error_type)


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName=font_name, fontSize=18, leading=24, alignment=TA_CENTER, spaceAfter=8 * mm),
        "heading": ParagraphStyle("ReportHeading", parent=base["Heading2"], fontName=font_name, fontSize=12, leading=18, spaceBefore=4 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontName=font_name, fontSize=9.5, leading=15),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontName=font_name, fontSize=8, leading=12, textColor=colors.HexColor("#555555")),
        "cell": ParagraphStyle("ReportCell", parent=base["BodyText"], fontName=font_name, fontSize=7.5, leading=10.5),
    }


def _table_style(font_name: str) -> TableStyle:
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F2EC")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C9C0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ])


def _clause_reference(rule_id: str | None, mapping: dict[str, dict]) -> str:
    """把一条错误回指到规范条款；找不到时留空而不是编造。"""
    if rule_id is None:
        return "—"
    clause = mapping.get(rule_id)
    return clause["title"] if clause else "—"


def _basis_story(rules: RuleSet, rule_file: str, styles: dict[str, ParagraphStyle], font_name: str) -> list:
    """渲染「检测依据」：规范来源信息 + 条款明细表 + 人工核对提示。"""
    summary = summarize_rule_source(rules)
    story: list = []
    title_line = summary["title"]
    if summary["scope"]:
        title_line = f"{title_line}（适用范围：{summary['scope']}）"
    story.append(Paragraph(f"规范名称：{_text(title_line)}", styles["body"]))
    if summary["organization"]:
        story.append(Paragraph(f"发布单位：{_text(summary['organization'])}", styles["body"]))
    if summary["document"]:
        story.append(Paragraph(f"依据文档：{_text(summary['document'])}", styles["body"]))
    story.append(Paragraph(f"规则文件：{_text(rule_file)}（规则版本 {_text(rules.schema_version)}）", styles["body"]))
    story.append(Paragraph(f"依据说明：{_text(rule_basis_text(rules))}", styles["body"]))

    clauses = summary["clauses"]
    if clauses:
        story.append(Spacer(1, 2 * mm))
        rows = [[Paragraph(label, styles["cell"]) for label in ("规范条款", "出处章节", "规范摘要", "校验方式")]]
        for clause in clauses:
            method = "人工核对" if not clause["automated"] else f"自动（{clause['rule_count']} 项）"
            rows.append([
                Paragraph(_text(clause["title"]), styles["cell"]),
                Paragraph(_text(clause["chapter"]), styles["cell"]),
                Paragraph(_text(clause["text"]), styles["cell"]),
                Paragraph(method, styles["cell"]),
            ])
        table = Table(rows, colWidths=[28 * mm, 36 * mm, 82 * mm, 28 * mm], repeatRows=1)
        table.setStyle(_table_style(font_name))
        story.append(table)

    if summary["notes"]:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("以下内容规范有要求但机器不做判定，请教师人工核对：", styles["small"]))
        for note in summary["notes"]:
            story.append(Paragraph("· " + _text(note), styles["small"]))
    return story


def build_report_story(
    task: TaskRecord,
    *,
    rules: RuleSet,
    rule_file: str,
    styles: dict[str, ParagraphStyle],
    font_name: str,
) -> list:
    """组装报告的版面内容，抽出来便于直接测试报告写了什么。"""
    story: list = [
        Paragraph("论文格式检测报告", styles["title"]),
        Paragraph(f"文件名称：{_text(task.filename)}", styles["body"]),
        Paragraph(f"任务编号：{_text(task.task_id)}", styles["body"]),
        Paragraph(f"检测状态：{_text(task.status)}", styles["body"]),
        Spacer(1, 4 * mm),
        Paragraph("检测依据", styles["heading"]),
    ]
    story.extend(_basis_story(rules, rule_file, styles, font_name))
    story.extend([
        Paragraph("检测结果", styles["heading"]),
        Paragraph(f"共发现 {len(task.errors)} 个格式问题。" if task.errors else "未发现格式问题，检测通过。", styles["body"]),
    ])
    if task.errors:
        clause_mapping = clauses_by_rule_id(rules)
        rows = [[Paragraph(label, styles["cell"]) for label in ("类型", "位置", "错误文本", "当前格式", "规范要求", "规范条款")]]
        for error in task.errors:
            rows.append([
                Paragraph(_text(_error_type_label(error.type)), styles["cell"]),
                Paragraph(_text(error.location), styles["cell"]),
                Paragraph(_text(error.content or "（无文本）"), styles["cell"]),
                Paragraph(_text(error.current), styles["cell"]),
                Paragraph(_text(error.expected), styles["cell"]),
                Paragraph(_text(_clause_reference(error.rule_id, clause_mapping)), styles["cell"]),
            ])
        table = Table(rows, colWidths=[22 * mm, 26 * mm, 48 * mm, 22 * mm, 22 * mm, 34 * mm], repeatRows=1)
        table.setStyle(_table_style(font_name))
        first_basis = next((error.basis for error in task.errors if error.basis), "")
        footnote = "「规范条款」列给出每条问题在依据文档中的出处；其余条款见「检测依据」章节。"
        if first_basis:
            footnote += f"规则级依据示例：{_text(first_basis)}。"
        story.extend([Spacer(1, 3 * mm), table, Paragraph(footnote, styles["small"])])
    return story


def build_report(task: TaskRecord, *, rules: RuleSet, rule_file: str) -> Path:
    font_name = ensure_report_font()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = report_path(report_id_for(task.task_id))
    styles = _styles(font_name)
    story = build_report_story(task, rules=rules, rule_file=rule_file, styles=styles, font_name=font_name)
    document = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    document.build(story)
    return target
