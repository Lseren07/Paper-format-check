"""PDF report generation for completed detection tasks."""

from __future__ import annotations

import html
import os
import re
from collections import OrderedDict
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

from ..rules.contracts import RuleSet
from ..services.location import format_location
from ..services.rule_summary import (
    clauses_by_rule_id,
    summarize_rule_source,
)
from ..services.task_store import TaskRecord


REPORT_DIR = Path(os.getenv("REPORT_DIR", "reports"))
REPORT_FONT_NAME = "PaperCheckerChinese"
REPORT_FONT_PATH = Path(os.getenv("REPORT_FONT_PATH", r"C:\Windows\Fonts\simhei.ttf"))
ERROR_EXCERPT_LENGTH = 30

INK = colors.HexColor("#1F3A2E")
MUTED = colors.HexColor("#5B6B63")
ACCENT = colors.HexColor("#2F6B52")
HEADER_BG = colors.HexColor("#2F6B52")
ROW_BG = colors.HexColor("#F3F8F5")
RULE_COLOR = colors.HexColor("#C9D6CF")


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
    "header_footer_format_error": "页眉页脚格式",
    "page_number_segments_error": "页码分段",
    "page_header_pattern_error": "页眉内容",
    "reference_baseline_error": "参考文献序号",
    "table_figure_format_error": "图/表格式",
    "caption_position_error": "题注位置",
    "page_number_error": "页码",
    "abstract_length_error": "摘要字数",
    "abstract_consistency_error": "摘要中英文配对",
    "page_break_after_heading_error": "章节分页",
    "formula_format_error": "公式格式",
}


STATUS_LABELS = {
    "uploaded": "已上传",
    "detecting": "检测中",
    "completed": "已完成",
    "failed": "检测失败",
}

# 后端在部分规则里用简写标记状态（missing、justify、new-page 等），
# 这些是内部取值，不能直接印到报告上。与前端 App.tsx 的 VALUE_LABELS 保持一致。
VALUE_LABELS = {
    "missing": "缺失",
    "missing-drawing": "缺图",
    "missing-table": "缺表",
    "missing-or-invalid": "缺失或格式错误",
    "out-of-order": "顺序不符",
    "no extra entry": "不应存在",
    "none": "未设置",
    "default": "默认",
    "drawing": "有图",
    "table": "有表",
    "page field": "页码域",
    "decimal": "阿拉伯数字",
    "upperRoman": "大写罗马数字",
    "lowerRoman": "小写罗马数字",
    "upperLetter": "大写字母",
    "lowerLetter": "小写字母",
    "header": "页眉",
    "footer": "页脚",
    "header_footer": "页眉或页脚",
    "left": "左对齐",
    "center": "居中",
    "right": "右对齐",
    "justify": "两端对齐",
    "both": "两端对齐",
    "distribute": "分散对齐",
    "below": "下方",
    "above": "上方",
    "same-page": "与上文同页",
    "new-page": "另起一页",
    "comma": "逗号",
    "semicolon": "分号",
    "no trailing punctuation": "不应有结尾标点",
    "True": "是",
    "False": "否",
    "true": "是",
    "false": "否",
}

# 规则里用占位标题标记论文结构，报告上要换成读者认得的叫法。
SECTION_LABELS = {
    "ABSTRACT": "英文摘要",
    "ABSTRACT_CN": "中文摘要",
    "REFERENCES": "参考文献",
    "KEYWORDS": "关键词",
}

# 页边距按习惯顺序（上下左右、页眉页脚）排列，而不是按规则文件里的顺序。
MARGIN_ORDER = {
    "上边距": 0,
    "下边距": 1,
    "左边距": 2,
    "右边距": 3,
    "页眉距边界": 4,
    "页脚距边界": 5,
    "纸张宽度": 6,
    "纸张高度": 7,
}


# 未经过 relocate_errors 的位置仍是机器标识（p-0037:run-0002 等），报告端再兜底转换一次。
_MACHINE_LOCATION_RE = re.compile(
    r"^(?:p-\d+|section-\d+|table-\d+|toc(?::|$)|structure(?::|$)|header(?::|$)|"
    r"page-number$|keywords$|abstract-length$|abstract-pair$|citation-order$)"
)


