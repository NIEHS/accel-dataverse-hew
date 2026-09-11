import json
import os

from jinja2 import Environment, FileSystemLoader, Template

from accelerator_core.utils.logger import setup_logger

logger = setup_logger("accelerator")


class TemplateProcessor:
    """
    Library for jinja templates for data models
    """

    def __init__(self):
        """
        Initialize ingest tool
        :return:
        """

        # Get the directory of the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_dir = os.path.join(script_dir, "templates")

        # Create a Jinja environment with the FileSystemLoader
        self.env = Environment(loader=FileSystemLoader(script_dir))
        self.env.filters["jsonify"] = json.dumps

    def retrieve_template(self, template_name: str) -> Template:
        """
        retrieve a template from the templates dir
        :param template_name: string with the template name as found in the templates dir, without version or extension
        :param template_version: string in x.x.x form with the version number
        :return: Template for jinja rendering
        """

        return self.env.get_template(f"{template_name}.jinja")
