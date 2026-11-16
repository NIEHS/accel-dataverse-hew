import unittest

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    crosswalk_publication,
)


class NamedReferenceProjectionTest(unittest.TestCase):
    def project(self, **fields):
        return crosswalk_publication(
            {
                "id": "HEWRES:references",
                "title": "References",
                "resource_type": "literature",
                **fields,
            },
            CrosswalkContext(
                catalog_version="test",
                metadata_block_version="test",
                target_collection="test",
            ),
        ).to_dataverse_payload()["datasetVersion"]["metadataBlocks"]

    def test_identifier_only_relations_are_not_names_or_award_numbers(self):
        blocks = self.project(
            contacts=["PERSON:jane"],
            contributors=["PERSON:alex"],
            funding_sources=["HEWFUND:award"],
        )
        citation = {field["typeName"]: field for field in blocks["citation"]["fields"]}
        self.assertNotIn("contributor", citation)
        self.assertNotIn("grantNumber", citation)
        for entry in citation.get("datasetContact", {}).get("value", []):
            self.assertNotEqual(
                entry.get("datasetContactName", {}).get("value"), "PERSON:jane"
            )
        resource = {
            field["typeName"]: field for field in blocks["hewResource"]["fields"]
        }
        self.assertEqual(resource["hewContact"]["value"], ["PERSON:jane"])
        self.assertEqual(resource["hewFundingSource"]["value"], ["HEWFUND:award"])

    def test_named_references_keep_pairings_and_project_explicit_values(self):
        blocks = self.project(
            contacts_details=[{"name": "Jane Example", "email": "jane@example.org"}],
            contributors_details=[
                {"reference_id": "PERSON:alex", "name": "Alex Example"}
            ],
            funding_sources_details=[
                {
                    "name": "Heat award",
                    "award_number": "R01-EXAMPLE",
                    "funder_name": "Example Foundation",
                }
            ],
            annotations=[
                {
                    "id": "HEWANN:one",
                    "subject": "HEWRES:references",
                    "coded_by_details": [{"description": "Study team"}],
                }
            ],
        )
        citation = {field["typeName"]: field for field in blocks["citation"]["fields"]}
        self.assertEqual(
            citation["datasetContact"]["value"][0]["datasetContactName"]["value"],
            "Jane Example",
        )
        self.assertEqual(
            citation["grantNumber"]["value"][0]["grantNumberValue"]["value"],
            "R01-EXAMPLE",
        )
        self.assertEqual(
            citation["grantNumber"]["value"][0]["grantNumberAgency"]["value"],
            "Example Foundation",
        )
        references = blocks["hewEntityReferences"]["fields"][0]["value"]
        alex = next(
            entry
            for entry in references
            if entry.get("hewReferenceIdentifier", {}).get("value") == "PERSON:alex"
        )
        self.assertEqual(alex["hewReferenceName"]["value"], "Alex Example")
        self.assertFalse(
            any(
                "annotations" in entry["hewReferenceRelation"]["value"]
                for entry in references
            )
        )

    def test_description_only_funding_does_not_become_award_number(self):
        blocks = self.project(
            funding_sources_details=[
                {"description": "Supported by community donations"}
            ]
        )
        self.assertNotIn(
            "grantNumber", {f["typeName"] for f in blocks["citation"]["fields"]}
        )
        self.assertIn("hewEntityReferences", blocks)

    def test_name_only_contact_is_preserved_without_invalid_citation_contact(self):
        blocks = self.project(contacts_details=[{"name": "Jane Example"}])
        self.assertNotIn(
            "datasetContact", {f["typeName"] for f in blocks["citation"]["fields"]}
        )
        reference = blocks["hewEntityReferences"]["fields"][0]["value"][0]
        self.assertEqual(reference["hewReferenceName"]["value"], "Jane Example")

    def test_unresolved_author_id_is_preserved_without_a_name(self):
        blocks = self.project(
            authors=[{"id": "PERSON:unknown", "agent_type": "Person"}]
        )
        self.assertNotIn(
            "author", {f["typeName"] for f in blocks["citation"]["fields"]}
        )
        reference = blocks["hewEntityReferences"]["fields"][0]["value"][0]
        self.assertEqual(reference["hewReferenceIdentifier"]["value"], "PERSON:unknown")
