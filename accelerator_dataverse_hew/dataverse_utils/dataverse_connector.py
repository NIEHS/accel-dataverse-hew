from __future__ import annotations

from __future__ import annotations

import json
import time
from urllib.parse import quote

import requests

from accelerator_dataverse_hew.dataverse_utils.dataverse_config import DataverseConfig
from accelerator_dataverse_hew.crosswalks.publication.v1 import (
    CrosswalkContext,
    DataversePublicationProjection,
    crosswalk_jsonld_publication,
)
import logging

logger = logging.getLogger()


class DataverseListing:
    """
    Data structure holding result of a 'list datasets in a dataverse collection'
    """

    def __init__(self):
        self.id = 0
        self.identifier = ""
        self.persistent_url = ""
        self.protocol = ""
        self.authority = ""
        self.separator = "/"
        self.publisher = ""
        self.storage_identifier = ""
        self.dataset_type = ""
        self.type = ""


    @staticmethod
    def from_dict(json_data:dict):
        """
        From a dict representation from the API, return a DataverseListing object.
        :param json_data: dict with entry
        :return: DataverseListing for that entry
        """

        listing = DataverseListing()
        listing.id = json_data["id"]
        listing.identifier = json_data["identifier"]
        listing.persistent_url = json_data["persistentUrl"]
        listing.protocol = json_data["protocol"]
        listing.authority = json_data["authority"]
        listing.separator = json_data["separator"]
        listing.publisher = json_data["publisher"]
        listing.storage_identifier = json_data["storageIdentifier"]
        listing.dataset_type = json_data["datasetType"]
        listing.type = json_data["type"]
        return listing

    def format_pid(self) -> str:
        """Format a persistent identifier for API calls"""
        return "{0}:{1}/{2}".format(self.protocol, self.authority, self.identifier)

class DataverseDisseminationResult:
    """
    Information about storing a dataset in a dataverse collection, including the pid of the dataset
    and any error or reponse information.
    """

    def __init__(
        self,
        pid: str = "",
        success: bool = True,
        message: str = "",
        status_code: int = 0,
        api_url: str = "",
    ):
        self.pid = pid
        self.success = success
        self.message = message
        self.status_code = status_code
        self.api_url = api_url

    @staticmethod
    def from_dict(json_dict:dict):
        result = DataverseDisseminationResult()
        result.pid = json_dict["pid"]
        result.success = json_dict["success"]
        result.message = json_dict["message"]
        result.api_url = json_dict["api_url"]
        result.status_code = json_dict["status_code"]
        return result

    def to_dict(self):
        return {
            "pid": self.pid,
            "success": self.success,
            "message": self.message,
            "api_url": self.api_url,
            "status_code": self.status_code
        }

class AbstractDataverseConnector:
    """
    Abstract superclass for a DataverseConnector. This allows easy mocking and/or integration into
    environments such as Airflow.
    """

    def __init__(self, dataverse_config:DataverseConfig):
        self.dataverse_config = dataverse_config

    def add_dataverse(self, dataverse_collection:DataverseCollection):
       pass


