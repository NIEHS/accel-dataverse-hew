# Temporal Fields Review

## Removed HEW Fields

The following fields have been removed from the HEW TSV metadata definition and publication crosswalk:

- `temporal_coverage`
- `coverage_status`
- `temporal_join_method`

The HEW Dataverse projection now maps structured temporal intervals and dataset value-support semantics without these fields.

## Remaining Temporal Structure

### Human-Readable Coverage

The free-text `temporal_coverage` field is removed. Structured coverage is the authoritative temporal representation.

### Structured Temporal Extent

Use `temporal_extent` for coverage intervals:

- Inclusive start time
- Exclusive end time

Coverage status is not a catalog field. Coverage timezone is represented by `hewTemporalTimezone`.

### Temporal Timezone

Timezone remains represented in two distinct contexts:

- `hewTemporalTimezone` for coverage timestamps
- `hewDatasetTemporalTimezone` for dataset value intervals

### Temporal Value Support

Use `temporal_support` for the semantics of dataset values:

- Temporal resolution
- Temporal alignment
- Calendar
- Day-boundary convention
- Aggregation window
- Support timezone

## Redundancy and Scope

- `temporal_resolution` belongs to `TemporalSupport`; it is not part of the coverage interval.
- `calendar` belongs to value interpretation and should not be duplicated in coverage metadata.
- `temporal_alignment`, `day_boundary_convention`, and `aggregation_window` describe separate facts and remain independent.
- Delivery-level temporal support and distribution validity remain outside catalog-level Dataverse metadata unless explicitly added to a distribution manifest or technical attachment.

## Crosswalk Behavior

The publication crosswalk still maps:

- Structured temporal start/end
- Dataset temporal resolution
- Calendar
- Temporal alignment
- Day-boundary convention
- Aggregation window
- Coverage timezone
- Dataset support timezone

The crosswalk does not map:

- Human-readable temporal coverage
- Coverage status
- Temporal join method
