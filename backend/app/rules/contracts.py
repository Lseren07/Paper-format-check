from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuleTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["all", "body", "heading"] = "all"
    heading_level: int | None = None

    @model_validator(mode="after")
    def validate_heading_target(self) -> "RuleTarget":
        if self.name == "heading" and self.heading_level is None:
            raise ValueError("heading target requires heading_level")
        if self.name != "heading" and self.heading_level is not None:
            raise ValueError("heading_level is only valid for heading targets")
        if self.heading_level is not None and not 1 <= self.heading_level <= 9:
            raise ValueError("heading_level must be between 1 and 9")
        return self


class CheckRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    target: str | RuleTarget = "all"
    expected: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RuleClause(BaseModel):
    """规范原文中的一条条款摘要，用于向教师说明「为什么报这个错」。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    chapter: str
    text: str
    rules: list[str] = Field(default_factory=list)
    automated: bool = True


class RuleSource(BaseModel):
    """规则库的来源规范，描述本套 checks 依据哪份文件的哪些条款。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    document: str
    organization: str | None = None
    scope: str | None = None
    clauses: list[RuleClause] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuleSet(BaseModel):
    """一套完整的格式规则。

    `rule_set_id` 用于目录扫描时标识这套规则：省略时注册表回退到文件名。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    rule_set_id: str | None = None
    name: str
    description: str | None = None
    source: RuleSource | None = None
    checks: list[CheckRule] = Field(default_factory=list)
