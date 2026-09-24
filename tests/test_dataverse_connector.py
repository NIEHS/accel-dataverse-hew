import json
import unittest
from pathlib import Path

from accelerator_dataverse_hew.crosswalks.publication.v1 import CrosswalkContext
from accelerator_dataverse_hew.dataverse_utils.dataverse_config import DataverseConfig
from accelerator_dataverse_hew.dataverse_utils.dataverse_connector import DataverseConnector


class FakeResponse:
    status_code = 200
    url = "http://dataverse.example/api/dataverses/hew-publications/datasets"

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.url = None
        self.payload = None
        self.headers = None
        self.file_upload = None

    def post(self, url, headers=None, json=None, params=None, files=None):
        self.url = url
        self.headers = headers
        self.payload = json
        if files:
            self.file_upload = {"params": params, "files": files}
            return FakeResponse({"status": "OK", "data": {"files": [{"dataFile": {"id": 7}}]}})
        return FakeResponse({"status": "OK", "data": {"persistentId": "doi:10.0000/test"}})

# ignore the contents of sample1.json, this is all fake and sample1 is really the mongo format
class DataverseConnectorTest(unittest.TestCase):
    def test_creates_dataset_from_mongo_jsonld_data(self):
        document = json.loads(
            (Path(__file__).parent / "fixtures" / "sample1.json").read_text(encoding="utf-8")
        )
        session = FakeSession()
        connector = DataverseConnector(
            DataverseConfig(
                dataverse_host="http://dataverse.example",
                api_key="test-key",
                dataverse="root",
            ),
            session=session,
        )

        projection = connector.crosswalk_publication(
            document["data"],
            CrosswalkContext(
                catalog_version="hew-catalog-2026-09",
                metadata_block_version="hew-blocks-1.0.0",
                target_collection="hew-publications",
            ),
        )
        result = connector.create_dataset("hew publications", projection)

        self.assertEqual(result.pid, "doi:10.0000/test")
        self.assertEqual(
            session.url,
            "http://dataverse.example/api/dataverses/hew%20publications/datasets",
        )
        self.assertEqual(session.headers["X-Dataverse-key"], "test-key")
        self.assertEqual(
            session.payload["datasetVersion"]["metadataBlocks"]["citation"]["fields"][0]["value"],
            document["data"]["title"],
        )

    def test_disseminates_dataset_and_original_jsonld_file(self):
        document = json.loads(
            (Path(__file__).parent / "fixtures" / "sample1.json").read_text(encoding="utf-8")
        )
        session = FakeSession()
        connector = DataverseConnector(
            DataverseConfig("http://dataverse.example", "test-key", "root"),
            session=session,
        )

        projection = connector.crosswalk_publication(
            document["data"],
            CrosswalkContext(
                catalog_version="hew-catalog-2026-09",
                metadata_block_version="hew-blocks-1.0.0",
                target_collection="root",
            ),
        )
        result = connector.disseminate_publication(
            "root",
            projection,
            document["data"],
        )

        self.assertEqual(result["dataset"]["pid"], "doi:10.0000/test")
        filename, content, media_type = session.file_upload["files"]["file"]
        self.assertEqual(filename, "hew-resource.jsonld")
        self.assertEqual(media_type, "application/ld+json")
        self.assertEqual(json.loads(content), document["data"])


if __name__ == "__main__":
    unittest.main()
