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


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    name: str
    checks: list[CheckRule] = Field(default_factory=list)
