from __future__ import annotations

from datetime import date
import json
from typing import Any, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class PublicationSource(BaseModel):
    """The HEW publication fields consumed by the v1 projection."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str
    title: str
    resource_type: Literal["literature"]
    abstract: str | None = None
    description: str | None = None
    url: AnyUrl | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    identifiers: list[str] | None = None
    authors: list[str] | None = None
    keywords: list[str] | None = None
    citation: str | None = None
    journal: str | None = None
    publication_type: str | None = None
    publication_date: date | None = None
    status: str | None = None
    related_resources: list[str] | None = None

    @field_validator("id", "title")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class CrosswalkContext(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    catalog_version: str
    metadata_block_version: str
    target_collection: str
    hew_schema_version: str = "1.2.0"
    crosswalk_version: str = "1.0.0"

    @field_validator(
        "catalog_version",
        "metadata_block_version",
        "target_collection",
        "hew_schema_version",
        "crosswalk_version",
    )
    @classmethod
    def require_context_value(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class DataverseField(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type_name: str = Field(alias="typeName")
    multiple: bool
    type_class: Literal["primitive", "compound", "controlledVocabulary"] = Field(
        alias="typeClass"
    )
    value: Any


class DataverseMetadataBlock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    display_name: str = Field(alias="displayName")
    fields: list[DataverseField]


class MappingEntry(BaseModel):
    source: str
    target: str | None = None
    detail: str | None = None


class MappingReport(BaseModel):
    crosswalk_id: str = "hew-publication-to-dataverse"
    crosswalk_version: str
    source_id: str
    mapped: list[MappingEntry] = Field(default_factory=list)
    omitted: list[MappingEntry] = Field(default_factory=list)
    unmapped: list[MappingEntry] = Field(default_factory=list)


class DataversePublicationProjection(BaseModel):
    source_id: str
    crosswalk_version: str
    metadata_blocks: dict[str, DataverseMetadataBlock]
    report: MappingReport
    source_jsonld: dict[str, Any] | None = None

    def to_dataverse_payload(self) -> dict[str, Any]:
        return {
            "datasetVersion": {
                "metadataBlocks": {
                    name: block.model_dump(by_alias=True, exclude_none=True)
                    for name, block in self.metadata_blocks.items()
                }
            }
        }

    def to_dataverse_json(self) -> str:
        """Serialize only the Dataverse metadata payload as valid JSON."""
        return json.dumps(self.to_dataverse_payload(), indent=2, sort_keys=True)

    def to_preservation_document(self) -> dict[str, Any] | None:
        """Return the original JSON-LD document for attachment storage."""
        return self.source_jsonld
