# HEW Dataverse Metadata Blocks

## Authority and scope

The design follows [metadata_blocks_design_notes.md](metadata_blocks_design_notes.md),
HEW_Catalog_Data_Model schema 2.0.0 (hew-model/schema/hew.yaml and its modules),
and HEW_Measures vocabulary 1.0.0 (data/HewMeasures.yaml).
These are fresh block definitions; there are no legacy HEW aliases or migration fields.

The provisioning assets are cafe_custom.tsv and hew_custom.tsv. The loader
installs every custom block and enables them together with the installed
Dataverse citation and geospatial blocks. Empty optional blocks are not emitted
for individual records. The structured dataset fields and temporal-support
hierarchy are metadata-block version `hew-blocks-1.1.0`; existing Dataverse
installations must provision and verify the updated definitions before
submitting records that use them.

## CAFE first

cafe_custom.tsv provisions all four custom blocks exported in
accelerator-dataverse/cafe_blocks.json, including all fields and controlled values:

| Block | HEW content |
|---|---|
| AdditionalMetadataAboutDataset | Exact matches to the complete cafeDatasetTerms vocabulary |
| computationalworkflow | Workflow type, repository URL, documentation |
| customCAFEDataSources | Derivation indicator and structured source dataset provenance |
| customCAFEDataLocation | Geospatial-file indicator, CRS, file type, spatial resolution |

Use the installed field names and controlled values unchanged. Only map values
whose semantics match; a publication mentioning a dataset does not make the
publication a derived dataset. Set `cafeDerivedFromExistingDataset` to Yes only
when the catalog record documents derivation from identified source dataset(s).
Being model-produced does not by itself establish that lineage. The publication
crosswalk defaults both required CAFE indicators to No when the source provides
no evidence.

For geospatial resources, map coordinate_reference_system and
coordinate_reference_system_uri to cafeSpatialReferenceSystemName/URL;
map quantitative_spatial_resolution.resolution_value/unit to
cafeSpatialResolutionValue/Unit, using the Other fields when the unit is outside
the CAFE vocabulary. Do not duplicate those resource/file characteristics in a
HEW-only field. Variable support retains its own CRS and resolution within its
structured support value.

Use citation for title, subtitle, description/abstract, URL, identifiers
(including same_as), authors, contacts, contributors, funding, keywords,
publication details, language, and publication dates. Use dataset terms and access
configuration for license/access_rights, rather than inventing HEW text fields.

## Common discovery: hewDiscovery

All resource types share these facets:

| Meaning | Plain-text facet | Separate machine and synonym fields |
|---|---|---|
| Record type | hewResourceType | hewResourceTypeExactMapping |
| Exposure | hewExposureConcept | hewExposureCurie, hewExposureAlias, hewExposureExactMapping |
| Health impact | hewHealthImpactConcept | hewHealthImpactCurie, hewHealthImpactAlias, hewHealthImpactExactMapping |
| Geography | hewGeographyConcept | hewGeographyCurie, hewGeographyAlias, hewGeographyExactMapping |
| Topic/theme | hewTopicConcept | hewTopicCurie, hewTopicAlias, hewTopicExactMapping |
| Event type | hewEvent (free-text) | — |
| Data/tool | hewDataToolConcept | hewDataToolCurie, hewDataToolAlias, hewDataToolExactMapping |
| Model | — | hewModelExactMapping |

hewGeographicFeature is an additional plain-text facet. CURIEs, aliases, and
exact mapping fields are searchable but never facetable. Only populate mapping
fields when an actual mapping exists. Record-type CURIEs identify the corresponding
HEW schema class where known.

Project publication review concepts, survey exposure_agents/health_impacts/
geographic_locations/special_topics/event_types, dataset concepts, and project
themes here. Do not create parallel survey or review discovery facets.
The shared discovery helper also accepts catalog hierarchy entries and simple
plain-text terms. Explicit preferred_label/label/title/name takes precedence,
then a matched HEW Measures title, then the first supplied alias. Unknown CURIEs
without labels remain in the CURIE field and are reported; they never become
human-readable facets. OBO prefixes are canonicalized to uppercase.

### Measures rollup

Match a HEWM CURIE (or its full HEW Measures term IRI) to the pinned packaged
HEW Measures snapshot. Populate hewMeasureLabel/Curie/Alias/ExactMapping.
Follow the term's taxonomy_parent and every transitive class is_a ancestor,
omitting the abstract Category root. Populate hewMeasureParentLabel and
hewMeasureParentCurie with deduplicated values.

For example, HEWM:0000181 produces Drought and the Weather and Environment
parent facets. Taxonomy classes have vocab: CURIEs, not fabricated HEWM numbers.
Plain labels and aliases are not fuzzy-matched to identifiers. Unknown HEWM
identifiers do not acquire guessed parents.

