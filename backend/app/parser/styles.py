"""解析 styles.xml，补足 python-docx 对继承链和主题字体的不足。"""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from .units import half_points

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CJK = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef\u2018-\u201d\u2026\u00b7]")
EAST_ASIAN_FONTS = {
    "宋体", "黑体", "楷体", "仿宋", "微软雅黑",
    "华文宋体", "华文黑体", "华文楷体", "华文中宋", "华文仿宋", "华文行楷",
}
LATIN_COMPANIONS = {"Times New Roman", "TimesNewRoman"}

# OOXML 的 w:jc 取值与 python-docx 的枚举名不是一套词表：样式里两端对齐写的是
# both，而段落直接格式经 python-docx 读出来是 justify。不归一就会让同一处格式
# 因为写在样式里还是写在段落里而得出两个值，规则据此误报。这里统一到
# paragraph.alignment.name.lower()（见 word_parser）。
ALIGNMENT_ALIASES = {
    "start": "left",
    "end": "right",
    "both": "justify",
    "mediumkashida": "justify_med",
    "highkashida": "justify_hi",
    "lowkashida": "justify_low",
    "thaidistribute": "thai_justify",
}


def normalize_alignment(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    return ALIGNMENT_ALIASES.get(lowered, lowered)


def parse_theme(root: ET.Element | None) -> dict:
    """提取 Office 主题字体，以解析 minorEastAsia 等间接字体引用。"""
    result = {}
    if root is None:
        return result
    for family, tag in (("major", "majorFont"), ("minor", "minorFont")):
        node = root.find(f".//{A}{tag}")
        if node is not None:
            for key, child in (("Ascii", "latin"), ("EastAsia", "ea"), ("Cs", "cs")):
                item = node.find(f"{A}{child}")
                if item is not None and item.get("typeface"):
                    result[f"{family}{key}"] = item.get("typeface")
    return result


def parse_styles(root: ET.Element | None) -> dict:
    result = {"styles": {}, "defaults": {}}
    if root is None:
        return result
    defaults = root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
    default_ppr = root.find(f"{W}docDefaults/{W}pPrDefault/{W}pPr")
    result["defaults"] = _rpr(defaults)
    result["paragraph_defaults"] = _ppr(default_ppr)
    for s in root.findall(f"{W}style"):
        sid = s.get(f"{W}styleId")
        if sid:
            based = s.find(f"{W}basedOn")
            result["styles"][sid] = {
                "name": s.findtext(f"{W}name") or "",
                "based_on": based.get(f"{W}val") if based is not None else None,
                "rpr": _rpr(s.find(f"{W}rPr")),
                "ppr": _ppr(s.find(f"{W}pPr")),
            }
    return result


def _twips(value: str | None) -> float | None:
    try:
        return float(value) / 20 if value is not None else None
    except (TypeError, ValueError):
        return None


def _ppr(ppr: ET.Element | None) -> dict:
    if ppr is None:
        return {}
    out: dict = {}
    jc = ppr.find(f"{W}jc")
    if jc is not None and jc.get(f"{W}val"):
        out["alignment"] = normalize_alignment(jc.get(f"{W}val"))
    spacing = ppr.find(f"{W}spacing")
    if spacing is not None:
        before, after = _twips(spacing.get(f"{W}before")), _twips(spacing.get(f"{W}after"))
        if before is not None: out["space_before_pt"] = before
        if after is not None: out["space_after_pt"] = after
        line = spacing.get(f"{W}line")
        if line is not None:
            try:
                raw = float(line)
                rule = (spacing.get(f"{W}lineRule") or "auto").lower()
                out["line_spacing"] = raw / 20 if rule in {"exact", "atleast"} else raw / 240
            except ValueError:
                pass
    ind = ppr.find(f"{W}ind")
    if ind is not None:
        for attr, key in (("left", "left_indent_pt"), ("right", "right_indent_pt"), ("firstLine", "first_line_indent_pt"), ("hanging", "hanging_indent_pt")):
            value = _twips(ind.get(f"{W}{attr}"))
            if value is not None: out[key] = value
        for attr, key in (("firstLineChars", "first_line_indent_chars"), ("hangingChars", "hanging_indent_chars")):
            value = ind.get(f"{W}{attr}")
            if value is not None:
                try: out[key] = float(value) / 100
                except ValueError: pass
    return out

def _rpr(rpr: ET.Element | None) -> dict:
    if rpr is None:
        return {}
    out = {}
    for key, tag in (("bold", "b"), ("italic", "i")):
        node = rpr.find(f"{W}{tag}")
        if node is not None:
            out[key] = node.get(f"{W}val", "true") not in {"0", "false", "off"}
    fonts = rpr.find(f"{W}rFonts")
    if fonts is not None:
        out["font"] = {k: fonts.get(f"{W}{k}") for k in ("ascii", "hAnsi", "eastAsia", "cs") if fonts.get(f"{W}{k}")}
        out["font_theme"] = {k: fonts.get(f"{W}{k}Theme") for k in ("ascii", "hAnsi", "eastAsia", "cs") if fonts.get(f"{W}{k}Theme")}
    size = rpr.find(f"{W}sz")
    if size is not None:
        out["size_pt"] = half_points(size.get(f"{W}val"))
    return out


def _merge_rpr(merged: dict, rpr: dict) -> None:
    for key, value in rpr.items():
        if key in {"font", "font_theme"} and isinstance(value, dict):
            current = merged.setdefault(key, {})
            for font_key, font_value in value.items():
                current.setdefault(font_key, font_value)
        else:
            merged.setdefault(key, value)


def resolve_style(style_id: str, resources: dict) -> dict:
    merged, seen = {}, set()
    current = style_id
    while current and current not in seen:
        seen.add(current)
        item = resources.get("styles", {}).get(current, {})
        _merge_rpr(merged, item.get("rpr", {}))
        current = item.get("based_on")
    _merge_rpr(merged, resources.get("defaults", {}))
    paragraph = {}
    current = style_id
    seen = set()
    while current and current not in seen:
        seen.add(current)
        item = resources.get("styles", {}).get(current, {})
        for key, value in item.get("ppr", {}).items():
            paragraph.setdefault(key, value)
        current = item.get("based_on")
    for key, value in resources.get("paragraph_defaults", {}).items():
        paragraph.setdefault(key, value)
    merged["paragraph"] = paragraph
    font = dict(merged.get("font", {}))
    for key, theme_key in merged.get("font_theme", {}).items():
        font.setdefault(key, resources.get("theme", {}).get(theme_key))
    if font:
        merged["font"] = font
    return merged


def font_for_text(font: dict | None, text: str | None) -> str | None:
    """Pick the script-appropriate font: CJK -> eastAsia, otherwise ascii."""
    payload = font or {}
    east = payload.get("east_asia") or payload.get("eastAsia")
    ascii_name = payload.get("ascii") or payload.get("hAnsi")
    if CJK.search(text or ""):
        return east or payload.get("effective") or ascii_name
    if not (text or "").strip():
        return None
    return ascii_name or payload.get("effective") or east


def font_matches(current: str | None, expected: str | None, text: str | None) -> bool:
    if current is None or expected is None:
        return True
    if current == expected:
        return True
    if CJK.search(text or ""):
        return False
    return expected in EAST_ASIAN_FONTS and current in LATIN_COMPANIONS
