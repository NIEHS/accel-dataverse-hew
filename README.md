# accel-dataverse-hew
HEW Dataverse Support

This package includes HEW related functions for crosswalk and deposit of HEW data into Dataverse.

## Load metadata blocks

With the `dataverse` profile running from `accel-compose`, load the CAFE and HEW
metadata blocks into a target Dataverse collection:

```sh
python -m accelerator_dataverse_hew.dataverse_utils.load_metadata_blocks \
  --dataverse-target root
```

The utility uses `http://localhost:8081` by default. Set `DATAVERSE_HOST` and,
when required, `DATAVERSE_API_KEY` to override the connection settings.

The [assets](./assets) directory contains Dataverse customization assets for HEW, including CAFE and HEW custom
metadata blocks.

## Documentation
* [HEW Dataverse Support](./docs/README.md)
* [Metadata Blocks Guidance](./docs/metadata_blocks_guidance.md)
* [Dataverse Metadata Customization guide](https://guides.dataverse.org/en/latest/admin/metadatacustomization.html)
