import os

from accelerator_core.utils.accelerator_config import AcceleratorConfig


class DataverseConfig:
    """
    Accelerator configuration for Dataverse
    """

    def __init__(self, dataverse_host:str, api_key:str, dataverse:str):
        self.dataverse_host = dataverse_host # http(s)://hostname[:port]
        self.api_key = api_key # dataverse api key
        self.dataverse = dataverse # dataverse name

    @staticmethod
    def from_env():
        api_key = os.environ.get('DATAVERSE_API_KEY')
        host = os.environ.get('DATAVERSE_HOST')
        dataverse = os.environ.get('DATAVERSE')
        return DataverseConfig(dataverse_host=host, api_key=api_key, dataverse=dataverse)
