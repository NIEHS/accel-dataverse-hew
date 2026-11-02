"""Shared discovery projection for HEW resources and review annotations."""

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files

OBO_PREFIXES = {
    "ecto",
    "envo",
    "mondo",
    "hp",
    "chebi",
    "uberon",
    "ncit",
    "vo",
    "scdo",
    "pato",
    "gsso",
    "ppo",
}
RESOURCE_LABELS = {
    "literature": "Literature resource",
    "dataset": "Dataset resource",
    "cohort": "Cohort resource",
    "survey_instrument": "Survey instrument",
    "survey_dataset": "Survey dataset",
    "software_code_library": "Software/code library",
    "model": "Model resource",
    "geospatial_dataset": "Geospatial dataset",
    "exposome_dataset": "Exposome dataset",
    "resource_collection": "Resource collection",
    "tool": "Tool resource",
    "other": "Other resource",
}
RESOURCE_CLASSES = {
    "literature": "LiteratureResource",
    "dataset": "DatasetResource",
    "cohort": "CohortResource",
    "survey_instrument": "SurveyInstrument",
    "survey_dataset": "SurveyDataset",
    "software_code_library": "SoftwareResource",
    "model": "ModelResource",
    "geospatial_dataset": "GeospatialResource",
    "resource_collection": "ResourceCollection",
    "tool": "ToolResource",
    "program": "Program",
    "project": "Project",
    "funding_source": "FundingSource",
    "spatiotemporal_exposure": "SpatiotemporalExposure",
    "covariate_calculation": "CovariateCalculation",
}
LABELS = {
    "global_or_unspecified_location": "Global or unspecified location",
    "central_south_america": "Central/South America",
    "non_us_north_america": "Non-US North America",
    "united_states": "United States",
    "ocean_coastal": "Ocean/coastal",
}
CONCEPT_SOURCES = {
    "hewExposure": ("exposures", "exposure_agents", "exposure_concept"),
    "hewHealthImpact": ("health_impacts", "associated_health_outcomes"),
    "hewGeography": ("geography", "geographic_locations"),
    "hewTopic": ("special_topics", "themes"),
    "hewEvent": ("event_types",),
    "hewDataTool": ("data_and_models",),
}
ANNOTATION_SOURCES = {
    "exposure_annotations": "hewExposure",
    "health_impact_annotations": "hewHealthImpact",
    "special_topic_annotations": "hewTopic",
}


def curie(value):
    """Compact supported IRIs and normalize canonical OBO prefixes."""
    value = value.strip()
    for base, prefix in (
        ("https://w3id.org/hew/measures/term/", "HEWM:"),
        ("https://w3id.org/hew/measures/", "vocab:"),
    ):
        if value.startswith(base):
            return prefix + value[len(base) :]
    match = re.fullmatch(r"https?://purl.obolibrary.org/obo/([A-Za-z]+)_(.+)", value)
    if match:
        return f"{match[1].upper()}:{match[2]}"
    for prefix_name, base in measures()["prefixes"].items():
        if value.startswith(base) and base.startswith(("http://", "https://")):
            prefix = (
                prefix_name.upper()
                if prefix_name.lower() in OBO_PREFIXES
                else prefix_name
            )
            return prefix + ":" + value[len(base) :]
    prefix, separator, local = value.partition(":")
    if separator and (prefix.lower() in OBO_PREFIXES or prefix.lower() == "hewm"):
        return f"{prefix.upper()}:{local}"
    return value


def is_identifier(value):
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_.-]*:\S+$", value))


