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
    result["defaults"] = _rpr(defaults)
    for s in root.findall(f"{W}style"):
        sid = s.get(f"{W}styleId")
        if sid:
            based = s.find(f"{W}basedOn")
            result["styles"][sid] = {
                "name": s.findtext(f"{W}name") or "",
                "based_on": based.get(f"{W}val") if based is not None else None,
                "rpr": _rpr(s.find(f"{W}rPr")),
            }
    return result


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
