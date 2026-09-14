from ..models.contracts import ErrorItem
from .contracts import CheckRule


_ERROR_TYPES = {
    "font": "font_error", "size": "size_error", "bold": "bold_error",
    "alignment": "alignment_error", "line_spacing": "line_spacing_error",
    "paragraph_indent": "paragraph_indent_error",
}


def make_error(rule: CheckRule, *, location: str, content: str, current: str, expected: str) -> ErrorItem:
    return ErrorItem(
        error_id=f"{rule.id}:{location}",
        type=_ERROR_TYPES.get(rule.type, f"{rule.type}_error"),
        location=location,
        content=content,
        current=current,
        expected=expected,
        rule_id=rule.id,
        basis=_rule_basis(rule),
    )


def _rule_basis(rule: CheckRule) -> str:
    """Provide a compact, traceable explanation for a report or UI."""
    expected = ", ".join(f"{key}={value}" for key, value in rule.expected.items())
    return f"规则 {rule.id}：{expected}" if expected else f"规则 {rule.id}"