def values(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def label(value):
    return LABELS.get(
        value, value.replace("_", " ").capitalize() if "_" in value else value
    )


@lru_cache(maxsize=1)
def measures():
    return json.loads(
        files(__package__).joinpath("hew_measures_terms.json").read_text()
    )


@lru_cache(maxsize=1)
def cafe_terms():
    return json.loads(files(__package__).joinpath("cafe_terms.json").read_text())


def _concepts(value):
    for item in values(value):
        if isinstance(item, Mapping) and "levels" in item:
            for entries in item["levels"].values():
                yield from _concepts(entries)
        elif isinstance(item, Mapping) and any(
            key in item for key in ("level1", "level2", "level3")
        ):
            for key in ("level1", "level2", "level3"):
                yield from _concepts(item.get(key))
        elif isinstance(item, (str, Mapping)):
            yield item


def discovery_values(source):
    """Return Dataverse field values and concepts whose labels cannot be resolved.

    Only labels become facets. Unknown identifiers remain searchable in CURIE
    fields and are returned for the caller's mapping report.
    """
    output = defaultdict(list)
    unresolved = []
    vocabulary = measures()["terms"]

    def add(name, entries):
        for entry in values(entries):
            if (
                isinstance(entry, str)
                and entry.strip()
                and entry.strip() not in output[name]
            ):
                output[name].append(entry.strip())

    def measure(identifier, mappings=()):
        term = vocabulary.get(identifier)
        if not term:
            return
        add("hewMeasureCurie", identifier)
        add("hewMeasureLabel", term["title"])
        add("hewMeasureAlias", term.get("aliases"))
        add(
            "hewMeasureExactMapping",
            [curie(item) for item in term.get("exact_mappings", [])],
        )
        add("hewMeasureExactMapping", list(mappings))
        for parent in term["parents"]:
            add("hewMeasureParentLabel", parent["label"])
            add("hewMeasureParentCurie", parent["curie"])

    def concept(stem, item):
        if isinstance(item, str):
            item = {"coded_concept": item} if is_identifier(item) else {"label": item}
        identifier = item.get("coded_concept") or item.get("id") or item.get("@id")
        identifier = curie(identifier) if isinstance(identifier, str) else None
        if identifier and not is_identifier(identifier):
            item = {**item, "label": item.get("label") or identifier}
            identifier = None
        term = vocabulary.get(identifier, {})
        aliases = [*values(item.get("aliases")), *values(term.get("aliases"))]
        preferred = next(
            (
                item.get(key)
                for key in ("preferred_label", "label", "title", "name")
                if item.get(key)
            ),
            None,
        )
        preferred = (
            preferred
            or term.get("title")
            or next(
                (
                    alias
                    for alias in aliases
                    if isinstance(alias, str) and not is_identifier(alias)
                ),
                None,
            )
        )
        if preferred and not is_identifier(preferred):
            add(stem + "Concept", label(preferred))
        elif identifier:
            add(stem + "Curie", identifier)
            unresolved.append(identifier)
        if identifier:
            add(stem + "Curie", identifier)
        add(
            stem + "Alias",
            [
                alias
                for alias in aliases
                if isinstance(alias, str) and not is_identifier(alias)
            ],
        )
        mappings = [
            curie(mapping)
            for mapping in [
                *values(item.get("exact_mappings")),
                *values(term.get("exact_mappings")),
            ]
            if isinstance(mapping, str)
        ]
        add(stem + "ExactMapping", mappings)
        measure(identifier, mappings)

    def measure_references(value):
        if isinstance(value, str) and curie(value).startswith("HEWM:"):
            identifier = curie(value)
            if identifier not in vocabulary:
                add("hewMeasureCurie", identifier)
                unresolved.append(identifier)
            else:
                measure(identifier)
        elif isinstance(value, list):
            for item in value:
                measure_references(item)
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if key not in {"aliases", "evidence_text", "description", "notes"}:
                    measure_references(item)

    resource_type = source.get("resource_type") or source.get("@type", "")
    if isinstance(resource_type, str) and resource_type:
        class_name = resource_type.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        resource_type = next(
            (
                name
                for name, class_value in RESOURCE_CLASSES.items()
                if class_value == class_name
            ),
            resource_type,
        )
        if is_identifier(resource_type):
            output["hewResourceTypeCurie"] = [curie(resource_type)]
            unresolved.append(resource_type)
        else:
            output["hewResourceType"] = RESOURCE_LABELS.get(
                resource_type, label(resource_type)
            )
        if resource_type in RESOURCE_CLASSES:
            output["hewResourceTypeCurie"] = ["HEW:" + RESOURCE_CLASSES[resource_type]]
    for stem, names in CONCEPT_SOURCES.items():
        for name in names:
            for item in _concepts(source.get(name)):
                concept(stem, item)
    for feature in values(source.get("geographic_features")):
        if isinstance(feature, str):
            add("hewGeographicFeature", label(feature))
    data_and_models = source.get("data_and_models")
    if isinstance(data_and_models, Mapping):
        for item in _concepts(data_and_models.get("model_types")):
            concept("hewModel", item)
    for annotation in values(source.get("annotations")):
        if not isinstance(annotation, Mapping):
            continue
        for name, stem in ANNOTATION_SOURCES.items():
            for item in _concepts(annotation.get(name)):
                concept(stem, item)
        for geography in values(annotation.get("geography_annotations")):
            if isinstance(geography, Mapping):
                for item in _concepts(geography.get("geographic_locations")):
                    concept("hewGeography", item)
                for feature in values(geography.get("geographic_features")):
                    if isinstance(feature, str):
                        add("hewGeographicFeature", label(feature))
        for method in values(annotation.get("data_tool_method_annotations")):
            if isinstance(method, Mapping):
                for name, stem in (
                    ("data_resource_types", "hewDataTool"),
                    ("model_types", "hewModel"),
                ):
                    for item in _concepts(method.get(name)):
                        concept(stem, item)
    measure_references(source)
    return dict(output), list(dict.fromkeys(unresolved))
