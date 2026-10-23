# Metadata Blocks Design Notes

This documents the strategy for dataverse metadata blocks and gives guidance for design/implementation

## Principles

* We will maintain the maximal provisioning of the cafe custom metadata blocks
* We will focus on commonality between the types in the HEW catalog, so broad facets, measures are available, make facets and general classificiations available in a common block across hew types
* where a cafe metadata block field is available, crosswalk to that field
* where the hew model includes curies, utilize the plain text versions for facets and populating the metadata blocks

## Metadata block design

* where available, populate the cafe metadata block fields
* create a hew discovery metadata block for terms and term mappings, where facets are made available for the major enumerated HEW types including the record type, exposure, health impact, geography and topic concept. For those types, include the plain text version as a facet, add separate fields for curies, aliases and exact mappings to other vocabularies as curies
* for HEW measures, create a rollup by matching the HEW measures curie back tot he HEW_Measures, such that the parent terms are populated for a facet rollup and presented in the discovery metadata block
* Add a geospatial metadata block to carry geospatial information
* add a temporal metadata block to casrry temporal information
* add blocks to carry the information from each hew type that does not map to the above defined metadata blocks
