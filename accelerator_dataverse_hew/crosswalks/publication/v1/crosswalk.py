from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from accelerator_dataverse_hew.crosswalks.publication.v1.models import (
    CrosswalkContext,
    DataverseField,
    DataverseMetadataBlock,
    DataversePublicationProjection,
    MappingEntry,
    MappingReport,
    PublicationSource,
)


class PublicationValidationError(ValueError):
    """Raised when a source record cannot satisfy the publication contract."""


def _context_contains_hew(context: Any) -> bool:
    if isinstance(context, str):
        return "w3id.org/hew" in context
    if isinstance(context, list):
        return any(_context_contains_hew(item) for item in context)
    if isinstance(context, Mapping):
        if any(key in {"HEW", "hew", "HEWRES", "HEWANN"} for key in context):
            return True
        return any(_context_contains_hew(value) for value in context.values())
    return False


def _jsonld_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_jsonld_value(item) for item in value]
    if isinstance(value, Mapping):
        if "@value" in value:
            return value["@value"]
        if "@id" in value:
            return value["@id"]
        if "@list" in value:
            return [_jsonld_value(item) for item in value["@list"]]
        return {key: _jsonld_value(item) for key, item in value.items()}
    return value


def _jsonld_type_name(value: Any) -> str:
    if isinstance(value, list):
        if len(value) != 1:
            raise PublicationValidationError("JSON-LD @type must identify one resource class")
        value = value[0]
    if not isinstance(value, str):
        raise PublicationValidationError("JSON-LD @type must be a string")
    return value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _normalized_jsonld_source(document: Mapping[str, Any], context: CrosswalkContext) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise PublicationValidationError("JSON-LD publication must be an object")
    if "@context" not in document or not _context_contains_hew(document["@context"]):
        raise PublicationValidationError("JSON-LD document is missing a supported HEW @context")
    if "@type" in document:
        type_name = _jsonld_type_name(document["@type"])
        if type_name not in {"HEWResource", "LiteratureResource"}:
            raise PublicationValidationError(f"unsupported HEW JSON-LD @type: {type_name}")

    source = {
        key: _jsonld_value(value)
        for key, value in document.items()
        if not key.startswith("@")
    }
    if "id" not in source and "@id" in document:
        source["id"] = _jsonld_value(document["@id"])
    if "@type" not in document and source.get("resource_type") != "literature":
        raise PublicationValidationError(
            "JSON-LD document without @type must declare resource_type: literature"
        )
    if source.get("hew_schema_version") and source["hew_schema_version"] != context.hew_schema_version:
        raise PublicationValidationError("JSON-LD HEW schema version does not match crosswalk context")
    return source


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
PMID_PATTERN = re.compile(r"^\d+$")
PMCID_PATTERN = re.compile(r"^PMC\d+$", re.IGNORECASE)

KNOWN_SOURCE_FIELDS = {
    "id",
    "title",
    "resource_type",
    "abstract",
    "description",
    "url",
    "doi",
    "pmid",
    "pmcid",
    "identifiers",
    "authors",
    "keywords",
    "citation",
    "journal",
    "publication_type",
    "publication_date",
    "status",
    "related_resources",
}


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _text(value, field_name)


