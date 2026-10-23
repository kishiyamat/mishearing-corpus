"""HTTP contracts shared by search, individual records, and exports."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CSV_FIELDS = (
    "MishearID",
    "Src",
    "Tgt",
    "Tips",
    "Note",
    "OriginalFlag",
    "DocID",
    "URL",
    "SpeakerID",
    "ListenerID",
    "Language",
)
SearchText = Annotated[str, Field(min_length=1, max_length=500)]
ClassificationID = Annotated[str, Field(min_length=1, max_length=128)]


class VersionQuery(BaseModel):
    """Validate a requested dataset SHA without accepting arbitrary Git revisions."""

    model_config = ConfigDict(extra="forbid")
    dataset_version: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{40}$", description="Full advertised Git SHA"
    )


class AppliedFilters(BaseModel):
    """Describe effective search conditions, independent of pagination or format."""

    q: SearchText | None = None
    src: SearchText | None = None
    tgt: SearchText | None = None
    tags: list[ClassificationID] = Field(default_factory=list, max_length=50)
    tag_mode: Literal["and", "or"] = "and"
    environments: list[ClassificationID] = Field(default_factory=list, max_length=50)
    environment_mode: Literal["and", "or"] = "and"
    language: SearchText | None = None
    source: SearchText | None = None

    @field_validator("tags", "environments")
    @classmethod
    def canonicalize_ids(cls, values: list[str]) -> list[str]:
        """Remove duplicate classification IDs and report them in stable order."""
        return sorted(set(values))


class SearchQuery(AppliedFilters, VersionQuery):
    """Combine effective filters and a version constraint for read operations."""

    def applied(self) -> AppliedFilters:
        """Return only effective filters, excluding transport-specific controls."""
        return AppliedFilters.model_validate(
            self.model_dump(include=set(AppliedFilters.model_fields))
        )


class RecordsQuery(SearchQuery):
    """Bound page size and offset while preserving the shared search contract."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ExportQuery(SearchQuery):
    """Select an export format; pagination controls are intentionally forbidden."""

    format: Literal["csv", "jsonl"] = "csv"


class Record(BaseModel):
    """Preserve CSV cells as strings and attach immutable public associations.

    Construct with the eleven CSV columns plus source provenance. Empty cells
    stay empty strings; OriginalFlag is not coerced to a boolean.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    MishearID: str
    Src: str
    Tgt: str
    Tips: str
    Note: str
    OriginalFlag: str
    DocID: str
    URL: str
    SpeakerID: str
    ListenerID: str
    Language: str
    TagIDs: tuple[str, ...] = ()
    EnvIDs: tuple[str, ...] = ()
    source: str
    source_file: str


class SnapshotMetadata(BaseModel):
    """Identify both the Git revision and the bytes that supplied an answer."""

    model_config = ConfigDict(frozen=True)
    dataset_version: str
    dataset_sha256: str


class LinkQuality(BaseModel):
    """Count bridge rows referencing an absent record without altering inputs."""

    model_config = ConfigDict(frozen=True)
    orphan_tag_links: int = 0
    orphan_environment_links: int = 0


class DatasetInfo(SnapshotMetadata):
    """Advertise one loaded snapshot and filter IDs attached to actual records."""

    id: str = "mishearing-corpus"
    record_count: int
    file_count: int
    tag_ids: tuple[str, ...]
    environment_ids: tuple[str, ...]
    languages: tuple[str, ...]
    sources: tuple[str, ...]
    quality: LinkQuality


class DatasetsResponse(BaseModel):
    """List only the dataset versions this instance can actually serve."""

    datasets: tuple[DatasetInfo, ...]


class RecordsResponse(SnapshotMetadata):
    """Return a page with full-match counts and reproducible effective filters."""

    filters: AppliedFilters
    total: int
    limit: int
    offset: int
    next_offset: int | None
    records: tuple[Record, ...]


class RecordResponse(SnapshotMetadata):
    """Return one exact-ID match and its input snapshot provenance."""

    record: Record
