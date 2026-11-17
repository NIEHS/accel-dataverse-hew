from __future__ import annotations

import json
import re
import math
from datetime import datetime
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from accelerator_dataverse_hew.crosswalks.discovery import cafe_terms, discovery_values

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
                key: _jsonld_value(item)
                for key, item in value.items()
                if not key.startswith("@")
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
            raise PublicationValidationError(
                "JSON-LD @type must identify one resource class"
            )
        value = value[0]
    if not isinstance(value, str):
        raise PublicationValidationError("JSON-LD @type must be a string")
    return value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _normalized_jsonld_source(
    document: Mapping[str, Any], context: CrosswalkContext
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise PublicationValidationError("JSON-LD publication must be an object")
    if "@context" not in document or not _context_contains_hew(document["@context"]):
        raise PublicationValidationError(
            "JSON-LD document is missing a supported HEW @context"
        )
    if "@type" in document:
        type_name = _jsonld_type_name(document["@type"])
        if type_name not in {"HEWResource", "LiteratureResource"}:
            raise PublicationValidationError(
                f"unsupported HEW JSON-LD @type: {type_name}"
            )

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
    if (
        source.get("hew_schema_version")
        and source["hew_schema_version"] != context.hew_schema_version
    ):
        raise PublicationValidationError(
            "JSON-LD HEW schema version does not match crosswalk context"
        )
    return source


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
PMID_PATTERN = re.compile(r"^\d+$")
PMCID_PATTERN = re.compile(r"^PMC\d+$", re.IGNORECASE)
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", re.IGNORECASE)

REFERENCE_DETAIL_FIELDS = {
    "adapted_from_details",
    "affiliations_details",
    "authors_details",
    "collection_members_details",
    "contacts_details",
    "contributors_details",
    "curator_details",
    "funder_details",
    "funding_sources_details",
    "generated_by_details",
    "maintainers_details",
    "measurement_method_details",
    "parent_organization_details",
    "part_of_programs_details",
    "part_of_project_details",
    "population_or_cohort_details",
    "produces_resources_details",
    "related_resources_details",
    "research_program_details",
    "software_details",
    "source_dataset_details",
    "source_organization_details",
    "source_project_details",
    "source_variables_details",
    "sponsoring_organizations_details",
    "uses_resources_details",
}

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
    "spatial_extent",
    "temporal_extent",
    "temporal_support",
}

KNOWN_SOURCE_FIELDS.update(REFERENCE_DETAIL_FIELDS)
KNOWN_SOURCE_FIELDS.add("processing_methods")


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
    normalized = re.sub(
        r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/", "", normalized, flags=re.I
    )
    normalized = re.sub(r"^pmid:\s*", "", normalized, flags=re.I).rstrip("/")
    if not PMID_PATTERN.fullmatch(normalized):
        raise PublicationValidationError(f"invalid PMID: {value}")
    return normalized


def _normalize_pmcid(value: str) -> str:
    normalized = value.strip()
    normalized = re.sub(
        r"^https?://pmc\.ncbi\.nlm\.nih\.gov/articles/", "", normalized, flags=re.I
    )
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
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


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
        raise PublicationValidationError(
            "authors must be a list of strings or agent objects"
        )


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


def _author_name(author: AuthorSource) -> str | None:
    if author.name:
        return author.name
    if author.family_name and author.given_name:
        return f"{author.family_name}, {author.given_name}"
    return author.family_name or author.given_name


def _author_values(source: PublicationSource) -> list[dict[str, Any]]:
    values = []
    for author in source.authors or []:
        if isinstance(author, str):
            if author.strip() and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", author):
                values.append({"authorName": _field("authorName", author.strip())})
            continue
        name = _author_name(author)
        if not name:
            continue
        value = {"authorName": _field("authorName", name)}
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
            descriptions.append(
                {"dsDescriptionValue": _field("dsDescriptionValue", value.strip())}
            )
    if not descriptions:
        descriptions.append(
            {"dsDescriptionValue": _field("dsDescriptionValue", source.title)}
        )
    return descriptions


