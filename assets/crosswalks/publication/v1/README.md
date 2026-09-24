# HEW publication crosswalk v1

This directory defines the first HEW-to-Dataverse publication projection. The
crosswalk targets HEW schema version `1.2.0` and accepts the compact JSON-LD
`LiteratureResource` document persisted by MongoDB. It does not require the
source record to be stored as LinkML YAML or as a LinkML-shaped JSON document.
The machine-readable contract is in `mapping.yaml`.

## Required Dataverse configuration

Load and enable these metadata blocks in the target collection before loading
publication records:

- `citation`
- `hewResource`
- `customCAFEDataSources`
- `customCAFEDataLocation`

Enable these blocks when the corresponding source data is present:

- `hewReview` for systematic-review annotations;
- `geospatial` for meaningful resource-level geographic coverage;
- `AdditionalMetadataAboutDataset` for exact CAFE vocabulary matches.

The publication projection supplies the required CAFE derivation and
geospatial-file indicators as `No` when those facts are absent from the HEW
record. The remaining CAFE fields and the computational-workflow block remain
available for later resource types.

Install the block definitions with:

```sh
python -m accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks \
  --host "${DATAVERSE_HOST:-http://localhost:8081}" \
  --dataverse-target "${DATAVERSE_TARGET:-root}"
```

The target collection is selected by `DATAVERSE_TARGET` or the explicit
`--dataverse-target` argument. The API key is supplied through
`DATAVERSE_API_KEY` or `--api-key`. The crosswalk itself also requires a source
catalog version, metadata-block version, and target collection as context; the
catalog version is not currently a slot in the HEW source schema.

## Publication input contract

Before transformation, parse the JSON-LD document and verify its context and
`@type` against HEW schema version `1.2.0`. Then validate the supported HEW
publication semantics and adapt the document into a temporary source view for
the crosswalk. The minimum publication record contains:

- `id` or the JSON-LD equivalent `@id`;
- `title`;
- `resource_type: literature`.

LinkML remains the schema authority and can validate the adapted slot map; it is
not an intermediate persistence format. Pydantic validates the crosswalk
context and Dataverse projection rather than duplicating the HEW schema.

The crosswalk preserves the complete source record as JSON or JSON-LD. Fields
not represented by the Dataverse projection must be reported as unmapped rather
than silently discarded.

## Versioning

`mapping.yaml` is versioned independently from the HEW schema and deployed
Dataverse TSV definitions. A projection should record:

- HEW schema version;
- crosswalk version;
- metadata-block version;
- source catalog/record version;
- target collection.

Changes to field meaning, cardinality, controlled values, or preservation
behavior require a new major crosswalk version.
