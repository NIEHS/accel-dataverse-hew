# HEW Dataverse Metadata Blocks

## Authority and scope

The design follows [metadata_blocks_design_notes.md](metadata_blocks_design_notes.md),
HEW_Catalog_Data_Model schema 2.0.0 (hew-model/schema/hew.yaml and its modules),
and HEW_Measures vocabulary 1.0.0 (data/HewMeasures.yaml).
These are fresh block definitions; there are no legacy HEW aliases or migration fields.

The provisioning assets are cafe_custom.tsv and hew_custom.tsv. The loader
installs every custom block and enables them together with the installed
Dataverse citation and geospatial blocks. Empty optional blocks are not emitted
for individual records.

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
publication a derived dataset. The publication crosswalk defaults both required
CAFE indicators to No when the source provides no evidence.

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
| Record type | hewResourceType | hewResourceTypeCurie, hewResourceTypeAlias, hewResourceTypeExactMapping |
| Exposure | hewExposureConcept | hewExposureCurie, hewExposureAlias, hewExposureExactMapping |
| Health impact | hewHealthImpactConcept | hewHealthImpactCurie, hewHealthImpactAlias, hewHealthImpactExactMapping |
| Geography | hewGeographyConcept | hewGeographyCurie, hewGeographyAlias, hewGeographyExactMapping |
| Topic/theme | hewTopicConcept | hewTopicCurie, hewTopicAlias, hewTopicExactMapping |
| Event | hewEventConcept | hewEventCurie, hewEventAlias, hewEventExactMapping |
| Data/tool | hewDataToolConcept | hewDataToolCurie, hewDataToolAlias, hewDataToolExactMapping |
| Model | hewModelConcept | hewModelCurie, hewModelAlias, hewModelExactMapping |

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
identifiers, environmental context labels/CURIEs, grid definitions, detailed
quantitative/administrative resolution, and variable spatial support.
Resource-level extent and variable-level support have distinct meanings.
CRS/file metadata uses CAFE fields first.

hewTemporal carries free-text coverage and repeated hewTemporalExtent compounds
with start/end timestamps, resolution, calendar, timezone, and coverage status.
Timestamps remain text so UTC offsets and sub-day precision survive; start is
inclusive and end exclusive. The publication crosswalk validates explicit
offsets and interval ordering. Variable temporal support, update cadence and
typical latency have separate fields. Date-only project/association periods
retain their source precision rather than inventing times.

Detailed nested support, grid, variable, distribution, parameter, and value
specifications use explicitly named JSON textbox fields where further compound
nesting would obscure relationships. Preserve complete source JSON-LD as well.

## Remaining type-specific information

| Block | Classes/content not covered above |
|---|---|
| hewResource | Catalog resource ID, status, related resources, schema/catalog/crosswalk/block versions |
| hewPublication | LiteratureResource study objective; bibliographic fields reuse citation |
| hewReview | Review identifiers, coding scheme/version, dates, coders/reviewers, evidence, notes and confidence |
| hewDataResource | DatasetResource/CohortResource/SurveyDataset data dictionary, variables, survey instruments, population, deliveries, distributions, processing and OMOP linkage |
| hewSurvey | SurveyInstrument constructs/questions, population, administration, EDC, readability, CDE integration and instrument relationships |
| hewProvenance | Agents and role-bearing associations; identifiers, entity, role, association dates, affiliation, contribution and source |
| hewSoftware | SoftwareResource language, software type and maintainers; repository/documentation reuse CAFE |
| hewModelResource | ModelResource type and input/output variables |
| hewTool | ToolResource type, maintainers and input/output variables; repository reuses CAFE |
| hewCollection | ResourceCollection membership, scope, curator, source project and version |
| hewProject | Program/Project/FundingSource status, program membership, sponsorship, resource use/production and funding mechanism; award/funder reuse citation |
| hewExposureEstimate | SpatiotemporalExposure variable/source references, value specification, population, uncertainty and quality flags |
| hewCalculation | CovariateCalculation method, software, parameters, inputs/outputs, joins, buffers, extraction and temporal window |

Common title/identity, discovery, coverage and CAFE mappings apply to every type.
A class with no extra slots, such as CohortResource, shares its parent dataset
block instead of receiving an empty block.

## Source handling and implementation boundary

MongoDB JSON-LD is the dissemination source; LinkML remains the semantic
authority. Normalize only a temporary view and attach the original source
unchanged. Report unsupported values rather than silently discarding them.
Do not persist an intermediate LinkML serialization.

The executable publication crosswalk uses the new blocks for common discovery,
measure rollup, coding provenance, geographic coverage/geometry and temporal
extent. Its contract is in crosswalks/publication/v1/mapping.yaml.
Other resource types have provisioned fields and the mappings above; their
deposit crosswalks remain separate implementation work.

Install with the metadata-block loader documented in the repository README.
Update Solr fields and reload/reindex after provisioning before verifying
facets. The loader preserves unrelated collection block configuration.
