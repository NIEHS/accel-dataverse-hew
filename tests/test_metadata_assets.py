import csv
import json
import unittest
from pathlib import Path

from accelerator_dataverse_hew.crosswalks.discovery import (
    cafe_terms,
    discovery_values,
    measures,
)
from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    PublicationValidationError,
    crosswalk_publication,
)

ASSETS = Path(__file__).parents[1] / "assets"


def definitions():
    fields = {}
    vocabulary = {}
    blocks = set()
    for filename in ("cafe_custom.tsv", "hew_custom.tsv"):
        section = None
        with (ASSETS / filename).open(newline="") as stream:
            for row in csv.reader(stream, delimiter="\t"):
                if row and row[0].startswith("#"):
                    section = row[0]
                elif row and section == "#metadataBlock":
                    blocks.add(row[1])
                elif row and section == "#datasetField":
                    if row[1] in fields:
                        raise AssertionError(f"Duplicate field: {row[1]}")
                    fields[row[1]] = row
                elif row and section == "#controlledVocabulary":
                    vocabulary.setdefault(row[1], []).append(row[2])
    return blocks, fields, vocabulary


class MetadataAssetsTest(unittest.TestCase):
    def setUp(self):
        self.context = CrosswalkContext(
            catalog_version="test",
            metadata_block_version="test",
            target_collection="test",
        )

    def test_rollup_covers_all_ancestors_and_multiple_resource_types(self):
        for resource_type in ("literature", "survey_instrument", "dataset", "model"):
            output, unresolved = discovery_values(
                {
                    "resource_type": resource_type,
                    "exposure_agents": ["https://w3id.org/hew/measures/term/0000181"],
                    "measured_variables": ["HEWM:0000181"],
                }
            )
            self.assertEqual(
                output["hewResourceType"],
                {
                    "literature": "Literature resource",
                    "survey_instrument": "Survey instrument",
                    "dataset": "Dataset resource",
                    "model": "Model resource",
                }[resource_type],
            )
            self.assertNotIn("hewResourceTypeCurie", output)
            self.assertNotIn("hewResourceTypeAlias", output)
            self.assertEqual(output["hewExposureConcept"], ["Drought"])
            self.assertEqual(
                output["hewMeasureParentLabel"], ["Weather", "Environment"]
            )
            for field in (
                "hewExposureCurie",
                "hewHealthImpactCurie",
                "hewGeographyCurie",
                "hewTopicCurie",
                "hewDataToolCurie",
                "hewMeasureCurie",
                "hewMeasureParentCurie",
            ):
                self.assertNotIn(field, output)
            self.assertFalse(unresolved)
        nested = next(
            (identifier, term)
            for identifier, term in measures()["terms"].items()
            if len(term["parents"]) == 3
        )
        output, _ = discovery_values({"measured_variables": [nested[0]]})
        self.assertEqual(len(output["hewMeasureParentLabel"]), 3)

    def test_removed_resource_type_fields_are_not_provisioned(self):
        _, fields, _ = definitions()
        self.assertNotIn("hewResourceTypeCurie", fields)
        self.assertNotIn("hewResourceTypeAlias", fields)
        for field in (
            "hewExposureCurie",
            "hewHealthImpactCurie",
            "hewGeographyCurie",
            "hewTopicCurie",
            "hewDataToolCurie",
            "hewMeasureCurie",
            "hewMeasureParentCurie",
        ):
            self.assertNotIn(field, fields)

    def test_event_types_are_provisioned_as_free_text(self):
        _, fields, _ = definitions()
        self.assertIn("hewEvent", fields)
        self.assertNotIn("hewEventConcept", fields)
        self.assertNotIn("hewEventCurie", fields)
        self.assertNotIn("hewEventAlias", fields)
        self.assertNotIn("hewEventExactMapping", fields)
        output, unresolved = discovery_values({"event_types": ["Heat waves"]})
        self.assertEqual(output["hewEvent"], ["Heat waves"])
        self.assertFalse(unresolved)

    def test_unknown_curies_never_become_facets(self):
        output, unresolved = discovery_values(
            {
                "health_impacts": ["hp:9999999"],
                "exposure_agents": ["HEWM:unknown"],
                "themes": [
                    {
                        "id": "ENVO:123",
                        "label": "Environment",
                        "exact_mappings": ["envo:456"],
                    }
                ],
            }
        )
        self.assertEqual(set(unresolved), {"HP:9999999", "HEWM:unknown"})
        self.assertFalse(output.get("hewHealthImpactConcept"))
        self.assertFalse(output.get("hewMeasureParentLabel"))
        self.assertEqual(output["hewTopicConcept"], ["Environment"])
        self.assertEqual(output["hewTopicExactMapping"], ["ENVO:456"])

    def test_publication_fields_match_provisioned_ownership_and_cardinality(self):
        document = json.loads(
            (Path(__file__).parent / "fixtures" / "hew_record_2.json").read_text()
        )["data"]
        document["study_objective"] = "Assess weather-related health impacts"
        projection = crosswalk_publication(document, self.context)
        _, fields, vocabulary = definitions()

        def validate(field, block_name, parent=""):
            if block_name in {"citation", "geospatial"}:
                return
            row = fields[field["typeName"]]
            self.assertEqual(row[15], block_name)
            self.assertEqual(row[14], parent)
            self.assertEqual(row[10] == "TRUE", field["multiple"], field["typeName"])
            expected_type_class = (
                "compound"
                if row[5] == "none"
                else "controlledVocabulary" if row[9] == "TRUE" else "primitive"
            )
            self.assertEqual(expected_type_class, field["typeClass"], field["typeName"])
            if field["typeClass"] == "compound":
                entries = field["value"] if field["multiple"] else [field["value"]]
                for entry in entries:
                    for child in entry.values():
                        validate(child, block_name, field["typeName"])
            elif field["typeClass"] == "controlledVocabulary":
                for value in field["value"] if field["multiple"] else [field["value"]]:
                    self.assertIn(value, vocabulary[field["typeName"]])

        for name, block in projection.to_dataverse_payload()["datasetVersion"][
            "metadataBlocks"
        ].items():
            names = [field["typeName"] for field in block["fields"]]
            self.assertEqual(len(names), len(set(names)))
            for field in block["fields"]:
                validate(field, name)

    def test_dataset_catalog_fields_keep_canonical_variable_and_distribution_structure(self):
        _, fields, _ = definitions()

        for parent, required_children in (
            (
                "hewVariableDefinitionEntry",
                {
                    "hewVariableId",
                    "hewVariableName",
                    "hewVariableDataType",
                    "hewVariableUnit",
                    "hewVariableConceptMapping",
                },
            ),
            (
                "hewDistributionEntry",
                {
                    "hewDistributionEntryUrl",
                    "hewDistributionMediaType",
                    "hewDistributionFormat",
                },
            ),
            (
                "hewDatasetTemporalSupport",
                {
                    "hewTemporalResolution",
                    "hewTemporalAlignment",
                    "hewDayBoundaryConvention",
                    "hewAggregationWindow",
                    "hewTemporalCalendar",
                },
            ),
        ):
            self.assertEqual(fields[parent][5], "none")
            expected_multiple = parent != "hewDatasetTemporalSupport"
            self.assertEqual(fields[parent][10] == "TRUE", expected_multiple)
            self.assertEqual(
                {name for name, row in fields.items() if row[14] == parent}
                & required_children,
                required_children,
            )

        self.assertEqual(
            fields["hewTemporalResolution"][14], "hewDatasetTemporalSupport"
        )
        self.assertEqual(fields["hewTemporalCalendar"][14], "hewDatasetTemporalSupport")
        self.assertEqual(fields["hewTemporalStart"][14], "hewTemporalExtent")
        self.assertEqual(fields["hewVariableConceptMapping"][9], "FALSE")
        self.assertEqual(fields["hewVariableOmopConceptStatus"][9], "TRUE")
        self.assertEqual(len(definitions()[2]["hewVariableOmopConceptStatus"]), 5)
        self.assertIn(
            "model-produced alone does not imply derivation",
            fields["cafeDerivedFromExistingDataset"][3],
        )

    def test_projects_coverage_and_full_cafe_terms(self):
        projection = crosswalk_publication(
            {
                "id": "HEW:test",
                "title": "Coverage",
                "resource_type": "literature",
                "themes": ["Asthma", "Drought", "unmapped label"],
                "spatial_extent": {
                    "bounding_box": {
                        "west": -100,
                        "east": -70,
                        "north": 45,
                        "south": 30,
                    },
                    "geometry": {"geometry_type": "Polygon", "wkt": "POLYGON EMPTY"},
                },
                "coordinate_reference_system_uri": "http://www.opengis.net/def/crs/EPSG/0/4326",
                "centroid": {"latitude": 35, "longitude": -85},
                "temporal_extent": {
                    "start_time": "2024-01-01T00:00:00-05:00",
                    "end_time": "2025-01-01T00:00:00-05:00",
                    "temporal_resolution": "daily",
                    "calendar": "gregorian",
                },
                "temporal_support": {
                    "calendar": "daymet_365",
                    "temporal_alignment": "interval",
                    "day_boundary_convention": "local_midnight",
                    "aggregation_window": "P1D",
                    "timezone": "America/New_York",
                },
            },
            self.context,
        )
        blocks = projection.to_dataverse_payload()["datasetVersion"]["metadataBlocks"]
        self.assertEqual(
            blocks["AdditionalMetadataAboutDataset"]["fields"][0]["value"],
            ["Asthma", "Drought"],
        )
        self.assertIn("geospatial", blocks)
        self.assertIn("hewGeospatial", blocks)
        geospatial_fields = {
            field["typeName"] for field in blocks["hewGeospatial"]["fields"]
        }
        self.assertNotIn("hewCentroidLatitude", geospatial_fields)
        self.assertNotIn("hewCentroidLongitude", geospatial_fields)
        extent = blocks["hewTemporal"]["fields"][0]["value"][0]
        self.assertEqual(
            extent["hewTemporalStart"]["value"], "2024-01-01T00:00:00-05:00"
        )
        self.assertNotIn("hewTemporalResolution", extent)
        support = blocks["hewTemporal"]["fields"][1]["value"]
        self.assertEqual(support["hewTemporalResolution"]["value"], "daily")
        self.assertEqual(support["hewTemporalCalendar"]["value"], "daymet_365")
        self.assertEqual(support["hewDayBoundaryConvention"]["value"], "local_midnight")
        self.assertEqual(support["hewAggregationWindow"]["value"], "P1D")

    def test_rejects_invalid_coordinate_and_time_ranges(self):
        base = {"id": "HEW:test", "title": "Coverage", "resource_type": "literature"}
        for extent in (
            {"west": -181, "east": 20, "north": 45, "south": 30},
            {"west": 30, "east": 20, "north": 45, "south": 30},
            {"west": 10, "east": 20, "north": float("nan"), "south": 30},
        ):
            with self.assertRaises(PublicationValidationError):
                crosswalk_publication(
                    {**base, "spatial_extent": {"bounding_box": extent}}, self.context
                )
        for extent in (
            {"start_time": "2024-01-01"},
            {"start_time": "2025-01-01T00:00:00Z", "end_time": "2024-01-01T00:00:00Z"},
        ):
            with self.assertRaises(PublicationValidationError):
                crosswalk_publication({**base, "temporal_extent": extent}, self.context)
