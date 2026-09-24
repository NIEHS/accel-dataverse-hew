import argparse
import csv
import json
import os
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

import requests


DEFAULT_ASSET_FILES = ("cafe_custom.tsv", "hew_custom.tsv")


def metadata_block_names(tsv_path: Path) -> list[str]:
    """Return the metadata block names declared in a Dataverse TSV file."""
    names = []
    in_metadata_block_section = False
    with tsv_path.open("r", encoding="utf-8", newline="") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        for row in reader:
            if row and row[0] == "#metadataBlock":
                in_metadata_block_section = True
                continue
            if row and row[0].startswith("#"):
                in_metadata_block_section = False
            if in_metadata_block_section and len(row) > 1 and row[1].strip():
                if row[1] not in names:
                    names.append(row[1])
    if not names:
        raise ValueError(f"No metadata blocks found in {tsv_path}")
    return names


def _response_data(response: requests.Response):
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") not in (None, "OK"):
        raise RuntimeError(f"Dataverse request failed: {payload}")
    return payload.get("data")


def _configured_block_names(data: Iterable) -> list[str]:
    names = []
    for block in data or []:
        name = block.get("name") if isinstance(block, dict) else block
        if name and name not in names:
            names.append(name)
    return names


def load_metadata_blocks(
    dataverse_host: str,
    dataverse_target: str,
    api_key: Optional[str] = None,
    asset_directory: Optional[Path] = None,
    session: Optional[requests.Session] = None,
) -> list[str]:
    """Load the HEW metadata blocks and enable them for a Dataverse collection."""
    host = dataverse_host.rstrip("/")
    asset_directory = asset_directory or Path(__file__).resolve().parents[2] / "assets"
    http = session or requests.Session()
    headers = {"X-Dataverse-key": api_key} if api_key else {}
    loaded_names = []

    for asset_file in DEFAULT_ASSET_FILES:
        tsv_path = asset_directory / asset_file
        if not tsv_path.is_file():
            raise FileNotFoundError(f"Metadata block asset not found: {tsv_path}")
        response = http.post(
            f"{host}/api/admin/datasetfield/load",
            headers={**headers, "Content-Type": "text/tab-separated-values"},
            data=tsv_path.read_bytes(),
        )
        _response_data(response)
        for name in metadata_block_names(tsv_path):
            if name not in loaded_names:
                loaded_names.append(name)

    target_path = quote(dataverse_target, safe="")
    response = http.get(
        f"{host}/api/dataverses/{target_path}/metadatablocks",
        headers=headers,
    )
    configured_names = _configured_block_names(_response_data(response))
    for name in loaded_names:
        if name not in configured_names:
            configured_names.append(name)

    response = http.post(
        f"{host}/api/dataverses/{target_path}/metadatablocks",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps(configured_names),
    )
    _response_data(response)
    return loaded_names


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataverse-target",
        required=True,
        help="Dataverse collection name or alias to enable the metadata blocks for",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("DATAVERSE_HOST", "http://localhost:8081"),
        help="Dataverse base URL (default: DATAVERSE_HOST or http://localhost:8081)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DATAVERSE_API_KEY"),
        help="Dataverse API key (default: DATAVERSE_API_KEY)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    loaded_names = load_metadata_blocks(
        dataverse_host=args.host,
        dataverse_target=args.dataverse_target,
        api_key=args.api_key,
    )
    print(
        f"Loaded {len(loaded_names)} metadata blocks into "
        f"Dataverse target '{args.dataverse_target}': {', '.join(loaded_names)}"
    )


if __name__ == "__main__":
    main()
