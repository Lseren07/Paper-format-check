"""解析 styles.xml，补足 python-docx 对继承链和主题字体的不足。"""
from xml.etree import ElementTree as ET
from .units import half_points
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

def parse_theme(root: ET.Element | None) -> dict:
    """提取 Office 主题字体，以解析 minorEastAsia 等间接字体引用。"""
    result = {}
    if root is None: return result
    for family, tag in (("major", "majorFont"), ("minor", "minorFont")):
        node = root.find(f".//{A}{tag}")
        if node is not None:
            for key, child in (("Ascii", "latin"), ("EastAsia", "ea"), ("Cs", "cs")):
                item = node.find(f"{A}{child}")
                if item is not None and item.get("typeface"): result[f"{family}{key}"] = item.get("typeface")
    return result

def parse_styles(root: ET.Element | None) -> dict:
    result = {"styles": {}, "defaults": {}}
    if root is None: return result
    defaults = root.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
    result["defaults"] = _rpr(defaults)
    for s in root.findall(f"{W}style"):
        sid = s.get(f"{W}styleId")
        if sid:
            based = s.find(f"{W}basedOn")
            result["styles"][sid] = {"name": s.findtext(f"{W}name") or "", "based_on": based.get(f"{W}val") if based is not None else None, "rpr": _rpr(s.find(f"{W}rPr"))}
    return result

def _rpr(rpr: ET.Element | None) -> dict:
    if rpr is None: return {}
    out = {}
    for key, tag in (("bold", "b"), ("italic", "i")):
        node = rpr.find(f"{W}{tag}")
        if node is not None: out[key] = node.get(f"{W}val", "true") not in {"0", "false", "off"}
    fonts = rpr.find(f"{W}rFonts")
    if fonts is not None:
        out["font"] = {k: fonts.get(f"{W}{k}") for k in ("ascii", "hAnsi", "eastAsia", "cs") if fonts.get(f"{W}{k}")}
        out["font_theme"] = {k: fonts.get(f"{W}{k}Theme") for k in ("ascii", "hAnsi", "eastAsia", "cs") if fonts.get(f"{W}{k}Theme")}
    size = rpr.find(f"{W}sz")
    if size is not None: out["size_pt"] = half_points(size.get(f"{W}val"))
    return out

def resolve_style(style_id: str, resources: dict) -> dict:
    merged, seen = {}, set()
    current = style_id
    while current and current not in seen:
        seen.add(current)
        item = resources.get("styles", {}).get(current, {})
        for k, v in item.get("rpr", {}).items():
            merged.setdefault(k, v)
        current = item.get("based_on")
    for key, value in resources.get("defaults", {}).items():
        merged.setdefault(key, value)
    font = dict(merged.get("font", {}))
    for key, theme_key in merged.get("font_theme", {}).items():
        font.setdefault(key, resources.get("theme", {}).get(theme_key))
    if font: merged["font"] = font
    return merged