The packaged snapshot records its source revision, schema, version, prefixes,
and CC-BY-4.0 license. Rebuild it from HEW_Measures data/HewMeasures.yaml or its
dist/hew_measures.jsonld export when upgrading the vocabulary. Keep the parent
chain and exact_mappings as well as titles and aliases.

## Geospatial and temporal

Use the installed geospatial block for named geographic coverage, geographic
units, and bounding boxes. Validate numeric coordinate ranges and ordering
before creating a Dataverse record.

hewGeospatial carries geometry type, WKT, GeoJSON, centroid, named location
identifiers, environmental context labels/CURIEs, compact spatial-resolution
summaries, and the dataset spatial-support category. Detailed grid definitions
and support objects remain in the source attachment or linked technical metadata.
Resource-level extent and variable-level support have distinct meanings.
CRS/file metadata uses CAFE fields first.

hewTemporal carries free-text coverage, a dataset-default
`hewDatasetTemporalSupport` compound, and repeated `hewTemporalExtent`
compounds. Extent contains only coverage start/end, timestamp timezone, and
coverage status; timestamps remain text so UTC offsets and sub-day precision
survive, with start inclusive and end exclusive. Resolution, calendar, temporal
alignment, day-boundary convention, aggregation window, and value-support
timezone belong to temporal support, not to the coverage interval. In
particular, retain source calendars such as `daymet_365`; do not normalize them
to Gregorian dates or treat a daily interval as a coverage date. Update cadence
and typical latency are separate dataset properties. The publication crosswalk
validates explicit offsets and interval ordering and moves legacy resolution or
calendar values out of temporal extents into the support compound.

### Dataset variables, deliveries, and distributions

For `hewDataResource`, use repeatable `hewVariableDefinitionEntry` records for
the meaning of each dataset variable/field and `hewVariableDeliveryEntry`
records for how that variable is represented in a specific product or data
layout. This pattern is not limited to environmental variables or file formats:
it can describe a CSV/Parquet column, a NetCDF array or band, a coordinate,
dimension, identifier, or measure. Use a stable `hewVariableId` on the
definition and copy that identifier into `hewDeliveryVariableId` to preserve the
relationship. Record the canonical meaning, datatype, unit, role, measured
property, method, and concept mappings on the definition; record native name,
delivery datatype/unit, aggregation, and delivery-specific support on the delivery.
Decoding details such as scale factors, offsets, missing-value sentinels, and CF
cell-method syntax belong in the linked data dictionary or preserved source. Keep concepts paired with their variable definitions rather than flattening
multiple variables into unrelated resource-level lists.

Dataset temporal support supplies defaults. An explicit delivery's temporal
support describes that delivery's values and takes precedence as a whole; do
not merge individual default properties into it silently. This is how distinct
calendars, daily boundaries, alignments, and aggregation windows stay attached
to the correct variable. Keep detailed native grids and their identifiers in the source or linked
technical metadata; the Dataverse projection exposes compact resolution and
support summaries rather than a grid model.

Use repeatable `hewDistributionEntry` records to keep each access URL together
with its title, `hewDistributionMediaType` (such as `application/x-netcdf` or
`application/vnd.apache.parquet`), and `hewDistributionFormat` (such as NetCDF-4
or Apache Parquet). These are different properties: MIME type identifies the
media type, while format can retain the format name/version. Link distributions
to the variable identifiers they contain when known. Variable definitions, deliveries, distributions, and dataset temporal support
use their structured compounds rather than duplicate JSON fields. Detailed spatial support and grid definitions remain in the source or linked
technical metadata. Preserve complete source JSON-LD and link the full data
dictionary for details beyond the structured catalog projection.

Keep run-level provenance and generated-value details in EnVar and link them to
the HEW dataset/product using stable identifiers; do not copy run records onto
every catalog dataset or variable.

## Remaining type-specific information

| Block | Classes/content not covered above |
|---|---|
| hewResource | Catalog resource ID, status, and related resources; processing versions remain in the crosswalk report |
| hewPublication | LiteratureResource study objective; bibliographic fields reuse citation |
| hewDataResource | DatasetResource/CohortResource/SurveyDataset data dictionary, repeatable variable definitions and deliveries, distributions, processing and OMOP linkage |
| hewSurvey | SurveyInstrument constructs/questions, population, administration, EDC, readability, CDE integration and instrument relationships |
| hewSoftware | SoftwareResource language, software type and maintainers; repository/documentation reuse CAFE |
| hewModelResource | ModelResource type and input/output variables |
| hewTool | ToolResource type, maintainers and input/output variables; repository reuses CAFE |
| hewCollection | ResourceCollection membership, scope, curator, source project and version |
| hewProject | Program/Project/FundingSource status, program membership, sponsorship, resource use/production and funding mechanism; award/funder reuse citation |
| hewExposureEstimate | SpatiotemporalExposure variable/source references, value specification, population, uncertainty and quality flags |
| hewCalculation | ProcessingMethod name and description, software/version, and external provenance reference |

Common title/identity, discovery, coverage and CAFE mappings apply to every type.
A class with no extra slots, such as CohortResource, shares its parent dataset
block instead of receiving an empty block.

