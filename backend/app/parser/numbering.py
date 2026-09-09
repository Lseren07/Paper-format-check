"""读取 numbering.xml 的编号模板；复杂格式无法可靠展开时保留原模板。"""
from xml.etree import ElementTree as ET
import re
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def parse_numbering(root: ET.Element | None) -> dict:
    if root is None: return {}
    abstract = {}
    for a in root.findall(f"{W}abstractNum"):
        levels = {}
        for lvl in a.findall(f"{W}lvl"):
            ilvl = lvl.get(f"{W}ilvl", "0")
            levels[ilvl] = {k: (lvl.find(f"{W}{tag}").get(f"{W}val") if lvl.find(f"{W}{tag}") is not None else None) for k, tag in (("format", "numFmt"), ("level_text", "lvlText"), ("start", "start"))}
        abstract[a.get(f"{W}abstractNumId")] = levels
    nums = {}
    for n in root.findall(f"{W}num"):
        aid = n.find(f"{W}abstractNumId")
        nums[n.get(f"{W}numId")] = abstract.get(aid.get(f"{W}val") if aid is not None else "", {})
    return nums


def numbering_label(template: str | None, counters: list[int], number_format: str | None) -> str | None:
    """展开常见 decimal 多级模板；其他格式保留定义，避免伪造编号。"""
    if not template:
        return None

    def convert(value: int) -> str:
        if number_format == "decimal": return str(value)
        if number_format in {"upperRoman", "lowerRoman"}:
            result = ""; numerals = ((1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I"))
            for amount, numeral in numerals: result += numeral * (value // amount); value %= amount
            return result if number_format == "upperRoman" else result.lower()
        if number_format in {"upperLetter", "lowerLetter"}: 
            out = ""
            while value: value, rem = divmod(value - 1, 26); out = chr(65 + rem) + out
            return out if number_format == "upperLetter" else out.lower()
        return str(value)

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        return convert(counters[index]) if 0 <= index < len(counters) else match.group(0)
    return re.sub(r"%(\d+)", replace, template)
