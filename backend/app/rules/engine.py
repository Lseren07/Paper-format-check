from collections.abc import Callable

from ..models.contracts import Document, ErrorItem
from .contracts import CheckRule, RuleSet
from .detectors import (
    detect_alignment, detect_bold, detect_font, detect_heading_numbering,
    detect_line_spacing, detect_paragraph_indent, detect_reference_baseline,
    detect_size, detect_table_figure_format, detect_toc_consistency, detect_page_margin,
)

Detector = Callable[[Document, CheckRule], list[ErrorItem]]
DETECTORS: dict[str, Detector] = {
    "font": detect_font,
    "size": detect_size,
    "bold": detect_bold,
    "alignment": detect_alignment,
    "line_spacing": detect_line_spacing,
    "paragraph_indent": detect_paragraph_indent,
    "heading_numbering": detect_heading_numbering,
    "toc_consistency": detect_toc_consistency,
    "table_figure_format": detect_table_figure_format,
    "reference_baseline": detect_reference_baseline,
    "page_margin": detect_page_margin,
}


class RuleEngine:
    def __init__(self, document: Document, rules: RuleSet) -> None:
        self.document = document
        self.rules = rules

    def run(self) -> list[ErrorItem]:
        errors: list[ErrorItem] = []
        for rule in self.rules.checks:
            if not rule.enabled:
                continue
            detector = DETECTORS.get(rule.type)
            if detector is None:
                raise ValueError(f"unknown rule type: {rule.type}")
            errors.extend(detector(self.document, rule))
        return sorted(errors, key=lambda error: (error.location, error.error_id))
