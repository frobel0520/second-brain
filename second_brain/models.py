"""跨層共用的資料結構。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Document:
    id: str
    source_path: str
    title: str
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    translated_content: str | None = None
    category: str | None = None
    starred: bool = False


@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    chunk: Chunk
    document: Document
    score: float


@dataclass
class DocumentSummary:
    id: str
    title: str
    source_path: str
    created_at: datetime
    chunk_count: int
    tags: list[str] = field(default_factory=list)
    has_translation: bool = False
    category: str | None = None
    starred: bool = False


@dataclass
class FeedSubscription:
    id: str
    url: str
    name: str
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_synced_at: datetime | None = None
    category: str | None = None
