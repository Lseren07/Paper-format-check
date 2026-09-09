"""解析部件关系，图片和图表只输出元数据，不读取二进制。"""
from xml.etree import ElementTree as ET
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
def parse_relationships(root: ET.Element | None) -> dict[str, str]:
    if root is None: return {}
    return {r.get("Id"): r.get("Target", "") for r in root.findall(f"{REL}Relationship") if r.get("Id")}