def _notes_text(source: PublicationSource) -> str | None:
    values = [
        value.strip()
        for value in (source.citation, source.journal)
        if value and value.strip()
    ]
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
        values = [
            item.strip() for item in value if isinstance(item, str) and item.strip()
        ]
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
        return [
            item.strip() for item in value if isinstance(item, str) and item.strip()
        ]
    return []


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
            str(value)
            for value in [
                bibliographic.get("accession_number"),
                *(bibliographic.get("study_identifiers") or []),
            ]
            if value not in (None, "")
        ],
        "authors": (
            [bibliographic["first_author"]] if bibliographic.get("first_author") else []
        ),
        "publication_date": (
            str(bibliographic["year"])
            if bibliographic.get("year") is not None
            else None
        ),
        "source": source_name,
        "source_reference_number": reference_number,
        "bibliographic": bibliographic,
        "review": record.get("review") or {},
        "annotations": record.get("annotations") or [],
        "exposures": record.get("exposures") or [],
        "health_impacts": record.get("health_impacts") or [],
        "geography": record.get("geography") or [],
        "geographic_features": record.get("geographic_features") or [],
        "data_and_models": record.get("data_and_models") or {},
        "special_topics": record.get("special_topics") or {},
        "raw_values": record.get("raw_values") or {},
    }
    for name in (
        "description",
        "abstract",
        "study_objective",
        "spatial_coverage",
        "spatial_extent",
        "temporal_coverage",
        "temporal_extent",
        "temporal_support",
        "themes",
    ):
        if record.get(name) is not None:
            publication[name] = record[name]
    return {
        key: value for key, value in publication.items() if value not in (None, [], {})
    }


def _record(
    report: list[MappingEntry],
    source: str,
    target: str | None = None,
    detail: str | None = None,
):
    report.append(MappingEntry(source=source, target=target, detail=detail))


