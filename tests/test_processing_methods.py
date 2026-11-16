import csv
from pathlib import Path
import unittest

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    PublicationValidationError,
    crosswalk_publication,
)


class ProcessingMethodProjectionTest(unittest.TestCase):
    def project(self, methods):
        return crosswalk_publication(
            {
                "id": "HEWRES:processed",
                "title": "Processed study",
                "resource_type": "literature",
                "processing_methods": methods,
            },
            CrosswalkContext(
                catalog_version="test",
                metadata_block_version="test",
                target_collection="test",
            ),
        ).to_dataverse_payload()["datasetVersion"]["metadataBlocks"]

    def test_methods_preserve_software_and_provenance_pairs(self):
        blocks = self.project(
            [
                {
                    "name": "Area summary",
                    "description": "Summarized temperature over study areas.",
                    "software_details": {
                        "name": "Amadeus",
                        "reference_id": "HEWRES:amadeus",
                    },
                    "software_version": "1.0",
                    "provenance_reference": "https://example.org/runs/one",
                },
                {
                    "name": "Manual review",
                    "provenance_reference_details": {
                        "description": "Study team methods notebook"
                    },
                },
            ]
        )
        entries = blocks["hewCalculation"]["fields"][0]["value"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["hewMethodSoftwareName"]["value"], "Amadeus")
        self.assertEqual(
            entries[0]["hewMethodSoftwareIdentifier"]["value"], "HEWRES:amadeus"
        )
        self.assertEqual(
            entries[1]["hewMethodProvenanceDescription"]["value"],
            "Study team methods notebook",
        )
        definitions = {}
        section = None
        with (
            Path(__file__).resolve().parents[1] / "assets/hew_custom.tsv"
        ).open() as stream:
            for row in csv.reader(stream, delimiter="\t"):
                if row and row[0].startswith("#"):
                    section = row[0]
                elif row and section == "#datasetField":
                    definitions[row[1]] = row
        for entry in entries:
            for name in entry:
                self.assertEqual(definitions[name][14], "hewProcessingMethod")
        self.assertNotIn("hewCalculationParameter", definitions)
        self.assertNotIn("hewExtractionMethod", definitions)

    def test_execution_settings_and_conflicting_ids_are_rejected(self):
        for method in [
            {"parameters": [{"name": "buffer"}]},
            {
                "software": "HEWRES:one",
                "software_details": {"reference_id": "HEWRES:two"},
            },
        ]:
            with (
                self.subTest(method=method),
                self.assertRaises(PublicationValidationError),
            ):
                self.project([method])
