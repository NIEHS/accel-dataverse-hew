# HEW publication crosswalk v1

Projects HEW Catalog Data Model 2.0.0 LiteratureResource JSON-LD or catalog
exports into the fresh HEW block design. See [mapping.yaml](mapping.yaml) and
[metadata blocks guidance](../../../metadata_blocks_guidance.md).

Required source fields are id (or @id), title and resource_type: literature.
JSON-LD documents require a supported HEW context. Inlined authors project
their names and ORCID identifiers; publication dates support YYYY, YYYY-MM
and YYYY-MM-DD.

The projection emits citation, hewResource, hewDiscovery and the required CAFE
indicators. It emits hewPublication only for study_objective, hewReview for
coding provenance/evidence, geographic and temporal blocks for supplied
coverage, and cafeDatasetTerms for exact vocabulary matches.

Discovery uses plain-text labels, with separate CURIE, alias and exact-mapping
fields. Known HEWM CURIEs use the pinned HEW_Measures snapshot to supply labels,
aliases, exact mappings and all taxonomy parent facets except Category.
Explicit preferred labels take precedence over vocabulary titles. Unknown
identifiers without labels are reported and never used as facets.

The preservation attachment is the original source, unchanged. Vocabulary
enrichment belongs only to the projection. License and access-rights fields
are reported as requiring dataset-level configuration.

Provision all blocks using the metadata loader described in the repository
README, then update Solr. Supply catalog_version, metadata_block_version and
target_collection in CrosswalkContext. The output records schema, catalog,
crosswalk and metadata-block versions in hewResource.