def _text(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def error_excerpt(content: str) -> str:
    collapsed = re.sub(r"\s+", " ", content).strip()
    if len(collapsed) <= ERROR_EXCERPT_LENGTH:
        return collapsed
    return f"{collapsed[:ERROR_EXCERPT_LENGTH]}……"


def _error_type_label(error_type: str) -> str:
    return ERROR_TYPE_LABELS.get(error_type, error_type)


def _display_value(value: object) -> str:
    """把内部枚举值翻成中文；不认识的值原样保留，不编造。"""
    text = str(value if value is not None else "").strip()
    if not text:
        return "—"
    label = VALUE_LABELS.get(text) or SECTION_LABELS.get(text)
    if label:
        return label
    after = re.fullmatch(r"after (.+)", text)
    if after:
        title = after.group(1)
        return f"位于“{SECTION_LABELS.get(title, title)}”之后"
    level = re.fullmatch(r"level=(\d+)", text)
    if level:
        return f"第 {level.group(1)} 级"
    bounded = re.fullmatch(r"0-(\d+)(词|汉字)", text)
    if bounded:
        return f"不超过 {bounded.group(1)} {bounded.group(2)}"
    return text


def _display_content(error) -> str:
    excerpt = error_excerpt(error.content)
    if error.type == "required_sections_error" and excerpt:
        return SECTION_LABELS.get(excerpt, excerpt)
    return excerpt or "—"


def _display_location(task: TaskRecord, error) -> str:
    location = error.location
    if not location:
        return "—"
    if task.document is not None and _MACHINE_LOCATION_RE.match(location):
        location = format_location(task.document, location)
    if error.type == "required_sections_error" and location == "论文结构":
        title = error.content.strip()
        if title:
            return f"论文结构（{SECTION_LABELS.get(title, title)}）"
    return location


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName=font_name, fontSize=20, leading=26, alignment=TA_CENTER, textColor=INK, spaceAfter=1 * mm),
        "meta": ParagraphStyle("ReportMeta", parent=base["BodyText"], fontName=font_name, fontSize=9, leading=14, textColor=INK),
        "heading": ParagraphStyle("ReportHeading", parent=base["Heading2"], fontName=font_name, fontSize=12.5, leading=18, textColor=ACCENT, spaceBefore=5 * mm, spaceAfter=2 * mm),
        "group": ParagraphStyle("ReportGroup", parent=base["BodyText"], fontName=font_name, fontSize=10, leading=15, textColor=INK, spaceBefore=3.5 * mm, spaceAfter=1.5 * mm, keepWithNext=1),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontName=font_name, fontSize=9.5, leading=15, textColor=INK),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontName=font_name, fontSize=8, leading=12, textColor=MUTED),
        "cell": ParagraphStyle("ReportCell", parent=base["BodyText"], fontName=font_name, fontSize=7.8, leading=11, textColor=INK),
        "cell_header": ParagraphStyle("ReportCellHeader", parent=base["BodyText"], fontName=font_name, fontSize=8, leading=11, textColor=colors.white),
    }


def _table_style(font_name: str) -> TableStyle:
    """只有横向分隔线的表格，减少线条噪音；首行为深色表头。"""
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_BG]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, HEADER_BG),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _clause_reference(rule_id: str | None, mapping: dict[str, dict]) -> str:
    """把一条错误回指到规范条款；找不到时留空而不是编造。"""
    if rule_id is None:
        return "—"
    clause = mapping.get(rule_id)
    return clause["title"] if clause else "—"


def _group_errors(
    task: TaskRecord, clause_mapping: dict[str, dict]
) -> "OrderedDict[tuple[str, str], list]":
    """按「问题类型 + 规范条款」分组，避免同类问题刷屏。"""
    groups: OrderedDict[tuple[str, str], list] = OrderedDict()
    for error in task.errors:
        key = (
            _error_type_label(error.type),
            _clause_reference(error.rule_id, clause_mapping),
        )
        groups.setdefault(key, []).append(error)
    return groups


def _section_order(rules: RuleSet) -> dict[str, int]:
    """规范里「必备结构」的装订顺序，用来给该组错误排序。"""
    for check in rules.checks:
        if check.enabled and check.type == "required_sections":
            titles = check.expected.get("order") or check.expected.get("titles") or []
            return {str(title): index for index, title in enumerate(titles)}
    return {}


def _location_key(text: str) -> list:
    """让「目录第1项」排在「目录第1.1项」前面，而不是按字符比较。"""
    parts = re.split(r"(\d+(?:\.\d+)*)", text)
    return [
        tuple(int(number) for number in part.split(".")) if index % 2 else part
        for index, part in enumerate(parts)
    ]


def _sort_items(
    task: TaskRecord, label: str, items: list, sections: dict[str, int]
) -> list:
    """同一组内按可读位置稳定排序，避免相同位置的多条错误随机换序。"""
    if label == "页边距":
        return sorted(items, key=lambda item: MARGIN_ORDER.get(_display_location(task, item), len(MARGIN_ORDER)))
    if label == "必备结构":
        return sorted(items, key=lambda item: (
            sections.get(item.content.strip(), len(sections)),
            _location_key(_display_location(task, item)),
            _display_content(item),
        ))
    return sorted(items, key=lambda item: (
        _location_key(_display_location(task, item)),
        _display_value(item.current),
        _display_content(item),
        _display_value(item.expected),
    ))


