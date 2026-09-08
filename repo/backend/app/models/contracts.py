from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    document_id: str
    source_filename: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    paragraphs: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    headers: list[dict[str, Any]] = Field(default_factory=list)
    footers: list[dict[str, Any]] = Field(default_factory=list)
    pages: list[dict[str, Any]] = Field(default_factory=list)


class ErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_id: str
    type: str
    location: str
    content: str
    current: str
    expected: str
