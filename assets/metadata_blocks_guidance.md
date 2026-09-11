# HEW Dataverse Metadata Blocks Guidance

## Purpose

This document guides dissemination of the Health and Extreme Weather (HEW)
catalog into Dataverse. HEW should reuse the existing CAFE/CHORDS metadata
blocks wherever their semantics are compatible, preserving interoperability
with the existing `accelerator-dataverse` installation.

The source CAFE block definition is:

`accelerator-dataverse/cafe_blocks.json`

The canonical HEW model is:

`HEW_Catalog_Data_Model/hew-model/schema/hew-geospatial.yaml`

## Compatibility principles

1. Preserve existing metadata block names, field names, and controlled values
   when reusing an installed CAFE block.
2. Treat CAFE-specific field names as compatibility identifiers, not as the
   preferred HEW vocabulary. For example, retain `cafeDatasetTerms` in the
   Dataverse projection but document it as a shared catalog-term field.
3. Prefer structured compound fields and identifiers over concatenated notes.
4. Use URI-valued fields for HEW concepts and external identifiers whenever the
   existing field supports them.
5. Do not force HEW concepts into an existing field merely because the label is
   similar. Add a HEW-specific block when the semantics or cardinality differ.
6. Keep the original HEW record available as JSON or JSON-LD when Dataverse
   fields cannot preserve the complete model.

## Existing blocks

### `citation`

Use for all HEW resources, especially literature resources. The existing block
supports:

- title, alternative title, URL, and depositor;
- authors, contacts, producers, contributors, and funding information;
- descriptions, subjects, keywords, and topic classifications;
- related publications, datasets, materials, and references;
- language, publication/production/deposit dates, and covered time periods;
- software and data-source text.

HEW mapping guidance:

| HEW model | Citation field |
|---|---|
| `title`, `name` | `title` or `alternativeTitle` |
| `description`, `abstract` | `dsDescription` |
| `url` | `alternativeURL` |
| `doi`, `pmid`, `pmcid`, `identifiers` | `otherId` |
| `authors` | `author` |
| `contacts` | `datasetContact` |
| `keywords` | `keyword` |
| `publication_type`, `citation`, `journal` | `publication`, `topicClassification`, or `notesText` as appropriate |
| `publication_date` | `productionDate` when no more specific installed field is available |
| `temporal_coverage` | `timePeriodCovered` |
| `license`, `access_rights` | Dataset-level terms/configuration, not citation text |
| `related_resources` | `relatedDatasets` or `relatedMaterial` |
| `funding_sources` | `grantNumber` |

For DOI, PMID, and PMCID, use an explicit agency/type in `otherId` rather than
putting all identifiers in free text. Preserve the canonical URL separately.

### `geospatial`

Use for resource-level geographic discovery:

- `geographicCoverage` for named countries, states, cities, or other places;
- `geographicUnit` for the unit represented by the resource;
- `geographicBoundingBox` for west/east/north/south bounds.

This is a projection of HEW `spatial_extent`, not a complete replacement for
it. The existing bounding-box fields are text fields, so validation of numeric
ranges and coordinate reference systems remains the responsibility of the HEW
crosswalk.

HEW geometry, named-location identifiers, centroids, environmental context,
GeoJSON, WKT, and CRS URIs should be preserved in a HEW JSON/JSON-LD attachment
until a suitable custom block is available.

### `AdditionalMetadataAboutDataset`

Use `cafeDatasetTerms` for broad HEW discovery terms that are already present
in the shared controlled vocabulary. Relevant existing values include terms
such as `Climate`, `Exposure`, `Environmental Health`, `Extreme Temperatures`,
`Health`, `Heat Wave`, `Wildfire`, `Health Equity`, `Public Health`, `Risk`,
`Vulnerability`, and `Weather`.

This field is valuable for CAFE/CHORDS compatibility, but it should not become
the sole representation of HEW coding. HEW ontology identifiers, review
coding states, evidence, and parent concepts require a richer representation.

### `computationalworkflow`

Use for software, notebooks, models, and workflow resources. Reuse:

