import json
import unittest
from pathlib import Path

from accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks import (
    DEFAULT_ASSET_FILES,
    load_metadata_blocks,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.configured_blocks = ["citation"]
        self.calls = []

    def post(self, url, headers=None, data=None):
        self.calls.append(("POST", url, headers, data))
        if url.endswith("/metadatablocks"):
            self.configured_blocks = json.loads(data)
        return FakeResponse({"status": "OK", "data": {}})

    def get(self, url, headers=None):
        self.calls.append(("GET", url, headers, None))
        return FakeResponse(
            {
                "status": "OK",
                "data": [{"name": name} for name in self.configured_blocks],
            }
        )


class LoadMetadataBlocksTest(unittest.TestCase):
    def test_repeated_load_preserves_existing_blocks_without_duplicates(self):
        session = FakeSession()
        asset_directory = Path(__file__).parents[1] / "assets"

        first = load_metadata_blocks(
            dataverse_host="http://dataverse.example/",
            dataverse_target="target collection",
            asset_directory=asset_directory,
            session=session,
        )
        first_configuration = list(session.configured_blocks)

        second = load_metadata_blocks(
            dataverse_host="http://dataverse.example/",
            dataverse_target="target collection",
            asset_directory=asset_directory,
            session=session,
        )

        self.assertEqual(first, second)
        self.assertEqual(first_configuration, session.configured_blocks)
        self.assertEqual(len(session.configured_blocks), len(set(session.configured_blocks)))
        self.assertIn("citation", session.configured_blocks)
        self.assertEqual(
            len(
                [
                    call
                    for call in session.calls
                    if call[0] == "POST" and call[1].endswith("/datasetfield/load")
                ]
            ),
            2 * len(DEFAULT_ASSET_FILES),
        )


if __name__ == "__main__":
    unittest.main()
