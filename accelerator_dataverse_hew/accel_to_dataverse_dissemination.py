from __future__ import annotations

import logging

try:
    from accelerator_core.utils.xcom_utils import XcomPropsResolver
    from accelerator_core.workflow.accel_data_models import DisseminationPayload
    from accelerator_core.workflow.accel_target_dissemination import (
        AccelDisseminationComponent,
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

    class AccelDisseminationComponent:  # type: ignore[no-redef]
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

from accelerator_dataverse_hew.dataverse_utils.dataverse_config import DataverseConfig
from accelerator_dataverse_hew.dataverse_utils.dataverse_connector import DataverseConnector


logger = logging.getLogger("accelerator-dataverse-hew")


class AccelDataverseHewDissemination(AccelDisseminationComponent):
    """Disseminate one crosswalked HEW publication to Dataverse."""

    def __init__(self, xcom_props_resolver: XcomPropsResolver):
        super().__init__(xcom_props_resolver)

    def disseminate(
        self, dissemination_payload: DisseminationPayload, additional_parameters: dict
    ) -> DisseminationPayload:
        logger.info(
            "disseminate with descriptor %s",
            dissemination_payload.dissemination_descriptor,
        )
        dataverse_config = DataverseConfig(
            dataverse_host=additional_parameters["dataverse_host"],
            api_key=additional_parameters["api_key"],
            dataverse=additional_parameters["dataverse"],
        )
        dataverse_connector = DataverseConnector(dataverse_config)

        payload_length = self.get_payload_length(dissemination_payload)
        if payload_length > 1:
            raise NotImplementedError(
                f"dissemination payload length {payload_length} > 1"
            )
        if payload_length == 0:
            logger.warning("dissemination payload is empty")
            return dissemination_payload

        payload_document = self.payload_resolve(dissemination_payload, 0)
        result = dataverse_connector.create_dataset_from_dict(
            dataverse_config.dataverse, payload_document, publish=True
        )

        dissemination_payload.dissemination_successful = True
        dissemination_payload.payload_inline = True
        dissemination_payload.payload = [result.to_dict()]
        return dissemination_payload