- `workflowType` for the existing workflow vocabulary;
- `workflowCodeRepository` for repository URLs;
- `workflowDocumentation` for documentation links or text.

This block is not needed for ordinary publication records unless the
publication explicitly describes a workflow or software artifact.

### `customCAFEDataSources`

Use for dataset, model, and derived-resource provenance. Reuse:

- `cafeDerivedFromExistingDataset` for the yes/no derivation indicator;
- `cafeSourceData` for source title, authors, institution, version, DOI/URL,
  dates, data type, spatial resolution, timestep, attribution, and disclaimer.

Do not populate this block for a publication merely because the paper cites a
dataset. Use it when the HEW resource itself is derived from or materially
depends on the source dataset.

### `customCAFEDataLocation`

Use for deposited geospatial files and dataset-level file characteristics:

- `cafeIncludesGeospatialFile`;
- `cafeSpatialReferenceSystem`;
- `cafeSpatialFileType` and `cafeSpatialFileTypeOther`;
- `cafeSpatialResolution`.

These fields map to parts of HEW `GeospatialResource`, but they describe files
and resource-level characteristics. They do not replace environmental-variable
`spatial_support` or `temporal_support`.

## HEW-specific blocks

The existing CAFE blocks do not adequately represent the following model areas.
These should be added as HEW-specific blocks rather than flattened into
`notesText`:

### HEW Resource Metadata

Recommended fields:

- HEW resource identifier;
- HEW resource type and status;
- canonical URL and alternate identifiers;
- exposure, health-impact, geography, data-tool, model, and special-topic
  concepts;
- related HEW resource identifiers;
- source catalog and catalog-version information.

### HEW Review Coding

Recommended fields:

- coding scheme and version;
- annotation date and information source;
- coding method;
- coder, reviewer, and generating-agent identifiers;
- exposure, health-impact, geography, data-tool/method, and special-topic
  annotations;
- evidence text, confidence, notes, and human-review status.

### HEW Data Resource Metadata

Recommended fields:

- data dictionary and variables;
- measured and environmental variables;
- measured property and measurement method;
- aggregation method;
- variable-level spatial and temporal support;
- ontology mappings and OMOP concept bindings;
- structured distributions and access information.

### HEW Agents and Provenance

Recommended fields:

- people, organizations, software agents, programs, projects, and funding
  sources;
- role-bearing agent associations;
- start/end dates, affiliation context, contribution description, and source.

For the first release, simple authors, contacts, contributors, producers, and
funding identifiers can use `citation`. Full role-bearing provenance may remain
in JSON-LD until the HEW block is implemented.

## Initial publication scope

For the first HEW publications dissemination workflow, emit:

1. the required `citation` block;
2. `geospatial` when the publication has meaningful geographic coverage;
3. `AdditionalMetadataAboutDataset.cafeDatasetTerms` for matching broad HEW
   terms;
4. HEW Resource Metadata for resource type and catalog identifiers, once the
   custom block is installed;
5. HEW Review Coding when systematic-review annotations are present;
6. a JSON or JSON-LD attachment containing any fields not represented in the
   metadata blocks.

The source and geospatial-file CAFE blocks should remain enabled for future
dataset, model, and geospatial-resource dissemination, but should generally be
empty for literature-only records.

## Crosswalk requirements

The accelerator crosswalk should:

- omit empty fields rather than emitting empty primitive or compound values;
- preserve HEW identifiers and identifier types;
- map HEW controlled terms to existing CAFE values only when the mapping is
  semantically exact;
- retain unmapped HEW terms in the HEW JSON/JSON-LD representation;
- distinguish resource-level spatial extent from variable-level spatial
  support;
- distinguish publication metadata from review annotations;
- validate bounding-box ordering and coordinate ranges before rendering;
- record the HEW schema version and catalog record/version in the output.

The existing CAFE blocks are therefore best treated as interoperable Dataverse
projections of the HEW model. They provide a strong foundation for citation,
discovery, geospatial indexing, source attribution, and workflow metadata, but
they should not be treated as the complete HEW schema.
