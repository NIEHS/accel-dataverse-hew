import csv
import json
from pathlib import Path
import unittest

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    crosswalk_jsonld_publication,
)


class ReviewSourceOnlyTest(unittest.TestCase):
    def test_review_is_preserved_without_dataverse_review_fields(self):
        document = {
            "@context": {"HEW": "https://w3id.org/hew/"},
            "@type": "LiteratureResource",
            "id": "HEWRES:source-only-review",
            "title": "Reviewed study",
            "resource_type": "literature",
            "annotations": [
                {
                    "id": "HEWANN:source-only",
                    "coding_scheme": "Private review workflow",
                    "confidence": 0.7,
                    "coded_by_details": [{"name": "Private review team"}],
                    "exposure_annotations": [
                        {
                            "coded_concept": "HEWM:0000181",
                            "evidence_text": "Source-only evidence passage",
                        }
                    ],
                }
            ],
        }
        projection = crosswalk_jsonld_publication(
            document,
            CrosswalkContext(
                catalog_version="test",
                metadata_block_version="test",
                target_collection="test",
            ),
        )
        self.assertEqual(projection.to_preservation_document(), document)
        blocks = projection.to_dataverse_payload()["datasetVersion"]["metadataBlocks"]
        self.assertNotIn("hewReview", blocks)
        payload = json.dumps(blocks)
        for value in (
            "Private review workflow",
            "Private review team",
            "Source-only evidence passage",
            "HEWANN:source-only",
        ):
            self.assertNotIn(value, payload)
        discovery = {
            field["typeName"]: field["value"]
            for field in blocks["hewDiscovery"]["fields"]
        }
        self.assertIn("Drought", discovery["hewExposureConcept"])
        for filename in ("hew_custom.tsv", "hew_custom_details_reference.tsv"):
            with (
                Path(__file__).resolve().parents[1] / "assets" / filename
            ).open() as stream:
                for row in csv.reader(stream, delimiter="\t"):
                    self.assertNotIn("hewReview", row)
