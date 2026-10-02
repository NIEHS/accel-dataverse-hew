from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from accelerator_dataverse_hew.crosswalks.publication.v1.models import (
    AuthorSource,
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
            properties = {
                key: _jsonld_value(item) for key, item in value.items() if not key.startswith("@")
            }
            # A bare node reference collapses to its IRI; an inlined node keeps its properties.
            if not properties:
                return value["@id"]
            return {"id": value["@id"], **properties}
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
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", re.IGNORECASE)

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
    "same_as",
    "themes",
    "spatial_coverage",
    "temporal_coverage",
    "access_rights",
    "license",
    "study_objective",
    "contacts",
    "contributors",
    "funding_sources",
    "derived_from_existing_dataset",
    "includes_geospatial_file",
    "contact_email",
    "contact_name",
    "subject",
    "source",
    "source_reference_number",
    "bibliographic",
    "review",
    "exposures",
    "health_impacts",
    "geography",
    "geographic_features",
    "data_and_models",
    "special_topics",
    "raw_values",
    "annotations",
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


def _validate_authors(record: Mapping[str, Any]) -> None:
    value = record.get("authors")
    if value is not None and (
        not isinstance(value, list)
        or any(not isinstance(item, (str, Mapping)) for item in value)
    ):
        raise PublicationValidationError("authors must be a list of strings or agent objects")


def validate_publication_source(record: Mapping[str, Any]) -> PublicationSource:
    """Validate the publication contract without discarding unknown HEW fields."""
    if not isinstance(record, Mapping):
        raise PublicationValidationError("publication must be a mapping")
    for field_name in ("id", "title", "resource_type"):
        if field_name not in record:
            raise PublicationValidationError(f"missing required field: {field_name}")
    if record["resource_type"] != "literature":
        raise PublicationValidationError("resource_type must be 'literature'")
    for field_name in ("identifiers", "keywords", "related_resources"):
        _validate_list(record, field_name)
    _validate_authors(record)
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


def _normalize_orcid(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"^https?://(www\.)?orcid\.org/", "", value.strip(), flags=re.I)
    normalized = re.sub(r"^orcid:\s*", "", normalized, flags=re.I).rstrip("/")
    return normalized.upper() if ORCID_PATTERN.fullmatch(normalized) else None


def _author_name(author: AuthorSource) -> str:
    if author.name:
        return author.name
    if author.family_name and author.given_name:
        return f"{author.family_name}, {author.given_name}"
    return author.family_name or author.given_name or author.id


def _author_values(source: PublicationSource) -> list[dict[str, Any]]:
    values = []
    for author in source.authors or []:
        if isinstance(author, str):
            if author.strip():
                values.append({"authorName": _field("authorName", author.strip())})
            continue
        value = {"authorName": _field("authorName", _author_name(author))}
        orcid = _normalize_orcid(author.orcid) or _normalize_orcid(author.id)
        if orcid:
            value["authorIdentifierScheme"] = _field(
                "authorIdentifierScheme", "ORCID", "controlledVocabulary"
            )
            value["authorIdentifier"] = _field("authorIdentifier", orcid)
        values.append(value)
    return values


def _description_values(source: PublicationSource) -> list[dict[str, Any]]:
    descriptions = []
    for value in (source.abstract, source.description):
        if value and value.strip():
            descriptions.append({"dsDescriptionValue": _field("dsDescriptionValue", value.strip())})
    if not descriptions:
        descriptions.append(
            {
                "dsDescriptionValue": _field(
                    "dsDescriptionValue", source.title
                )
            }
        )
    return descriptions


def _notes_text(source: PublicationSource) -> str | None:
    values = [value.strip() for value in (source.citation, source.journal) if value and value.strip()]
    return "; ".join(values) or None


def _cafe_boolean_value(source: PublicationSource, field_name: str) -> str:
    value = (source.model_extra or {}).get(field_name)
    if value is None:
        return "No"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and value.strip().lower() in {"yes", "true"}:
        return "Yes"
    if isinstance(value, str) and value.strip().lower() in {"no", "false"}:
        return "No"
    raise PublicationValidationError(f"{field_name} must be a boolean or yes/no value")


def _contact_values(source: PublicationSource) -> list[dict[str, Any]]:
    extra = source.model_extra or {}
    email = extra.get("contact_email")
    name = extra.get("contact_name") or "HEW Submitter"
    if not isinstance(email, str) or not email.strip():
        return []
    return [
        {
            "datasetContactName": _field("datasetContactName", str(name).strip()),
            "datasetContactEmail": _field("datasetContactEmail", email.strip()),
        }
    ]


def _subject_values(source: PublicationSource) -> list[str]:
    value = (source.model_extra or {}).get("subject")
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        values = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if values:
            return values
    return ["Other"]


def _status_label(status: str | None) -> str | None:
    if not status:
        return None
    return {"active": "Active", "draft": "Draft", "archived": "Archived"}.get(
        status.strip().lower()
    )


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _catalog_term_values(value: Any) -> list[str]:
    """Flatten HEW 2.0 catalog hierarchy entries without losing labels."""
    values = []
    for item in value or []:
        if isinstance(item, Mapping):
            for key in ("level1", "level2", "level3"):
                label = item.get(key)
                if isinstance(label, str) and label.strip():
                    values.append(label.strip())
        elif isinstance(item, str) and item.strip():
            values.append(item.strip())
    return list(dict.fromkeys(values))


def _annotation_list(source: PublicationSource) -> list[Mapping[str, Any]]:
    annotations = (source.model_extra or {}).get("annotations") or []
    return [annotation for annotation in annotations if isinstance(annotation, Mapping)]


def _annotation_concepts(
    annotations: list[Mapping[str, Any]], annotation_name: str, value_names: tuple[str, ...]
) -> list[str]:
    values = []
    for annotation in annotations:
        for item in annotation.get(annotation_name) or []:
            if isinstance(item, Mapping):
                for value_name in value_names:
                    value = item.get(value_name)
                    if isinstance(value, str) and value.strip():
                        values.append(value.strip())
                        break
            elif isinstance(item, str) and item.strip():
                values.append(item.strip())
    return list(dict.fromkeys(values))


def _annotation_field_values(
    annotations: list[Mapping[str, Any]], annotation_name: str, field_name: str
) -> list[str]:
    values = []
    for annotation in annotations:
        items = [annotation] if not annotation_name else annotation.get(annotation_name) or []
        for item in items:
            if isinstance(item, Mapping):
                value = item.get(field_name)
                if isinstance(value, list):
                    values.extend(str(item).strip() for item in value if str(item).strip())
                elif value not in (None, ""):
                    values.append(str(value).strip())
    return list(dict.fromkeys(values))


def _identifier_values_from_nodes(value: Any) -> list[str]:
    values = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        if isinstance(item, Mapping):
            item_value = item.get("id") or item.get("identifier")
            if item_value:
                values.append(str(item_value).strip())
        elif isinstance(item, str) and item.strip():
            values.append(item.strip())
    return list(dict.fromkeys(values))


def _annotation_node_identifiers(
    annotations: list[Mapping[str, Any]], *field_names: str
) -> list[str]:
    nodes = []
    for annotation in annotations:
        for field_name in field_names:
            value = annotation.get(field_name)
            if value not in (None, ""):
                nodes.extend(value if isinstance(value, list) else [value])
                break
    return _identifier_values_from_nodes(nodes)


def _annotation_detail_values(
    annotations: list[Mapping[str, Any]], annotation_name: str
) -> list[str]:
    values = []
    for annotation in annotations:
        for item in annotation.get(annotation_name) or []:
            if not isinstance(item, Mapping):
                continue
            concept = item.get("coded_concept") or item.get("exposure_concept") or item.get("health_impact_concept") or item.get("topic_concept")
            details = []
            for key in ("parent_concept", "specified_text", "coding_depth"):
                if item.get(key) not in (None, ""):
                    details.append(f"{key}={item[key]}")
            if concept and details:
                values.append(f"{concept} ({', '.join(details)})")
    return list(dict.fromkeys(values))


def _annotation_review_view(source: PublicationSource) -> dict[str, list[str] | str]:
    annotations = _annotation_list(source)
    exposures = _annotation_concepts(annotations, "exposure_annotations", ("coded_concept", "exposure_concept"))
    health_impacts = _annotation_concepts(annotations, "health_impact_annotations", ("coded_concept", "health_impact_concept"))
    special_topics = _annotation_concepts(annotations, "special_topic_annotations", ("coded_concept", "topic_concept"))
    geography = []
    features = []
    data_tools = []
    models = []
    for annotation in annotations:
        for item in annotation.get("geography_annotations") or []:
            if isinstance(item, Mapping):
                geography.extend(_string_values(item.get("geographic_locations")))
                features.extend(_string_values(item.get("geographic_features")))
        for item in annotation.get("data_tool_method_annotations") or []:
            if isinstance(item, Mapping):
                data_tools.extend(_string_values(item.get("data_resource_types")))
                models.extend(_string_values(item.get("model_types")))
    view: dict[str, list[str] | str] = {
        "exposures": list(dict.fromkeys(exposures)),
        "health_impacts": list(dict.fromkeys(health_impacts)),
        "geography": list(dict.fromkeys(geography)),
        "geographic_features": list(dict.fromkeys(features)),
        "data_tools": list(dict.fromkeys(data_tools)),
        "models": list(dict.fromkeys(models)),
        "special_topics": list(dict.fromkeys(special_topics)),
    }
    for annotation in annotations:
        for field_name in ("coding_scheme", "coding_method", "information_source", "reference_type"):
            value = annotation.get(field_name)
            if isinstance(value, str) and value.strip() and field_name not in view:
                view[field_name] = value.strip()
    return view


def _catalog_record_to_publication(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Adapt a HEW Catalog Data Model 2.0 export into the publication view."""
    if isinstance(record.get("data"), Mapping):
        record = record["data"]
    if not isinstance(record.get("bibliographic"), Mapping):
        return None
    bibliographic = record["bibliographic"]
    source_name = str(record.get("source") or "hew").strip()
    reference_number = str(record.get("source_reference_number") or "").strip()
    if not reference_number or not bibliographic.get("title"):
        return None

    publication: dict[str, Any] = {
        "id": f"HEWRES:{source_name}:{reference_number}",
        "title": bibliographic["title"],
        "resource_type": "literature",
        "doi": bibliographic.get("doi"),
        "identifiers": [
            str(value) for value in [
                bibliographic.get("accession_number"),
                *(bibliographic.get("study_identifiers") or []),
            ] if value not in (None, "")
        ],
        "authors": ([bibliographic["first_author"]]
                    if bibliographic.get("first_author") else []),
        "publication_date": str(bibliographic["year"])
        if bibliographic.get("year") is not None else None,
        "source": source_name,
        "source_reference_number": reference_number,
        "bibliographic": bibliographic,
        "review": record.get("review") or {},
        "exposures": record.get("exposures") or [],
        "health_impacts": record.get("health_impacts") or [],
        "geography": record.get("geography") or [],
        "geographic_features": record.get("geographic_features") or [],
        "data_and_models": record.get("data_and_models") or {},
        "special_topics": record.get("special_topics") or {},
        "raw_values": record.get("raw_values") or {},
    }
    return {key: value for key, value in publication.items() if value not in (None, [], {})}


def _catalog_review_fields(source: PublicationSource) -> list[DataverseField]:
    extra = source.model_extra or {}
    review = extra.get("review") or {}
    if not (
        review
        or extra.get("annotations")
        or extra.get("exposures")
        or extra.get("health_impacts")
        or extra.get("geography")
        or extra.get("data_and_models")
        or extra.get("special_topics")
    ):
        return []
    annotation_view = _annotation_review_view(source)
    exposures = _catalog_term_values(extra.get("exposures")) or annotation_view["exposures"]
    health_impacts = _catalog_term_values(extra.get("health_impacts")) or annotation_view["health_impacts"]
    geography = _catalog_term_values(extra.get("geography")) or annotation_view["geography"]
    data_and_models = extra.get("data_and_models") or {}
    levels = data_and_models.get("levels") if isinstance(data_and_models, Mapping) else {}
    data_tools = _catalog_term_values((levels or {}).get("1")) + _catalog_term_values((levels or {}).get("2"))
    models = _string_values(data_and_models.get("model_types")) if isinstance(data_and_models, Mapping) else []
    data_tools = data_tools or annotation_view["data_tools"]
    models = models or annotation_view["models"]
    special_topics = extra.get("special_topics") or {}
    special_levels = special_topics.get("levels") if isinstance(special_topics, Mapping) else {}
    special = _string_values((special_levels or {}).get("1")) + _string_values((special_levels or {}).get("2"))
    special = special or annotation_view["special_topics"]
    fields = []

    def add(name: str, value: Any, type_class: str = "primitive") -> None:
        values = _string_values(value)
        if values:
            fields.append(_field(name, values, type_class) if len(values) > 1 else _field(name, values[0], type_class))

    add("hewCodingScheme", review.get("coding_scheme") or annotation_view.get("coding_scheme") or extra.get("source"))
    add("hewCodingSchemeVersion", "2.0.0")
    coding_method = review.get("coding_method") or annotation_view.get("coding_method")
    coding_method = "Automated" if coding_method in {"automated", "laser_ai_generated"} else coding_method
    information_source = review.get("information_source") or annotation_view.get("information_source")
    information_source = "Complete resource" if information_source == "complete_resource" else information_source
    add("hewCodingMethod", coding_method or "Automated", "controlledVocabulary")
    add("hewInformationSource", information_source, "controlledVocabulary")
    add("hewReferenceType", review.get("reference_type") or annotation_view.get("reference_type"))
    add("hewRecommendForRemoval", review.get("recommend_for_removal"))
    add("hewPostpone", review.get("postpone"))
    add("hewExposureAnnotation", exposures)
    add("hewHealthImpactAnnotation", health_impacts)
    add("hewGeographyAnnotation", geography)
    add("hewDataToolMethodAnnotation", data_tools + models)
    add("hewSpecialTopicAnnotation", special)
    annotations = _annotation_list(source)
    add("hewAnnotationDate", _annotation_field_values(annotations, "", "annotation_date"))
    add("hewCoderIdentifier", _annotation_node_identifiers(annotations, "coded_by", "generated_by"))
    add("hewReviewerIdentifier", _annotation_node_identifiers(annotations, "reviewed_by"))
    add("hewEvidenceText", [
        value for annotation_name in (
            "exposure_annotations", "health_impact_annotations", "geography_annotations",
            "data_tool_method_annotations", "special_topic_annotations",
        ) for value in _annotation_field_values(annotations, annotation_name, "evidence_text")
    ])
    add("hewAnnotationNotes", [
        *(_string_values(review.get("notes"))),
        *_annotation_detail_values(annotations, "exposure_annotations"),
        *_annotation_detail_values(annotations, "health_impact_annotations"),
        *_annotation_detail_values(annotations, "special_topic_annotations"),
    ])
    confidence_values = [
        value for annotation in annotations
        for value in [annotation.get("confidence")]
        if value not in (None, "")
    ]
    add("hewConfidence", confidence_values)
    needs_review = [
        "Yes" if annotation.get("needs_human_review") else "No"
        for annotation in annotations
        if "needs_human_review" in annotation
    ]
    add("hewNeedsHumanReview", needs_review, "controlledVocabulary")
    removal = review.get("recommend_for_removal")
    postpone = review.get("postpone")
    add("hewAnnotationNotes", [f"recommend_for_removal: {removal}", f"postpone: {postpone}"] if removal or postpone else [])
    return fields


def _record(report: list[MappingEntry], source: str, target: str | None = None, detail: str | None = None):
    report.append(MappingEntry(source=source, target=target, detail=detail))


def crosswalk_publication(
    record: Mapping[str, Any], context: CrosswalkContext
) -> DataversePublicationProjection:
    """Project a validated HEW literature resource into Dataverse metadata."""
    source = validate_publication_source(_catalog_record_to_publication(record) or record)
    mapped: list[MappingEntry] = []
    omitted: list[MappingEntry] = []
    unmapped: list[MappingEntry] = []

    contact_values = _contact_values(source)
    citation_fields = [
        _field("title", source.title),
        _field("subject", _subject_values(source), "controlledVocabulary"),
        _compound_field("datasetContact", contact_values) if contact_values else None,
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
        citation_fields.append(_field("productionDate", source.publication_date))
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
    for source_name, target_name in (
        ("description", "hewResourceDescription"),
        ("spatial_coverage", "hewSpatialCoverage"),
        ("temporal_coverage", "hewTemporalCoverage"),
        ("access_rights", "hewAccessRights"),
        ("license", "hewLicense"),
        ("study_objective", "hewStudyObjective"),
    ):
        value = getattr(source, source_name)
        if value:
            resource_fields.append(_field(target_name, value))
            _record(mapped, source_name, f"hewResource.{target_name}")
        else:
            _record(omitted, source_name, f"hewResource.{target_name}", "empty")
    if identifiers:
        resource_fields.append(
            _field(
                "hewAlternateIdentifier",
                [f"{agency}:{value}" for agency, value in _identifier_values(source)],
            )
        )
        _record(mapped, "doi/pmid/pmcid/identifiers", "hewResource.hewAlternateIdentifier")

    annotation_view = _annotation_review_view(source)
    catalog_exposure_values = _catalog_term_values((source.model_extra or {}).get("exposures")) or annotation_view["exposures"]
    catalog_health_values = _catalog_term_values((source.model_extra or {}).get("health_impacts")) or annotation_view["health_impacts"]
    catalog_geography_values = _catalog_term_values((source.model_extra or {}).get("geography")) or annotation_view["geography"]
    catalog_feature_values = _string_values((source.model_extra or {}).get("geographic_features")) or annotation_view["geographic_features"]
    catalog_topic_values = _catalog_term_values((source.model_extra or {}).get("special_topics", {}).get("levels", {}).get("1", []))
    catalog_topic_values += _catalog_term_values((source.model_extra or {}).get("special_topics", {}).get("levels", {}).get("2", []))
    catalog_topic_values = catalog_topic_values or annotation_view["special_topics"]
    for target_name, values in (
        ("hewExposureConcept", catalog_exposure_values),
        ("hewHealthImpactConcept", catalog_health_values),
        ("hewGeographyConcept", catalog_geography_values),
        ("hewGeographicFeature", catalog_feature_values),
        ("hewTopicConcept", catalog_topic_values),
    ):
        if values:
            resource_fields.append(_field(target_name, values))
            _record(mapped, target_name, f"hewResource.{target_name}")

    for field_name in sorted(set(record) - KNOWN_SOURCE_FIELDS):
        _record(unmapped, field_name, detail="not supported by publication-v1")
    if _annotation_list(source):
        _record(mapped, "annotations", "hewReview")
    if source.related_resources:
        resource_fields.append(_field("hewRelatedResource", source.related_resources))
        _record(mapped, "related_resources", "hewResource.hewRelatedResource")
    else:
        _record(omitted, "related_resources", "hewResource.hewRelatedResource", "empty")

    for source_name, target_name in (
        ("same_as", "hewSameAs"),
        ("themes", "hewTheme"),
        ("contacts", "hewContact"),
        ("contributors", "hewContributor"),
        ("funding_sources", "hewFundingSource"),
    ):
        values = _string_values(getattr(source, source_name))
        if values:
            resource_fields.append(_field(target_name, values))
            _record(mapped, source_name, f"hewResource.{target_name}")
        else:
            _record(omitted, source_name, f"hewResource.{target_name}", "empty")

    cafe_source_fields = [
        _field(
            "cafeDerivedFromExistingDataset",
            _cafe_boolean_value(source, "derived_from_existing_dataset"),
            "controlledVocabulary",
        )
    ]
    cafe_location_fields = [
        _field(
            "cafeIncludesGeospatialFile",
            _cafe_boolean_value(source, "includes_geospatial_file"),
            "controlledVocabulary",
        )
    ]
    _record(mapped, "derived_from_existing_dataset", "customCAFEDataSources.cafeDerivedFromExistingDataset")
    _record(mapped, "includes_geospatial_file", "customCAFEDataLocation.cafeIncludesGeospatialFile")

    review_fields = _catalog_review_fields(source)
    if review_fields:
        _record(mapped, "review/exposures/health_impacts/geography/data_and_models/special_topics", "hewReview")

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
            "customCAFEDataSources": DataverseMetadataBlock(
                displayName="Metadata About Data Sources", fields=cafe_source_fields
            ),
            "customCAFEDataLocation": DataverseMetadataBlock(
                displayName="Metadata About Geospatial Files", fields=cafe_location_fields
            ),
            **({
                "hewReview": DataverseMetadataBlock(
                    displayName="HEW Review Coding", fields=review_fields
                )
            } if review_fields else {}),
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
    catalog_source = _catalog_record_to_publication(document)
    source_document = document.get("data") if isinstance(document.get("data"), Mapping) else document
    source = catalog_source or _normalized_jsonld_source(source_document, context)
    projection = crosswalk_publication(source, context)
    projection.source_jsonld = deepcopy(dict(document))
    return projection
