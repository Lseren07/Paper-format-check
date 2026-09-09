class DocumentParseError(ValueError):
    """解析失败时向上层暴露的稳定异常，不泄露底层路径或文档内容。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
