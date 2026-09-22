import os
from dataclasses import dataclass

@dataclass
class DataverseConfig:
    """
    Accelerator configuration for Dataverse
    """

    dataverse_host: str
    api_key: str | None
    dataverse: str

    @staticmethod
    def from_env():
        api_key = os.environ.get("DATAVERSE_API_KEY")
        host = os.environ.get("DATAVERSE_HOST", "http://localhost:8081")
        dataverse = os.environ.get("DATAVERSE", "root")
        return DataverseConfig(dataverse_host=host, api_key=api_key, dataverse=dataverse)
