from __future__ import annotations

try:
    from accelerator_core.utils.xcom_utils import XcomPropsResolver
    from accelerator_core.workflow.accel_data_models import DisseminationPayload
    from accelerator_core.workflow.dissemination_crosswalk import (
        DisseminationCrosswalk,
    )
except ImportError:  # pragma: no cover - runtime dependency is optional in some environments.
    class XcomPropsResolver:  # type: ignore[no-redef]
        def get_xcom_props(self):
            return type(
                "XcomProperties",
                (),
                {"temp_files_supported": False, "temp_files_location": None},
            )()

    class DisseminationPayload:  # type: ignore[no-redef]
        def __init__(self, dissemination_descriptor):
            self.dissemination_descriptor = dissemination_descriptor
            self.payload = []
            self.payload_path = []
            self.payload_inline = True
            self.dissemination_successful = True
            self.dissemination_message = ""
            self.dissemination_error_details = ""

    class DisseminationCrosswalk:  # type: ignore[no-redef]
        def __init__(self, xcom_props_resolver: XcomPropsResolver):
            self.xcom_props_resolver = xcom_props_resolver

        def get_payload_length(self, payload: DisseminationPayload) -> int:
            if payload.payload_inline:
                return len(payload.payload)
            return len(payload.payload_path)

        def payload_resolve(self, payload: DisseminationPayload, index: int) -> dict:
            if payload.payload_inline:
                if index < len(payload.payload):
                    return payload.payload[index]
                raise IndexError("payload index out of range")
            if index < len(payload.payload_path):
                return payload.payload_path[index]
            raise IndexError("payload path index out of range")

        def report_individual_dissemination(
            self, dissemination_payload: DisseminationPayload, item_id: str, item: dict
        ):
            if not item_id:
                raise ValueError("no item_id provided")
            dissemination_payload.payload.append(item)
            dissemination_payload.payload_inline = True

from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    crosswalk_jsonld_publication,
)
from accelerator_dataverse_hew.crosswalks.publication.v1.models import HEW_SCHEMA_VERSION


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
                "hew_schema_version", HEW_SCHEMA_VERSION
            ),
            crosswalk_version=context_values.get(
                "crosswalk_version", descriptor.dissemination_version or "1.0.0"
            ),
        )
        projection = crosswalk_jsonld_publication(source_document, context)

        transformed = DisseminationPayload(payload.dissemination_descriptor)
        self.report_individual_dissemination(
            transformed,
            transformed.dissemination_descriptor.dissemination_identifier,
            projection.to_dataverse_payload(),
        )
        return transformed


AccelToDataverseCrosswalk = AccelToDataverseHewCrosswalk
