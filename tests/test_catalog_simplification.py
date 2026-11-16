import json
import unittest

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    crosswalk_jsonld_publication,
)


class CatalogSimplificationTest(unittest.TestCase):
    def test_technical_details_stay_in_source_and_context_stays_in_report(self):
        context = CrosswalkContext(
            catalog_version="catalog-test",
            metadata_block_version="blocks-test",
            target_collection="test",
        )
        document = {
            "@context": {"HEW": "https://w3id.org/hew/"},
            "@type": "LiteratureResource",
            "id": "HEWRES:summary",
            "resource_type": "literature",
            "title": "Summary",
            "spatial_extent": {"spatial_resolution": "1 km"},
            "spatial_support": {
                "support_type": "raster_grid_cell",
                "grid_definition": {"id": "HEWGRID:technical-only"},
            },
            "agent_associations": [
                {
                    "id": "HEWASSOC:technical-only",
                    "agent_details": {"name": "Source-only role holder"},
                }
            ],
            "contributors_details": [{"name": "Public contributor"}],
        }
        result = crosswalk_jsonld_publication(document, context)
        self.assertEqual(result.to_preservation_document(), document)
        self.assertEqual(result.report.processing_context, context)
        payload = result.to_dataverse_payload()
        blocks = payload["datasetVersion"]["metadataBlocks"]
        self.assertNotIn("hewProvenance", blocks)
        serialized = json.dumps(payload)
        for value in (
            "HEWGRID:technical-only",
            "Source-only role holder",
            "catalog-test",
            "blocks-test",
        ):
            self.assertNotIn(value, serialized)
        self.assertIn("Public contributor", serialized)
        fields = {f["typeName"]: f["value"] for f in blocks["hewGeospatial"]["fields"]}
        self.assertEqual(fields["hewSpatialResolution"], ["1 km"])
        self.assertEqual(fields["hewSpatialSupportType"], ["raster_grid_cell"])
        self.assertNotIn("hewGridDefinition", fields)
