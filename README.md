# accel-dataverse-hew
HEW Dataverse Support

This package includes HEW related functions for crosswalk and deposit of HEW data into Dataverse.

## Installation

Install the package and its development tools with:

```sh
python -m pip install -e ".[dev]"
```

Runtime dependencies are declared in `pyproject.toml`; the `dev` extra adds
test, formatting, coverage, and pre-commit tools.

## Load metadata blocks

With the `dataverse` profile running from `accel-compose`, load the CAFE and HEW
metadata blocks into a target Dataverse collection:

```sh
python -m accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks \
  --dataverse-target root
```

The publication integration test performs this provisioning step automatically
for the collection named by `DATAVERSE` in `.env`. The API key must belong to a
Dataverse administrator for metadata-field installation.

Publication dissemination creates and publishes a major dataset release. It
uses BSD 3-Clause as custom dataset terms because the local Dataverse profile
does not install BSD 3-Clause as a standard server-side license.

The utility uses `http://localhost:8081` by default. Set `DATAVERSE_HOST` and,
when required, `DATAVERSE_API_KEY` to override the connection settings.

The [assets](./assets) directory contains Dataverse customization assets for HEW,
including CAFE and HEW custom metadata blocks. The publication crosswalk is
documented in [assets/crosswalks/publication/v1](./assets/crosswalks/publication/v1/README.md).

## Dataverse integration test

Copy `.env_sample` to `.env`, add `DATAVERSE_API_KEY`, and place
`sample1_dataverse.json` and `sample2_dataverse.json` in `tests/fixtures/`.
Run the opt-in integration test with:

```sh
RUN_DATAVERSE_INTEGRATION=1 python -m unittest \
  integration_tests.test_publication_dissemination
```

## Procedures

### Provision custom metadata and Solr

After loading custom metadata blocks, update Solr's schema before creating or
publishing datasets. This is required for fields such as `hewSchemaVersion` and
the CAFE fields in `assets/cafe_custom.tsv`:

```sh
curl "${DATAVERSE_HOST:-http://127.0.0.1:8081}/api/admin/index/solr/schema" \
  | docker run -i --rm \
      -v accelerator_dataverse-solr-data:/var/solr \
      gdcc/configbaker:latest \
      update-fields.sh /var/solr/data/collection1/conf/schema.xml
```

Reload Solr after updating the schema:

```sh
docker compose --profile dataverse exec dataverse-solr \
  curl "http://localhost:8983/solr/admin/cores?action=RELOAD&core=collection1"
```

Run the metadata loader before the integration test, or let the integration
test provision the blocks automatically:

```sh
python -m accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks \
  --host "${DATAVERSE_HOST:-http://127.0.0.1:8081}" \
  --dataverse-target "${DATAVERSE:-root}"
```

If indexing failed before the schema was updated, recreate the affected draft
datasets or reindex them before checking Dataverse search.

## Documentation
* [Metadata Blocks Guidance](./assets/metadata_blocks_guidance.md)
* [Publication Crosswalk v1](./assets/crosswalks/publication/v1/README.md)
* [Dataverse Metadata Customization guide](https://guides.dataverse.org/en/latest/admin/metadatacustomization.html)
