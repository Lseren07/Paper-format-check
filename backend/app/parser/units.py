"""Word 常用内部单位转换。"""

def half_points(value: str | None) -> float | None:
    try: return int(value) / 2 if value is not None else None
    except (TypeError, ValueError): return None

def twips_to_points(value: int | None) -> float | None:
    return value / 20 if value is not None else None

def emu_to_points(value: int | None) -> float | None:
    return value / 12700 if value is not None else None