class DataverseConnector(AbstractDataverseConnector):
    """
    Connector to dataverse using Dataverse API
    """
    def __init__(self, dataverse_config:DataverseConfig):
        super().__init__(dataverse_config)
        self.api = NativeApi(dataverse_config.dataverse_host, dataverse_config.api_key)

    def get_version(self):
        resp = self.api.get_info_version()
        return resp

    def add_dataverse(self, dataverse_collection:DataverseCollection):
        logger.info("adding collection: {}".format(dataverse_collection))
        payload = dataverse_collection.render()
        dv = Dataverse()
        dv.from_json(payload)

        resp = self.api.create_dataverse(dataverse_collection.collection_parent, dv.json())
        logger.info("response: {}".format(resp))
        if resp.is_error:
            logger.error("ERROR - Could not create dataverse collection: {}".format(resp))
            raise Exception("ERROR - Could not create dataverse collection: {}".format(resp))

    def delete_dataverse(self, dataverse_id:str, clear_datasets:bool=False) -> bool:
        """
        Idempotent delete of dataverse by alias or id.
        :param dataverse_id: str with dataverse alias or id
        :param clear_datasets: clear datasets before deletion
        :return: bool with True if success
        """

        logger.info(f"delete dataverse with alias: {{dataverse_id}}")

        if clear_datasets:
            logger.info(f"clear datasets before deletion: {{dataverse_id}}")
            datasets = self.list_dataverse_contents(dataverse_id)
            if datasets:
                logger.info("have datasets to delete")
                for dataset in datasets:
                    logger.info(f"delete dataset: {dataset}")
                    self.delete_dataverse_collection(dataset.format_pid())

        try:
            resp = self.api.delete_dataverse(dataverse_id)
            return True
        except DataverseNotFoundError:
            logger.warning("dataverse not found with alias: {}".format(dataverse_id))
            return False
        except DataverseNotEmptyError:
            logger.warning("dataverse not empty of not exists: {}".format(dataverse_id))
            return False


    def verify_target_dataverse(self, dataverse_id:str) -> bool:
        """
        Verify that the target dataverse exists.
        :param dataverse_id: id or alias for target dataverse
        :return: bool of True if target dataverse exists
        """
        logger.info(f"verify target dataverse with alias: {{dataverse_id}}")

        resp = self.api.get_dataverse(dataverse_id)
        logger.info("response: {}".format(resp))
        return resp.is_success

    def list_dataverse_contents(self, dataverse_id:str) -> [DataverseListing]:
        """
        Given the id of a dataverse, list the contents of the dataverse. A not found will return an empty list
        :param dataverse_id: str with dataverse alias or id
        :return: [DataverseListing]
        """

        logger.info(f"listing dataverse contents for {dataverse_id}")
        resp = self.api.get_dataverse_contents(dataverse_id)
        logger.debug("response: {}".format(resp))

        if resp.is_error:
            if resp.status_code == 404:
                logger.warning("not found for dataverse {}".format(dataverse_id))
                return []
            else:
                logger.error("ERROR - Could not list dataverse contents: {}".format(resp))
                raise Exception("ERROR - Could not list dataverse contents: {}".format(resp))

        respdata = json.loads(resp.content)
        listing = []
        for entry in respdata["data"]:
            listing.append(DataverseListing.from_dict(entry))

        return listing

    def delete_dataverse_collection(self, collection_pid):
        """
        Delete a collection.
        :param collection_pid: collection pid to delete
        :return: bool of True if collection was deleted
        """

        logger.info(f"deleting collection {collection_pid}")
        self.api.delete_dataset(collection_pid, is_pid=True)

    def create_dataset(self, dataverse:str, dataverse_dataset:DataverseDataset) -> DataverseDisseminationResult:
        """
        Create a dataverse dataset.
        :param dataverse: dataverse to create collection within
        :param dataverse_dataset: DataverseDataset object with representation of the dataset
        :return: DataverseDisseminationResult
        """

        logger.info(f"create dataset: {dataverse_dataset}")
        payload = dataverse_dataset.render()
        resp = self.api.create_dataset(dataverse, payload, publish=False)
        logger.info("response: {}".format(resp))

        if not resp.is_success:
            logger.error("ERROR - Could not create dataverse dataset: {}".format(resp.content))
            raise Exception("ERROR - Could not create dataverse dataset: {}".format(resp.content))

        dataverse_result = DataverseDisseminationResult()
        resp_txt = json.loads(resp.text)
        dataverse_result.pid = resp.content
        dataverse_result.success = resp.is_success
        dataverse_result.message = resp.text
        dataverse_result.status_code = resp.status_code
        dataverse_result.api_url = resp.url
        dataverse_result.pid = resp_txt["data"]["persistentId"]

        return dataverse_result

    def create_dataset_from_dict(self, dataverse: str, dataverse_dataset_as_dict: dict) -> DataverseDisseminationResult:
        """
        Create a dataverse dataset.
        :param dataverse: dataverse to create collection within
        :param dataverse_dataset_from_dict: dict with representation of the dataset
        :return: DataverseDisseminationResult
        """

        logger.info(f"create dataset: {dataverse_dataset_as_dict}")
        resp = self.api.create_dataset(dataverse, dataverse_dataset_as_dict, publish=False)
        logger.info("response: {}".format(resp))
        if not resp.is_success:
            logger.warning("ERROR - Could not create dataverse dataset: {}".format(resp.content))
            raise Exception("ERROR - Could not create dataverse dataset: {}".format(resp.content))

        dataverse_result = DataverseDisseminationResult()
        resp_txt = json.loads(resp.text)
        dataverse_result.pid = resp.content
        dataverse_result.success = resp.is_success
        dataverse_result.message = resp.text
        dataverse_result.status_code = resp.status_code
        dataverse_result.api_url = f"{resp.url.scheme}://{resp.url.host}{resp.url.path}"
        dataverse_result.pid = resp_txt["data"]["persistentId"]

        return dataverse_result

    def delete_dataset(self, dataset_id:str) -> bool:
        logger.info(f"delete dataset: {dataset_id}")
        resp = self.api.delete_dataset(dataset_id)
        logger.info("response: {}".format(resp))
        return resp.is_success


