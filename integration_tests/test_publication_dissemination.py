import json
import os
import unittest
from pathlib import Path

from accelerator_core.utils.xcom_utils import DirectXcomPropsResolver
from accelerator_core.workflow.accel_data_models import (
    DisseminationDescriptor,
    DisseminationPayload,
)

from accelerator_dataverse_hew.accel_to_dataverse_crosswalk import (
    AccelToDataverseHewCrosswalk,
)
from accelerator_dataverse_hew.accel_to_dataverse_dissemination import (
    AccelDataverseHewDissemination,
)
from accelerator_dataverse_hew.dataverse_utils.dataverse_config import DataverseConfig
from accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks import (
    load_metadata_blocks,
)


REPOSITORY_ROOT = Path(__file__).parents[1]
ENV_PATH = REPOSITORY_ROOT / ".env"
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures"


def load_dotenv(path: Path) -> None:
    """Load simple KEY=value pairs without adding python-dotenv as a dependency."""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(name, value)


class PublicationDisseminationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("RUN_DATAVERSE_INTEGRATION") != "1":
            raise unittest.SkipTest(
                "set RUN_DATAVERSE_INTEGRATION=1 to run the Dataverse integration test"
            )

        load_dotenv(ENV_PATH)
        cls.config = DataverseConfig.from_env()
        if not cls.config.api_key:
            raise unittest.SkipTest("DATAVERSE_API_KEY is required in .env")

        load_metadata_blocks(
            dataverse_host=cls.config.dataverse_host,
            dataverse_target=cls.config.dataverse,
            api_key=cls.config.api_key,
        )

        cls.documents = []
        for filename in ("hew_record_1.json", "hew_record_2.json"):
            path = FIXTURE_DIRECTORY / filename
            if not path.exists():
                raise AssertionError(f"missing integration fixture: {path}")
            cls.documents.append((filename, json.loads(path.read_text(encoding="utf-8"))))

    def test_crosswalks_and_disseminates_publications(self):
        xcom_props_resolver = DirectXcomPropsResolver(False, None)
        crosswalk = AccelToDataverseHewCrosswalk(xcom_props_resolver)
        disseminator = AccelDataverseHewDissemination(xcom_props_resolver)

        for filename, document in self.documents:
            descriptor = DisseminationDescriptor()
            descriptor.schema_version = os.environ.get("HEW_SCHEMA_VERSION", "1.2.0")
            descriptor.dissemination_type = "dataverse"
            descriptor.dissemination_version = os.environ.get(
                "HEW_CROSSWALK_VERSION", "1.0.0"
            )
            descriptor.dissemination_identifier = filename

            payload = DisseminationPayload(descriptor)
            payload.payload.append(document)
            transformed = crosswalk.transform(payload)
            dataverse_payload = transformed.payload[0]

            self.assertIn("datasetVersion", dataverse_payload, filename)
            self.assertTrue(
                dataverse_payload["datasetVersion"]["metadataBlocks"],
                filename,
            )

            result = disseminator.disseminate(
                transformed,
                {
                    "dataverse_host": self.config.dataverse_host,
                    "api_key": self.config.api_key,
                    "dataverse": self.config.dataverse,
                },
            )

            self.assertTrue(result.dissemination_successful, filename)
            self.assertTrue(result.payload[0]["pid"], filename)


if __name__ == "__main__":
    unittest.main()