def _normalize_doi(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", normalized, flags=re.I)
    normalized = re.sub(r"^doi:\s*", "", normalized, flags=re.I)
    if not DOI_PATTERN.fullmatch(normalized):
        raise PublicationValidationError(f"invalid DOI: {value}")
    return normalized


def _normalize_pmid(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/", "", normalized, flags=re.I)
    normalized = re.sub(r"^pmid:\s*", "", normalized, flags=re.I).rstrip("/")
    if not PMID_PATTERN.fullmatch(normalized):
        raise PublicationValidationError(f"invalid PMID: {value}")
    return normalized


def _normalize_pmcid(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(r"^https?://pmc\.ncbi\.nlm\.nih\.gov/articles/", "", normalized, flags=re.I)
    normalized = re.sub(r"^pmcid:\s*", "", normalized, flags=re.I).rstrip("/")
    if not PMCID_PATTERN.fullmatch(normalized):
        raise PublicationValidationError(f"invalid PMCID: {value}")
    return normalized.upper()


def _normalize_url(value: Any, field_name: str) -> str:
    try:
        parts = urlsplit(str(value))
    except ValueError as error:
        raise PublicationValidationError(f"invalid {field_name}: {value}") from error
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise PublicationValidationError(f"invalid {field_name}: {value}")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _validate_list(record: Mapping[str, Any], field_name: str) -> None:
    value = record.get(field_name)
    if value is not None and (
        not isinstance(value, list) or any(not isinstance(item, str) for item in value)
    ):
        raise PublicationValidationError(f"{field_name} must be a list of strings")


def validate_publication_source(record: Mapping[str, Any]) -> PublicationSource:
    """Validate the publication contract without discarding unknown HEW fields."""
    if not isinstance(record, Mapping):
        raise PublicationValidationError("publication must be a mapping")
    for field_name in ("id", "title", "resource_type"):
        if field_name not in record:
            raise PublicationValidationError(f"missing required field: {field_name}")
    if record["resource_type"] != "literature":
        raise PublicationValidationError("resource_type must be 'literature'")
    for field_name in ("identifiers", "authors", "keywords", "related_resources"):
        _validate_list(record, field_name)
    for field_name in ("doi", "pmid", "pmcid", "url"):
        if record.get(field_name) is not None:
            _optional_text(record[field_name], field_name)

    try:
        source = PublicationSource.model_validate(record)
    except ValidationError as error:
        raise PublicationValidationError(str(error)) from error

    if source.doi:
        _normalize_doi(source.doi)
    if source.pmid:
        _normalize_pmid(source.pmid)
    if source.pmcid:
        _normalize_pmcid(source.pmcid)
    if source.url:
        _normalize_url(source.url, "url")
    return source


def _field(type_name: str, value: Any, type_class: str = "primitive") -> DataverseField:
    return DataverseField(
        typeName=type_name,
        multiple=isinstance(value, list),
        typeClass=type_class,
        value=value,
    )


def _compound_field(type_name: str, values: list[dict[str, Any]]) -> DataverseField:
    return _field(type_name, values, "compound")


def _identifier_values(source: PublicationSource) -> list[tuple[str, str]]:
    values = []
    if source.doi:
        values.append(("DOI", _normalize_doi(source.doi)))
    if source.pmid:
        values.append(("PMID", _normalize_pmid(source.pmid)))
    if source.pmcid:
        values.append(("PMCID", _normalize_pmcid(source.pmcid)))
    for identifier in source.identifiers or []:
        normalized = identifier.strip()
        if normalized:
            values.append(("HEW", normalized))
    return values


def _other_id_values(source: PublicationSource) -> list[dict[str, Any]]:
    return [
        {
            "otherIdAgency": _field("otherIdAgency", agency),
            "otherIdValue": _field("otherIdValue", value),
        }
        for agency, value in _identifier_values(source)
    ]


def _author_values(source: PublicationSource) -> list[dict[str, Any]]:
    return [
        {"authorName": _field("authorName", author.strip())}
        for author in source.authors or []
        if author.strip()
    ]


def _description_values(source: PublicationSource) -> list[dict[str, Any]]:
    descriptions = []
    for value in (source.abstract, source.description):
        if value and value.strip():
            descriptions.append({"dsDescriptionValue": _field("dsDescriptionValue", value.strip())})
    return descriptions


def _notes_text(source: PublicationSource) -> str | None:
    values = [value.strip() for value in (source.citation, source.journal) if value and value.strip()]
    return "; ".join(values) or None


def _status_label(status: str | None) -> str | None:
    if not status:
        return None
    return {"active": "Active", "draft": "Draft", "archived": "Archived"}.get(
        status.strip().lower()
    )


def _record(report: list[MappingEntry], source: str, target: str | None = None, detail: str | None = None):
    report.append(MappingEntry(source=source, target=target, detail=detail))


def crosswalk_publication(
    record: Mapping[str, Any], context: CrosswalkContext
) -> DataversePublicationProjection:
    """Project a validated HEW literature resource into Dataverse metadata."""
    source = validate_publication_source(record)
    mapped: list[MappingEntry] = []
    omitted: list[MappingEntry] = []
    unmapped: list[MappingEntry] = []

    citation_fields = [
        _field("title", source.title),
        _field("alternativeURL", _normalize_url(source.url, "url")) if source.url else None,
    ]
    if source.url:
        _record(mapped, "url", "citation.alternativeURL")
    else:
        _record(omitted, "url", "citation.alternativeURL", "empty")

    identifiers = _other_id_values(source)
    if identifiers:
        citation_fields.append(_compound_field("otherId", identifiers))
        _record(mapped, "doi/pmid/pmcid/identifiers", "citation.otherId")
    else:
        _record(omitted, "doi/pmid/pmcid/identifiers", "citation.otherId", "empty")

    authors = _author_values(source)
    if authors:
        citation_fields.append(_compound_field("author", authors))
        _record(mapped, "authors", "citation.author")
    else:
        _record(omitted, "authors", "citation.author", "empty")

    descriptions = _description_values(source)
    if descriptions:
        citation_fields.append(_compound_field("dsDescription", descriptions))
        _record(mapped, "abstract/description", "citation.dsDescription")
    else:
        _record(omitted, "abstract/description", "citation.dsDescription", "empty")

    keywords = [keyword.strip() for keyword in source.keywords or [] if keyword.strip()]
    if keywords:
        citation_fields.append(
            _compound_field(
                "keyword",
                [{"keywordValue": _field("keywordValue", keyword)} for keyword in dict.fromkeys(keywords)],
            )
        )
        _record(mapped, "keywords", "citation.keyword")
    else:
        _record(omitted, "keywords", "citation.keyword", "empty")

    notes_text = _notes_text(source)
    if notes_text:
        citation_fields.append(_field("notesText", notes_text))
        _record(mapped, "citation/journal", "citation.notesText")
    else:
        _record(omitted, "citation/journal", "citation.notesText", "empty")

    if source.publication_type:
        citation_fields.append(
            _compound_field(
                "topicClassification",
                [
                    {
                        "topicClassValue": _field(
                            "topicClassValue", source.publication_type
                        )
                    }
                ],
            )
        )
        _record(mapped, "publication_type", "citation.topicClassification")
    else:
        _record(omitted, "publication_type", "citation.topicClassification", "empty")

    if source.publication_date:
        citation_fields.append(_field("productionDate", source.publication_date.isoformat()))
        _record(mapped, "publication_date", "citation.productionDate")
    else:
        _record(omitted, "publication_date", "citation.productionDate", "empty")

    resource_fields = [
        _field("hewResourceId", source.id),
        _field("hewResourceType", "Literature resource", "controlledVocabulary"),
        _field("hewSchemaVersion", context.hew_schema_version),
        _field("hewCatalogVersion", context.catalog_version),
        _field("hewCrosswalkVersion", context.crosswalk_version),
    ]
    _record(mapped, "id", "hewResource.hewResourceId")
    _record(mapped, "resource_type", "hewResource.hewResourceType")
    if source.status:
        status_label = _status_label(source.status)
        if status_label:
            resource_fields.append(_field("hewResourceStatus", status_label, "controlledVocabulary"))
            _record(mapped, "status", "hewResource.hewResourceStatus")
        else:
            _record(unmapped, "status", detail=f"unsupported status: {source.status}")
    else:
        _record(omitted, "status", "hewResource.hewResourceStatus", "empty")

    if source.url:
        resource_fields.append(_field("hewCanonicalUrl", _normalize_url(source.url, "url")))
        _record(mapped, "url", "hewResource.hewCanonicalUrl")
    if identifiers:
        resource_fields.append(
            _field(
                "hewAlternateIdentifier",
                [f"{agency}:{value}" for agency, value in _identifier_values(source)],
            )
        )
        _record(mapped, "doi/pmid/pmcid/identifiers", "hewResource.hewAlternateIdentifier")

    for field_name in sorted(set(record) - KNOWN_SOURCE_FIELDS):
        _record(unmapped, field_name, detail="not supported by publication-v1")
    if source.related_resources:
        resource_fields.append(_field("hewRelatedResource", source.related_resources))
        _record(mapped, "related_resources", "hewResource.hewRelatedResource")
    else:
        _record(omitted, "related_resources", "hewResource.hewRelatedResource", "empty")

    report = MappingReport(
        crosswalk_version=context.crosswalk_version,
        source_id=source.id,
        mapped=mapped,
        omitted=omitted,
        unmapped=unmapped,
    )
    return DataversePublicationProjection(
        source_id=source.id,
        crosswalk_version=context.crosswalk_version,
        metadata_blocks={
            "citation": DataverseMetadataBlock(
                displayName="Citation Metadata", fields=[field for field in citation_fields if field]
            ),
            "hewResource": DataverseMetadataBlock(
                displayName="HEW Resource Metadata", fields=resource_fields
            ),
        },
        report=report,
    )


def crosswalk_jsonld_publication(
    document: Mapping[str, Any] | str, context: CrosswalkContext
) -> DataversePublicationProjection:
    """Validate compact HEW JSON-LD and project it without replacing the source."""
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except json.JSONDecodeError as error:
            raise PublicationValidationError("invalid JSON-LD document") from error
    if not isinstance(document, Mapping):
        raise PublicationValidationError("JSON-LD publication must be an object")
    source = _normalized_jsonld_source(document, context)
    projection = crosswalk_publication(source, context)
    projection.source_jsonld = deepcopy(dict(document))
    return projection
