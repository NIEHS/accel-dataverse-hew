import json
import unittest
from pathlib import Path
from unittest.mock import patch

from accelerator_core.utils.xcom_utils import DirectXcomPropsResolver
from accelerator_core.workflow.accel_data_models import (
    DisseminationDescriptor,
    DisseminationPayload,
)

from accelerator_dataverse_hew.accel_to_dataverse_crosswalk import (
    AccelToDataverseHewCrosswalk,
)
from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    crosswalk_jsonld_publication,
)
from accelerator_dataverse_hew.accel_to_dataverse_dissemination import (
    AccelDataverseHewDissemination,
)
from accelerator_dataverse_hew.dataverse_utils.dataverse_connector import (
    DataverseDisseminationResult,
)


def make_payload(document):
    descriptor = DisseminationDescriptor()
    descriptor.schema_version = "2.0.0"
    descriptor.dissemination_type = "dataverse"
    descriptor.dissemination_version = "1.0.0"
    descriptor.dissemination_identifier = "component-test"
    descriptor.dissemination_filter = {
        "catalog_version": "hew-catalog-2026-09",
        "metadata_block_version": "hew-blocks-1.0.0",
        "target_collection": "root",
    }
    payload = DisseminationPayload(descriptor)
    payload.payload.append(document)
    return payload


class AccelDataverseComponentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            (Path(__file__).parent / "fixtures" / "sample1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.resolver = DirectXcomPropsResolver(False, None)

    def test_crosswalk_transform_returns_dataverse_payload(self):
        crosswalk = AccelToDataverseHewCrosswalk(self.resolver)

        transformed = crosswalk.transform(make_payload(self.document))

        self.assertEqual(len(transformed.payload), 1)
        self.assertIn("datasetVersion", transformed.payload[0])
        self.assertEqual(
            transformed.payload[0]["datasetVersion"]["metadataBlocks"]["citation"][
                "fields"
            ][0]["value"],
            self.document["data"]["title"],
        )

    def test_transform_projects_measure_aliases_and_preserves_source(self):
        document = json.loads(json.dumps(self.document))
        exposure = {
            "coded_concept": "HEWM:0000181",
            "source_vocabularies": ["https://w3id.org/hew/measures/schema"],
            "@type": "ConceptAnnotation",
        }
        document["data"]["annotations"][0]["exposure_annotations"].append(exposure)
        crosswalk = AccelToDataverseHewCrosswalk(self.resolver)
        projections = []

        def capture_projection(*args, **kwargs):
            projection = crosswalk_jsonld_publication(*args, **kwargs)
            projections.append(projection)
            return projection

        with patch(
            "accelerator_dataverse_hew.accel_to_dataverse_crosswalk.crosswalk_jsonld_publication",
            side_effect=capture_projection,
        ):
            transformed = crosswalk.transform(make_payload(document))

        projected_document = projections[0].to_preservation_document()
        projected_exposure = projected_document["annotations"][0][
            "exposure_annotations"
        ][-1]
        self.assertEqual(projected_exposure, exposure)
        self.assertNotIn("aliases", exposure)
        blocks = transformed.payload[0]["datasetVersion"]["metadataBlocks"]
        resource_fields = {
            field["typeName"]: field for field in blocks["hewDiscovery"]["fields"]
        }
        review_fields = {
            field["typeName"]: field for field in blocks["hewReview"]["fields"]
        }
        self.assertIn("Drought", resource_fields["hewExposureConcept"]["value"])
        self.assertIn("drought", resource_fields["hewExposureAlias"]["value"])
        self.assertNotIn("hewExposureAnnotation", review_fields)

    @patch(
        "accelerator_dataverse_hew.accel_to_dataverse_dissemination.DataverseConnector"
    )
    def test_dissemination_only_submits_crosswalked_payload(self, connector_class):
        connector_class.return_value.create_dataset_from_dict.return_value = (
            DataverseDisseminationResult(pid="doi:10.0000/component-test")
        )
        crosswalk = AccelToDataverseHewCrosswalk(self.resolver)
        transformed = crosswalk.transform(make_payload(self.document))
        crosswalked_payload = transformed.payload[0]
        disseminator = AccelDataverseHewDissemination(self.resolver)

        result = disseminator.disseminate(
            transformed,
            {
                "dataverse_host": "http://dataverse.example",
                "api_key": "test-key",
                "dataverse": "root",
            },
        )

        connector_class.return_value.create_dataset_from_dict.assert_called_once_with(
            "root", crosswalked_payload, publish=True
        )
        self.assertEqual(result.payload[0]["pid"], "doi:10.0000/component-test")


if __name__ == "__main__":
    unittest.main()