def _coverage_blocks(source: PublicationSource) -> dict[str, DataverseMetadataBlock]:
    extra = source.model_extra or {}
    spatial = extra.get("spatial_extent") or {}
    temporal = extra.get("temporal_extent") or {}
    temporal_support = extra.get("temporal_support") or {}
    if (
        not isinstance(spatial, Mapping)
        or not isinstance(temporal, Mapping)
        or not isinstance(temporal_support, Mapping)
    ):
        raise PublicationValidationError(
            "spatial_extent, temporal_extent, and temporal_support must be objects"
        )
    blocks = {}
    geographic_fields = []
    spatial_fields = []
    temporal_fields = []
    cafe_location_fields = []
    if source.spatial_coverage:
        spatial_fields.append(_field("hewSpatialCoverage", source.spatial_coverage))
    if source.temporal_coverage:
        temporal_fields.append(_field("hewTemporalCoverage", source.temporal_coverage))
    bounds = spatial.get("bounding_box")
    if bounds:
        if not isinstance(bounds, Mapping):
            raise PublicationValidationError("bounding_box must be an object")
        try:
            coordinates = {
                key: float(bounds[key]) for key in ("west", "east", "north", "south")
            }
        except (ValueError, TypeError, KeyError) as error:
            raise PublicationValidationError(
                "bounding_box requires numeric west/east/north/south"
            ) from error
        if not all(math.isfinite(value) for value in coordinates.values()) or not (
            -180 <= coordinates["west"] <= coordinates["east"] <= 180
            and -90 <= coordinates["south"] <= coordinates["north"] <= 90
        ):
            raise PublicationValidationError(
                "bounding_box has invalid coordinate ranges or ordering"
            )
        geographic_fields.append(
            _compound_field(
                "geographicBoundingBox",
                [
                    {
                        name: _field(name, str(coordinates[key]))
                        for key, name in (
                            ("west", "westLongitude"),
                            ("east", "eastLongitude"),
                            ("north", "northLatitude"),
                            ("south", "southLatitude"),
                        )
                    }
                ],
            )
        )
    locations = spatial.get("named_locations") or []
    names = [
        item.get("name")
        for item in locations
        if isinstance(item, Mapping) and item.get("name")
    ]
    if names or source.spatial_coverage:
        geographic_fields.append(
            _compound_field(
                "geographicCoverage",
                [
                    {"otherGeographicCoverage": _field("otherGeographicCoverage", name)}
                    for name in names or [source.spatial_coverage]
                ],
            )
        )
    if names:
        spatial_fields.append(_field("hewNamedLocation", names))
    location_ids = [
        item.get("location_id")
        for item in locations
        if isinstance(item, Mapping) and item.get("location_id")
    ]
    if location_ids:
        spatial_fields.append(_field("hewLocationIdentifier", location_ids))
    geometry = spatial.get("geometry") or {}
    centroid = spatial.get("centroid") or {}
    for key, target, limit in (
        ("latitude", "hewCentroidLatitude", 90),
        ("longitude", "hewCentroidLongitude", 180),
    ):
        if centroid.get(key) is not None:
            try:
                coordinate = float(centroid[key])
            except (ValueError, TypeError) as error:
                raise PublicationValidationError(
                    f"centroid {key} must be numeric"
                ) from error
            if not math.isfinite(coordinate) or not -limit <= coordinate <= limit:
                raise PublicationValidationError(f"centroid {key} is out of range")
            spatial_fields.append(_field(target, coordinate))
    context = spatial.get("environmental_context") or []
    if context:
        context_values, _ = discovery_values({"themes": context})
        if context_values.get("hewTopicConcept"):
            spatial_fields.append(
                _field("hewEnvironmentalContext", context_values["hewTopicConcept"])
            )
        if context_values.get("hewTopicCurie"):
            spatial_fields.append(
                _field("hewEnvironmentalContextCurie", context_values["hewTopicCurie"])
            )
    crs = spatial.get("coordinate_reference_system_uri") or geometry.get(
        "coordinate_reference_system_uri"
    )
    if crs:
        crs_fields = {
            "cafeSpatialReferenceSystemName": _field(
                "cafeSpatialReferenceSystemName", crs
            )
        }
        if isinstance(crs, str) and crs.startswith(("http://", "https://")):
            crs_fields["cafeSpatialReferenceSystemURL"] = _field(
                "cafeSpatialReferenceSystemURL", crs
            )
        cafe_location_fields.append(
            _field("cafeSpatialReferenceSystem", crs_fields, "compound")
        )
    for key, target in (
        ("geometry_type", "hewGeometryType"),
        ("wkt", "hewGeometryWkt"),
        ("geojson", "hewGeometryGeoJson"),
    ):
        value = geometry.get(key)
        if value:
            spatial_fields.append(
                _field(
                    target,
                    [
                        (
                            json.dumps(value, sort_keys=True)
                            if isinstance(value, Mapping)
                            else value
                        )
                    ],
                )
            )
    # Publish compact discovery summaries, leaving full support and grids in source.
    support = extra.get("spatial_support") or {}
    if not isinstance(support, Mapping):
        raise PublicationValidationError("spatial_support must be an object")
    resolutions = []
    for value in (
        spatial.get("spatial_resolution"),
        extra.get("spatial_resolution"),
        support.get("spatial_resolution"),
    ):
        if isinstance(value, str) and value.strip():
            resolutions.append(value.strip())
    for owner in (spatial, extra, support):
        quantitative = owner.get("quantitative_spatial_resolution") or {}
        administrative = owner.get("administrative_spatial_resolution") or {}
        if (
            isinstance(quantitative, Mapping)
            and quantitative.get("resolution_value") is not None
        ):
            value = quantitative["resolution_value"]
            unit = quantitative.get("resolution_unit") or ""
            axis = quantitative.get("resolution_axis")
            summary = f"{value} {unit}".strip()
            if axis and axis != "nominal":
                summary += f" ({axis})"
            resolutions.append(summary)
        if isinstance(administrative, Mapping) and administrative.get(
            "administrative_level"
        ):
            resolutions.append(str(administrative["administrative_level"]))
    if resolutions:
        spatial_fields.append(
            _field("hewSpatialResolution", list(dict.fromkeys(resolutions)))
        )
    if support.get("support_type"):
        spatial_fields.append(
            _field("hewSpatialSupportType", [support["support_type"]])
        )
    temporal_children = {}
    timestamps = {}
    for key, target in (
        ("start_time", "hewTemporalStart"),
        ("end_time", "hewTemporalEnd"),
        ("timezone", "hewTemporalTimezone"),
        ("coverage_status", "hewTemporalCoverageStatus"),
    ):
        if temporal.get(key) is not None:
            value = temporal[key]
            if key in ("start_time", "end_time"):
                try:
                    timestamps[key] = datetime.fromisoformat(
                        value.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError, AttributeError) as error:
                    raise PublicationValidationError(
                        f"{key} must be an ISO 8601 datetime"
                    ) from error
                if timestamps[key].utcoffset() is None:
                    raise PublicationValidationError(f"{key} must include a UTC offset")
            temporal_children[target] = _field(target, value)
    if len(timestamps) == 2 and timestamps["start_time"] >= timestamps["end_time"]:
        raise PublicationValidationError(
            "temporal_extent start_time must precede end_time"
        )
    if temporal_children:
        temporal_fields.append(
            _compound_field("hewTemporalExtent", [temporal_children])
        )
    support_values = dict(temporal_support)
    # Older HEW exports placed these support properties on temporal_extent.
    # Preserve them, but serialize them under the separate support compound.
    for key in ("temporal_resolution", "calendar"):
        if key not in support_values and temporal.get(key) is not None:
            support_values[key] = temporal[key]
    support_children = {}
    for key, target in (
        ("temporal_resolution", "hewTemporalResolution"),
        ("calendar", "hewTemporalCalendar"),
        ("temporal_alignment", "hewTemporalAlignment"),
        ("day_boundary_convention", "hewDayBoundaryConvention"),
        ("aggregation_window", "hewAggregationWindow"),
        ("timezone", "hewDatasetTemporalTimezone"),
    ):
        if support_values.get(key) is not None:
            support_children[target] = _field(target, support_values[key])
    if support_children:
        temporal_fields.append(
            _field("hewDatasetTemporalSupport", support_children, "compound")
        )
    for name, title, fields in (
        ("geospatial", "Geospatial Metadata", geographic_fields),
        ("hewGeospatial", "HEW Geospatial", spatial_fields),
        ("hewTemporal", "HEW Temporal", temporal_fields),
        (
            "customCAFEDataLocation",
            "Metadata About Geospatial Files",
            cafe_location_fields,
        ),
    ):
        if fields:
            blocks[name] = DataverseMetadataBlock(displayName=title, fields=fields)
    return blocks


