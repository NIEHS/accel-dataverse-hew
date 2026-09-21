import json
import unittest
from datetime import date
from pathlib import Path

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    PublicationValidationError,
    crosswalk_jsonld_publication,
    crosswalk_publication,
    validate_publication_source,
)


class PublicationCrosswalkTest(unittest.TestCase):
    def setUp(self):
        self.context = CrosswalkContext(
            catalog_version="hew-catalog-2026-09",
            metadata_block_version="hew-blocks-1.0.0",
            target_collection="hew-publications",
        )

    def test_maps_citation_and_identifiers_with_normalization(self):
        record = {
            "id": "HEWRES:test-1",
            "title": "Example publication",
            "resource_type": "literature",
            "url": "HTTPS://EXAMPLE.ORG/publication/",
            "doi": "https://doi.org/10.1234/Example.1",
            "pmid": "PMID:12345",
            "pmcid": "pmcid:pmc98765",
            "authors": ["orcid:0000-0000-0000-0001", ""],
            "keywords": [" Heat ", "Heat", "health"],
            "abstract": "An abstract.",
            "publication_date": "2026-01-02",
            "citation": "Example et al.",
            "journal": "Example Journal",
            "status": "active",
        }

        projection = crosswalk_publication(record, self.context)
        payload = projection.to_dataverse_payload()
        blocks = payload["datasetVersion"]["metadataBlocks"]
        citation = blocks["citation"]["fields"]
        resource = blocks["hewResource"]["fields"]

        self.assertEqual(validate_publication_source(record).publication_date, date(2026, 1, 2))
        self.assertEqual(citation[1]["value"], "https://example.org/publication")
        identifiers = next(field for field in citation if field["typeName"] == "otherId")
        self.assertEqual(
            [(item["otherIdAgency"]["value"], item["otherIdValue"]["value"]) for item in identifiers["value"]],
            [("DOI", "10.1234/Example.1"), ("PMID", "12345"), ("PMCID", "PMC98765")],
        )
        keywords = next(field for field in citation if field["typeName"] == "keyword")
        self.assertEqual([item["keywordValue"]["value"] for item in keywords["value"]], ["Heat", "health"])
        authors = next(field for field in citation if field["typeName"] == "author")
        self.assertEqual(len(authors["value"]), 1)
        self.assertIn("hewCrosswalkVersion", {field["typeName"] for field in resource})
        self.assertEqual(projection.report.unmapped, [])

    def test_omits_empty_optional_values_and_reports_them(self):
        projection = crosswalk_publication(
            {"id": "HEWRES:test-2", "title": "Minimal", "resource_type": "literature"},
            self.context,
        )

        citation_names = {field.type_name for field in projection.metadata_blocks["citation"].fields}
        omitted_sources = {entry.source for entry in projection.report.omitted}
        self.assertNotIn("alternativeURL", citation_names)
        self.assertNotIn("otherId", citation_names)
        self.assertIn("url", omitted_sources)
        self.assertIn("keywords", omitted_sources)
        self.assertNotIn('"value": ""', json.dumps(projection.to_dataverse_payload()))

    def test_rejects_missing_or_invalid_publication_contract(self):
        with self.assertRaises(PublicationValidationError):
            validate_publication_source({"title": "Missing ID", "resource_type": "literature"})
        with self.assertRaises(PublicationValidationError):
            validate_publication_source(
                {"id": "HEWRES:test-3", "title": "Wrong type", "resource_type": "dataset"}
            )
        with self.assertRaises(PublicationValidationError):
            validate_publication_source(
                {
                    "id": "HEWRES:test-4",
                    "title": "Bad DOI",
                    "resource_type": "literature",
                    "doi": "not-a-doi",
                }
            )

    def test_reports_unsupported_fields_without_discarding_them_from_source(self):
        projection = crosswalk_publication(
            {
                "id": "HEWRES:test-5",
                "title": "Annotated",
                "resource_type": "literature",
                "annotations": [{"id": "HEWANN:test"}],
            },
            self.context,
        )

        self.assertEqual(projection.report.unmapped[0].source, "annotations")

    def test_projects_mongodb_jsonld_and_preserves_original_document(self):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "hew_publications"
            / "publication_identifiers.jsonld"
        )
        document = json.loads(fixture_path.read_text(encoding="utf-8"))

        projection = crosswalk_jsonld_publication(document, self.context)

        self.assertEqual(projection.source_id, "HEWRES:publication-identifiers")
        self.assertEqual(projection.to_preservation_document(), document)
        self.assertEqual(
            projection.to_dataverse_payload()["datasetVersion"]["metadataBlocks"]["citation"]["fields"][0]["value"],
            document["title"],
        )

    def test_projects_mongo_data_stanza_as_dataverse_json(self):
        mongo_document = json.loads(
            (Path(__file__).parent / "fixtures" / "sample1.json").read_text(encoding="utf-8")
        )

        projection = crosswalk_jsonld_publication(mongo_document["data"], self.context)
        output_directory = Path(__file__).parent / "temp"
        output_directory.mkdir(exist_ok=True)
        output_path = output_directory / "sample1_dataverse.json"
        output_path.write_text(projection.to_dataverse_json(), encoding="utf-8")

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        fields = payload["datasetVersion"]["metadataBlocks"]["citation"]["fields"]

        self.assertEqual(fields[0]["typeName"], "title")
        self.assertEqual(fields[0]["value"], mongo_document["data"]["title"])
        self.assertEqual(
            [field["typeName"] for field in fields],
            ["title", "otherId", "author"],
        )

    def test_rejects_jsonld_without_hew_context_or_type(self):
        base_document = {
            "id": "HEWRES:test-jsonld",
            "title": "Invalid JSON-LD",
            "resource_type": "literature",
        }
        with self.assertRaises(PublicationValidationError):
            crosswalk_jsonld_publication(base_document, self.context)
        with self.assertRaises(PublicationValidationError):
            crosswalk_jsonld_publication(
                {
                    "@context": {"HEW": "https://w3id.org/hew/"},
                    **{**base_document, "resource_type": "dataset"},
                },
                self.context,
            )


if __name__ == "__main__":
    unittest.main()