## Source handling and implementation boundary

MongoDB JSON-LD is the dissemination source; LinkML remains the semantic
authority. Normalize only a temporary view and attach the original source
unchanged. Report unsupported values rather than silently discarding them.
Do not persist an intermediate LinkML serialization.

The executable publication crosswalk uses the new blocks for common discovery,
measure rollup, geographic coverage/geometry and temporal
extent. Its contract is in crosswalks/publication/v1/mapping.yaml.
Other resource types have provisioned fields and the mappings above; their
deposit crosswalks remain separate implementation work.

Install with the metadata-block loader documented in the repository README.
Update Solr fields and reload/reindex after provisioning before verifying
facets. The loader preserves unrelated collection block configuration.

### Entity details

The publication crosswalk maps explicit author, contributor, contact, and funding
details to supported citation fields. Contacts require both a name and email;
funding awards require an explicit award number. Identifiers are never presented
as names or award numbers. Other entity-detail objects and unresolved author
identifiers remain in the unchanged HEW source attachment rather than being
projected into a generic entity-reference block.

### Extraction requests are outside catalog metadata

HEW metadata blocks describe cataloged resources and their reported methods and
provenance. Do not add `ExtractionRequest`, requested-variable selections, request
geometries or time windows, execution options, request status, or request tracking
identifiers. These belong in the service that executes the extraction.

`ProcessingMethod` describes how a resource was produced; it does not carry
execution settings or instructions to run a calculation.

### Processing methods

The `hewCalculation` block now displays as HEW Processing Methods and contains
repeatable `hewProcessingMethod` entries. Each entry keeps the method name and
description with software name/identifier/version and a provenance name, citation,
or identifier. Names and citations remain separate from URI/CURIE fields.

This replaces the former method-type, function, parameter JSON, input/output,
join, extraction, and temporal-window fields. Move detailed execution settings
to Amadeus or the originating workflow and link to its provenance record. Source
datasets continue to use CAFE source-data metadata. The publication crosswalk
projects `processing_methods` into the reduced block. Reload metadata definitions
and update Solr before using these fields; existing server metadata requires a
separate migration to retire previously installed fields.

### Review coding stays in the source

The HEW Review Coding block and its fields are no longer provisioned or projected
to Dataverse. Coding schemes, annotation identifiers and dates, coders/reviewers,
evidence, annotation notes, confidence, and review status remain in the original
source attachment. Named references inside review annotations are also source-only.
Annotations can still supply topic concepts for discovery facets. This does not
change the HEW source data model. Existing Dataverse installations need a separate
migration to retire previously installed review fields.

### Retired low-value fields

The discovery-focused cleanup removes the stale affiliation-context field;
duplicate variable-definition, delivery, distribution, and temporal-support JSON;
delivery decoding details (scale factor, offset, missing-value sentinel, CF
cell-method syntax); and legacy standalone variable/property/method/concept/OMOP
fields. Use the repeatable variable-definition, variable-delivery, distribution,
and dataset-temporal-support compounds instead. Their structured names, units,
concept mappings, support, and access links remain available. Orphan vocabulary
rows without a corresponding field definition have also been removed.

Full technical information remains in source attachments and linked data
dictionaries. This cleanup changes the Dataverse projection, not the HEW model.
Reload the metadata definitions and update Solr when deploying. Retiring fields
already installed on a server requires a separate migration of existing values.

### Retired technical detail and operational fields

The medium-priority cleanup retires the agent/provenance block, detailed spatial
support/resolution/grid JSON, the delivery grid-definition pointer, and public
catalog/schema/crosswalk/metadata-block version fields. The HEW model is unchanged.
Version context remains available as `report.processing_context` on the crosswalk
result; the original source attachment remains unchanged. Consumers that retain
operational provenance should save that report with their processing records.

Spatial coverage, geometry, CAFE CRS metadata, temporal support, variable support
summaries, and attribution remain available. `hewSpatialResolution` carries
human-readable numeric or administrative resolution summaries, and
`hewSpatialSupportType` describes the dataset's spatial unit. Full support and
grid structures stay in source metadata or linked data dictionaries. Server-side
retirement and migration of installed fields remain separate deployment work.

### Facet selection

Use facets for normalized categories and human-readable concept labels. Free-text
spatial/temporal coverage, survey versions, administration-time strings, exact
readability scores and question counts, and instrument adaptation references
remain available as metadata without facets. Target-population and research-program
references also remain non-faceted; use normalized population tags and topic labels
for categorization instead of raw entity identifiers or inconsistent names.
Ease-of-use values are retained for interpretation but are non-faceted until a
consistent assessment process supports comparisons across instruments.

This pass disables ten weak facets without removing their values or changing
their advanced-search settings. It does not introduce arbitrary numeric bins or
change the HEW source model. Core concept, geography, resource-type, temporal
resolution, population-tag, and software/tool/model category facets remain.