def build_report_story(
    task: TaskRecord,
    *,
    rules: RuleSet,
    rule_file: str,
    styles: dict[str, ParagraphStyle],
    font_name: str,
) -> list:
    """组装报告的版面内容，抽出来便于直接测试报告写了什么。

    先给概览再按问题类型分组列明细：同类错误只出现一个分组标题，
    位置、取值都转成中文，读者不用面对机器标识和英文枚举。
    """
    story: list = [
        Paragraph("论文格式检测报告", styles["title"]),
        HRFlowable(width="100%", thickness=0.8, color=RULE_COLOR, spaceBefore=1 * mm, spaceAfter=4 * mm),
        Paragraph(f"<font color='#5B6B63'>文件名称：</font>{_text(task.filename)}", styles["meta"]),
        Paragraph(f"<font color='#5B6B63'>任务编号：</font>{_text(task.task_id)}", styles["meta"]),
        Paragraph(f"<font color='#5B6B63'>检测状态：</font>{_text(STATUS_LABELS.get(task.status, task.status))}", styles["meta"]),
        Paragraph("检测结果", styles["heading"]),
    ]
    if not task.errors:
        story.append(Paragraph("未发现格式问题，检测通过。", styles["body"]))
    else:
        clause_mapping = clauses_by_rule_id(rules)
        groups = _group_errors(task, clause_mapping)
        type_count = len({_error_type_label(error.type) for error in task.errors})
        story.append(Paragraph(f"共发现 {len(task.errors)} 个问题。", styles["body"]))
        story.append(Paragraph(
            f"涉及 {type_count} 类格式项，已按类型分组。「当前格式」是文档中的实际取值，"
            "「规范要求」是规范规定的取值。",
            styles["small"],
        ))
        story.extend([Spacer(1, 2 * mm), _overview_table(groups, styles, font_name)])
        story.append(Paragraph("问题明细", styles["heading"]))
        sections = _section_order(rules)
        number = 0
        for group_index, ((label, clause), items) in enumerate(groups.items(), start=1):
            items = _sort_items(task, label, items, sections)
            heading = f"{group_index}. {_text(label)}（{len(items)} 项）"
            if clause != "—":
                heading += f"<font size=8 color='#5B6B63'>　规范依据：{_text(clause)}</font>"
            story.append(Paragraph(heading, styles["group"]))
            # 页边距、页码这类错误没有对应文字，整列留空反而占地方。
            has_content = any(error.content.strip() for error in items)
            headers = ["序号", "位置"] + (["相关文字"] if has_content else []) + ["当前格式", "规范要求"]
            widths = [12, 38, 50, 32, 42] if has_content else [12, 62, 42, 58]
            rows = [[Paragraph(item, styles["cell_header"]) for item in headers]]
            for error in items:
                number += 1
                cells = [
                    Paragraph(str(number), styles["cell"]),
                    Paragraph(_text(_display_location(task, error)), styles["cell"]),
                ]
                if has_content:
                    cells.append(Paragraph(_text(_display_content(error)), styles["cell"]))
                cells.extend([
                    Paragraph(_text(_display_value(error.current)), styles["cell"]),
                    Paragraph(_text(_display_value(error.expected)), styles["cell"]),
                ])
                rows.append(cells)
            table = Table(rows, colWidths=[width * mm for width in widths], repeatRows=1)
            table.setStyle(_table_style(font_name))
            story.append(table)

    # 检测依据简化为仅规范名称，放在结果之后
    summary = summarize_rule_source(rules)
    title_line = summary["title"]
    if summary["scope"]:
        title_line = f"{title_line}（适用范围：{summary['scope']}）"
    story.extend([
        Spacer(1, 4 * mm),
        Paragraph("检测依据", styles["heading"]),
        Paragraph(f"规范名称：{_text(title_line)}", styles["body"]),
    ])
    return story


def _overview_table(
    groups: "OrderedDict[tuple[str, str], list]",
    styles: dict[str, ParagraphStyle],
    font_name: str,
) -> Table:
    """类型 / 数量 / 规范依据的一页纸概览。"""
    totals: "OrderedDict[str, list]" = OrderedDict()
    for (label, clause), items in groups.items():
        entry = totals.setdefault(label, [0, []])
        entry[0] += len(items)
        if clause != "—" and clause not in entry[1]:
            entry[1].append(clause)

    rows = [[Paragraph(item, styles["cell_header"]) for item in ("问题类型", "数量", "规范依据")]]
    for label, (count, clauses) in totals.items():
        rows.append([
            Paragraph(_text(label), styles["cell"]),
            Paragraph(str(count), styles["cell"]),
            Paragraph(_text("、".join(clauses) if clauses else "—"), styles["cell"]),
        ])
    table = Table(rows, colWidths=[44 * mm, 18 * mm, 112 * mm], repeatRows=1)
    style = _table_style(font_name)
    style.add("ALIGN", (1, 0), (1, -1), "CENTER")
    style.add("ALIGN", (0, 0), (0, -1), "CENTER")
    table.setStyle(style)
    return table


def _page_footer(font_name: str):
    def draw(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(A4[0] / 2, 9 * mm, f"第 {document.page} 页")
        canvas.restoreState()

    return draw


def build_report(task: TaskRecord, *, rules: RuleSet, rule_file: str) -> Path:
    font_name = ensure_report_font()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = report_path(report_id_for(task.task_id))
    styles = _styles(font_name)
    story = build_report_story(task, rules=rules, rule_file=rule_file, styles=styles, font_name=font_name)
    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"{Path(task.filename).stem}_格式检测报告",
        author="论文格式检测系统",
    )
    footer = _page_footer(font_name)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return target
