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
    )
