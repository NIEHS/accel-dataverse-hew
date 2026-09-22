from __future__ import annotations

import logging

from accelerator_core.utils.xcom_utils import XcomPropsResolver
from accelerator_core.workflow.accel_data_models import DisseminationPayload
from accelerator_core.workflow.accel_target_dissemination import AccelDisseminationComponent

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