class DataverseConnector:
    """Small Dataverse API client for HEW publication projections."""

    def __init__(self, dataverse_config: DataverseConfig, session: requests.Session | None = None):
        self.dataverse_config = dataverse_config
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.dataverse_config.api_key:
            headers["X-Dataverse-key"] = self.dataverse_config.api_key
        return headers

    def _response_result(self, response: requests.Response) -> dict:
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            detail = response.text.strip()
            if detail:
                raise requests.HTTPError(
                    f"{error}; response body: {detail}", response=response
                ) from error
            raise
        result = response.json()
        if result.get("status") not in (None, "OK"):
            raise RuntimeError(f"Dataverse request failed: {result}")
        return result

    def create_dataset_from_dict(
        self, dataverse: str, dataverse_dataset: dict, publish: bool = False
    ) -> DataverseDisseminationResult:
        """Create a dataset and optionally publish it as a major release."""
        target = quote(dataverse, safe="")
        response = self.session.post(
            f"{self.dataverse_config.dataverse_host.rstrip('/')}/api/dataverses/{target}/datasets",
            headers=self._headers,
            json=dataverse_dataset,
        )
        result = self._response_result(response)
        data = result.get("data") or {}
        dissemination_result = DataverseDisseminationResult(
            pid=data.get("persistentId", ""),
            success=True,
            message=json.dumps(result),
            status_code=response.status_code,
            api_url=str(response.url),
        )
        if publish:
            publish_url = (
                f"{self.dataverse_config.dataverse_host.rstrip('/')}/api/datasets/"
                ":persistentId/actions/:publish"
            )
            publish_params = {
                "persistentId": dissemination_result.pid,
                "type": "major",
                "assureIsIndexed": "true",
            }
            for attempt in range(30):
                publish_response = self.session.post(
                    publish_url,
                    headers=self._headers,
                    params=publish_params,
                )
                try:
                    publish_result = self._response_result(publish_response)
                    break
                except requests.HTTPError as error:
                    if (
                        publish_response.status_code != 409
                        or "awaiting indexing" not in publish_response.text.lower()
                        or attempt == 29
                    ):
                        raise
                    time.sleep(1)
            dissemination_result.message = json.dumps(publish_result)
            dissemination_result.status_code = publish_response.status_code
            dissemination_result.api_url = str(publish_response.url)
        return dissemination_result

    def create_dataset(
        self,
        dataverse: str,
        projection: DataversePublicationProjection,
    ) -> DataverseDisseminationResult:
        return self.create_dataset_from_dict(dataverse, projection.to_dataverse_payload())

    def crosswalk_publication(
        self,
        document: dict | str,
        context: CrosswalkContext,
    ) -> DataversePublicationProjection:
        """Crosswalk one HEW JSON-LD publication without making API calls."""
        return crosswalk_jsonld_publication(document, context)

    def upload_jsonld_file(
        self,
        dataset_pid: str,
        document: dict | str,
        filename: str = "hew-resource.jsonld",
    ) -> dict:
        """Attach the original HEW JSON-LD document to an existing dataset."""
        content = document if isinstance(document, str) else json.dumps(document, indent=2)
        headers = {}
        if self.dataverse_config.api_key:
            headers["X-Dataverse-key"] = self.dataverse_config.api_key
        response = self.session.post(
            f"{self.dataverse_config.dataverse_host.rstrip('/')}/api/datasets/:persistentId/add",
            headers=headers,
            params={"persistentId": dataset_pid},
            files={"file": (filename, content.encode("utf-8"), "application/ld+json")},
        )
        return self._response_result(response)

    def disseminate_publication(
        self,
        dataverse: str,
        projection: DataversePublicationProjection,
        document: dict | str | None = None,
        filename: str = "hew-resource.jsonld",
    ) -> dict:
        """Disseminate an existing projection and optionally attach its source JSON-LD."""
        dataset_result = self.create_dataset(dataverse, projection)
        result = {"dataset": dataset_result.to_dict()}
        if document is not None:
            result["file"] = self.upload_jsonld_file(dataset_result.pid, document, filename)
        return result
