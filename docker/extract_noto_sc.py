"""Extract Noto Sans CJK SC from a Debian TTC/OTC into a ReportLab-friendly TTF."""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib.ttCollection import TTCollection

SEARCH_ROOT = Path("/usr/share/fonts")
OUTPUT = Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf")


def _font_names(font) -> str:
    names: list[str] = []
    table = font.get("name")
    if table is None:
        return ""
    for record in table.names:
        try:
            names.append(record.toUnicode())
        except Exception:
            continue
    return " ".join(names)


def _prefer_sc(fonts: list) -> object:
    scored: list[tuple[int, object]] = []
    for font in fonts:
        blob = _font_names(font)
        score = 0
        if "SC" in blob or "CN" in blob or "Simplified" in blob:
            score += 4
        if "Sans" in blob:
            score += 2
        if "Serif" in blob:
            score -= 1
        scored.append((score, font))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def main() -> None:
    candidates = sorted(
        list(SEARCH_ROOT.rglob("NotoSansCJK*.ttc"))
        + list(SEARCH_ROOT.rglob("NotoSansCJK*.otc"))
        + list(SEARCH_ROOT.rglob("NotoSansCJKsc*.ttc"))
    )
    if not candidates:
        found = ", ".join(str(path) for path in list(SEARCH_ROOT.rglob("*.ttc"))[:20])
        raise SystemExit(f"Noto CJK collection not found under {SEARCH_ROOT}. sample={found}")

    source = candidates[0]
    collection = TTCollection(str(source))
    if not collection.fonts:
        raise SystemExit(f"empty font collection: {source}")

    chosen = _prefer_sc(list(collection.fonts))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    chosen.save(str(OUTPUT))
    print(f"extracted {source} -> {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
