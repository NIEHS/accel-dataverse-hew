from __future__ import annotations

from copy import deepcopy

from accelerator_core.utils.xcom_utils import XcomPropsResolver
from accelerator_core.workflow.accel_data_models import DisseminationPayload
from accelerator_core.workflow.dissemination_crosswalk import DisseminationCrosswalk

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    crosswalk_jsonld_publication,
)


class AccelToDataverseHewCrosswalk(DisseminationCrosswalk):
    """Crosswalk one HEW JSON-LD publication into a Dataverse payload."""

    def __init__(self, xcom_props_resolver: XcomPropsResolver):
        super().__init__(xcom_props_resolver)

    def transform(self, payload: DisseminationPayload) -> DisseminationPayload:
        payload_length = self.get_payload_length(payload)
        if payload_length > 1:
            raise NotImplementedError("HEW Dataverse crosswalk accepts one document")
        if payload_length == 0:
            return payload

        payload_entry = self.payload_resolve(payload, 0)
        source_document = payload_entry.get("data", payload_entry)
        original_source_document = deepcopy(source_document)
        if isinstance(source_document, dict):
            source_document = dict(source_document)
            submission = payload_entry.get("submission")
            if isinstance(submission, dict):
                if submission.get("submitter_email") and not source_document.get("contact_email"):
                    source_document["contact_email"] = submission["submitter_email"]
                if submission.get("submitter_name") and not source_document.get("contact_name"):
                    source_document["contact_name"] = submission["submitter_name"]
        descriptor = payload.dissemination_descriptor
        context_values = descriptor.dissemination_filter or {}
        context = CrosswalkContext(
            catalog_version=context_values.get(
                "catalog_version", descriptor.schema_version or "unknown"
            ),
            metadata_block_version=context_values.get(
                "metadata_block_version", "unknown"
            ),
            target_collection=context_values.get(
                "target_collection", descriptor.dissemination_type or "root"
            ),
            hew_schema_version=context_values.get(
                "hew_schema_version", descriptor.schema_version or "1.2.0"
            ),
            crosswalk_version=context_values.get(
                "crosswalk_version", descriptor.dissemination_version or "1.0.0"
            ),
        )
        projection = crosswalk_jsonld_publication(source_document, context)
        projection.source_jsonld = original_source_document

        transformed = DisseminationPayload(payload.dissemination_descriptor)
        self.report_individual_dissemination(
            transformed,
            transformed.dissemination_descriptor.dissemination_identifier,
            projection.to_dataverse_payload(),
        )
        return transformed


AccelToDataverseCrosswalk = AccelToDataverseHewCrosswalk
