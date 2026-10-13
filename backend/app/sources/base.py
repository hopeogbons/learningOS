from dataclasses import dataclass, field
from typing import Any


class SourceError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code, self.message, self.retryable = code, message, retryable
        super().__init__(message)


@dataclass(frozen=True)
class ExtractedSection:
    title: str
    text: str
    locator_kind: str
    locator: dict[str, Any]


@dataclass(frozen=True)
class SourceSnapshot:
    sections: list[ExtractedSection]
    canonical_url: str | None = None
    source_language: str = 'und'
    metadata: dict[str, Any] = field(default_factory=dict)