def crosswalk_publication(
    record: Mapping[str, Any], context: CrosswalkContext
) -> DataversePublicationProjection:
    """Project a validated HEW literature resource into Dataverse metadata."""
    source = validate_publication_source(
        _catalog_record_to_publication(record) or record
    )
    for key in REFERENCE_DETAIL_FIELDS:
        value = (source.model_extra or {}).get(key)
        if value is None:
            continue
        entries = value if isinstance(value, list) else [value]
        for entry in entries:
            if not isinstance(entry, dict):
                raise PublicationValidationError(
                    f"{key} must contain reference objects"
                )
        if key in {
            "authors_details",
            "contacts_details",
            "contributors_details",
            "funding_sources_details",
        } and not isinstance(value, list):
            raise PublicationValidationError(
                f"{key} must be a list of reference objects"
            )
    mapped: list[MappingEntry] = []
    omitted: list[MappingEntry] = []
    unmapped: list[MappingEntry] = []

    contact_values = _contact_values(source)
    citation_fields = [
        _field("title", source.title),
        _field("subject", _subject_values(source), "controlledVocabulary"),
        _compound_field("datasetContact", contact_values) if contact_values else None,
        (
            _field("alternativeURL", _normalize_url(source.url, "url"))
            if source.url
            else None
        ),
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
                [
                    {"keywordValue": _field("keywordValue", keyword)}
                    for keyword in dict.fromkeys(keywords)
                ],
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
    ]
    _record(mapped, "id", "hewResource.hewResourceId")
    if source.status:
        resource_fields.append(
            _field("hewResourceStatus", _status_label(source.status) or source.status)
        )
        _record(mapped, "status", "hewResource.hewResourceStatus")
    if source.related_resources:
        resource_fields.append(_field("hewRelatedResource", source.related_resources))
        _record(mapped, "related_resources", "hewResource.hewRelatedResource")
    if source.same_as:
        identifiers.extend(
            {
                "otherIdAgency": _field("otherIdAgency", "same_as"),
                "otherIdValue": _field("otherIdValue", value),
            }
            for value in source.same_as
        )
        if not any(field and field.type_name == "otherId" for field in citation_fields):
            citation_fields.append(_compound_field("otherId", identifiers))
        _record(mapped, "same_as", "citation.otherId")
    # Identifier-only relations remain in HEW fields. Citation fields receive
    # explicit names and award numbers only; unresolved IDs are never labels.
    for source_name, compound, child in (
        ("contacts_details", "datasetContact", "datasetContactName"),
        ("contributors_details", "contributor", "contributorName"),
        ("funding_sources_details", "grantNumber", "grantNumberValue"),
    ):
        entries = (source.model_extra or {}).get(source_name) or []
        projected_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise PublicationValidationError(
                    f"{source_name} entries must be objects"
                )
            key = "award_number" if source_name == "funding_sources_details" else "name"
            value = _optional_text(entry.get(key), f"{source_name}.{key}")
            if not value:
                continue
            children = {child: _field(child, value)}
            if source_name == "contacts_details":
                email = _optional_text(entry.get("email"), "contacts_details.email")
                # Dataverse citation contacts require both a name and email.
                if not email:
                    continue
                children["datasetContactEmail"] = _field("datasetContactEmail", email)
            if source_name == "funding_sources_details" and entry.get("funder_name"):
                children["grantNumberAgency"] = _field(
                    "grantNumberAgency", entry["funder_name"]
                )
            projected_entries.append(children)
        if projected_entries:
            existing = next(
                (
                    field
                    for field in citation_fields
                    if field and field.type_name == compound
                ),
                None,
            )
            if existing:
                existing.value.extend(projected_entries)
            else:
                citation_fields.append(_compound_field(compound, projected_entries))
            _record(mapped, source_name, f"citation.{compound}")
    author_details = (source.model_extra or {}).get("authors_details") or []
    if author_details:
        entries = [
            {"authorName": _field("authorName", entry["name"])}
            for entry in author_details
            if entry.get("name")
        ]
        if entries:
            existing = next(
                (f for f in citation_fields if f and f.type_name == "author"), None
            )
            if existing:
                existing.value.extend(entries)
            else:
                citation_fields.append(_compound_field("author", entries))
            _record(mapped, "authors_details.name", "citation.author")

    publication_fields = (
        [_field("hewStudyObjective", source.study_objective)]
        if source.study_objective
        else []
    )
    if publication_fields:
        _record(mapped, "study_objective", "hewPublication.hewStudyObjective")
    discovery, unresolved = discovery_values(
        source.model_dump(mode="json", exclude_none=True)
    )
    discovery_fields = [
        _field(name, value) for name, value in discovery.items() if value
    ]
    for name in discovery:
        _record(
            mapped,
            "resource_type/themes/annotations/catalog concepts",
            f"hewDiscovery.{name}",
        )
    for identifier in unresolved:
        _record(
            unmapped,
            "concept label",
            detail=f"No plain-text label for {identifier}; retained in CURIE field",
        )
    for field_name in sorted(set(record) - KNOWN_SOURCE_FIELDS):
        _record(unmapped, field_name, detail="not supported by publication-v1")
    for field_name in ("license", "access_rights"):
        if getattr(source, field_name):
            _record(
                unmapped,
                field_name,
                detail="Requires dataset terms/access configuration; preserved in source",
            )

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
    _record(
        mapped,
        "derived_from_existing_dataset",
        "customCAFEDataSources.cafeDerivedFromExistingDataset",
    )
    _record(
        mapped,
        "includes_geospatial_file",
        "customCAFEDataLocation.cafeIncludesGeospatialFile",
    )

    cafe_vocabulary = {value.casefold(): value for value in cafe_terms()}
    matched_terms = sorted(
        {
            cafe_vocabulary[value.casefold()]
            for name, entries in discovery.items()
            if name.endswith(("Concept", "Label"))
            for value in (entries if isinstance(entries, list) else [entries])
            if value.casefold() in cafe_vocabulary
        }
    )
    coverage_blocks = _coverage_blocks(source)
    location_coverage = coverage_blocks.pop("customCAFEDataLocation", None)
    if location_coverage:
        cafe_location_fields.extend(location_coverage.fields)
        _record(
            mapped,
            "spatial_extent.coordinate_reference_system_uri",
            "customCAFEDataLocation.cafeSpatialReferenceSystem",
        )
    for name in coverage_blocks:
        _record(
            mapped,
            "spatial_extent/temporal_extent/spatial_coverage/temporal_coverage",
            name,
        )
    if matched_terms:
        coverage_blocks["AdditionalMetadataAboutDataset"] = DataverseMetadataBlock(
            displayName="Additional Metadata About Dataset",
            fields=[_field("cafeDatasetTerms", matched_terms, "controlledVocabulary")],
        )
        _record(
            mapped,
            "discovery labels",
            "AdditionalMetadataAboutDataset.cafeDatasetTerms",
        )

    processing_entries = []
    methods = (source.model_extra or {}).get("processing_methods") or []
    if not isinstance(methods, list):
        raise PublicationValidationError("processing_methods must be a list")
    for method in methods:
        if not isinstance(method, dict):
            raise PublicationValidationError(
                "processing_methods entries must be objects"
            )
        children = {}
        allowed = {
            "name",
            "description",
            "software",
            "software_details",
            "software_version",
            "provenance_reference",
            "provenance_reference_details",
        }
        if set(method) - allowed:
            raise PublicationValidationError(
                "processing_methods accepts descriptive metadata only; store execution settings in external provenance"
            )
        for key, target in (
            ("name", "hewMethodName"),
            ("description", "hewMethodDescription"),
            ("software_version", "hewMethodSoftwareVersion"),
        ):
            value = _optional_text(method.get(key), f"processing_methods.{key}")
            if value:
                children[target] = _field(target, value)
        for key, prefix in (
            ("software", "hewMethodSoftware"),
            ("provenance_reference", "hewMethodProvenance"),
        ):
            details = method.get(key + "_details") or {}
            if not isinstance(details, dict):
                raise PublicationValidationError(f"{key}_details must be an object")
            identifier = _optional_text(method.get(key), key)
            detail_id = _optional_text(
                details.get("reference_id"), key + "_details.reference_id"
            )
            if identifier and detail_id and identifier != detail_id:
                raise PublicationValidationError(f"conflicting identifiers for {key}")
            for suffix, value in (
                ("Identifier", identifier or detail_id),
                ("Name", details.get("name")),
                ("Description", details.get("description")),
            ):
                value = _optional_text(value, prefix + suffix)
                if value:
                    children[prefix + suffix] = _field(prefix + suffix, value)
        if children:
            processing_entries.append(children)
    if processing_entries:
        coverage_blocks["hewCalculation"] = DataverseMetadataBlock(
            displayName="HEW Processing Methods",
            fields=[_compound_field("hewProcessingMethod", processing_entries)],
        )
        _record(mapped, "processing_methods", "hewCalculation.hewProcessingMethod")

    report = MappingReport(
        crosswalk_version=context.crosswalk_version,
        processing_context=context,
        source_id=source.id,
        mapped=mapped,
        omitted=omitted,
        unmapped=unmapped,
    )
    return DataversePublicationProjection(
        source_id=source.id,
        crosswalk_version=context.crosswalk_version,
        metadata_blocks={
            **coverage_blocks,
            "citation": DataverseMetadataBlock(
                displayName="Citation Metadata",
                fields=[field for field in citation_fields if field],
            ),
            "hewResource": DataverseMetadataBlock(
                displayName="HEW Catalog Record", fields=resource_fields
            ),
            "hewDiscovery": DataverseMetadataBlock(
                displayName="HEW Discovery", fields=discovery_fields
            ),
            **(
                {
                    "hewPublication": DataverseMetadataBlock(
                        displayName="HEW Publication", fields=publication_fields
                    )
                }
                if publication_fields
                else {}
            ),
            "customCAFEDataSources": DataverseMetadataBlock(
                displayName="Metadata About Data Sources", fields=cafe_source_fields
            ),
            "customCAFEDataLocation": DataverseMetadataBlock(
                displayName="Metadata About Geospatial Files",
                fields=cafe_location_fields,
            ),
        },
        report=report,
    )


def crosswalk_jsonld_publication(
    document: Mapping[str, Any] | str, context: CrosswalkContext
) -> DataversePublicationProjection:
    """Validate and project HEW JSON-LD while preserving the source unchanged."""
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except json.JSONDecodeError as error:
            raise PublicationValidationError("invalid JSON-LD document") from error
    if not isinstance(document, Mapping):
        raise PublicationValidationError("JSON-LD publication must be an object")
    source_jsonld = deepcopy(dict(document))
    source_document = (
        source_jsonld.get("data")
        if isinstance(source_jsonld.get("data"), Mapping)
        else source_jsonld
    )
    catalog_source = _catalog_record_to_publication(source_jsonld)
    source = catalog_source or _normalized_jsonld_source(source_document, context)
    projection = crosswalk_publication(source, context)
    projection.source_jsonld = source_jsonld
    return projection
