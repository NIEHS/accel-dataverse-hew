import json

from accelerator_core.utils.data_utils import Serializable

from accelerator_dataverse_hew.dataverse_utils.template_processor import TemplateProcessor

class DataverseCollection(Serializable):
    def __init__(self):
        self.collection_name = ""
        self.collection_alias = ""
        self.dataverse_contacts = []
        self.affiliation = ""
        self.description = ""
        self.dataverse_type = ""
        self.collection_parent = ""

    def render(self):
        template_processor = TemplateProcessor()
        template = template_processor.retrieve_template("dataverse-collection")
        return template.render(collection=self)


class DataverseDataset(Serializable):
    def __init__(self):
        self.protocol = ""
        self.authority = ""
        self.identifier = ""
        self.citation = CitationMetadataBlock()
        self.geospatial = GeospatialMetadataBlock()
        self.computational_workflow = ComputationalWorkflow()
        self.cafe_custom = CafeCustomMetadata()
        self.license = License()
        self.files = []

    def render(self):
        template_processor = TemplateProcessor()
        template = template_processor.retrieve_template("dataset-extended")
        return template.render(dataset=self)

class DataverseCafeSourceDataset(Serializable):
    def __init__(self):
        self.title=""
        self.author=[]
        self.institution=""
        self.version_number=""
        self.doi_or_url=""
        self.last_modified_date=""
        self.date_obtained=""
        self.data_type="Other (specify)" # default to cv value
        self.data_type_other=""
        self.disclaimer=""
        # defer spatial resolution until next round


class DataverseDatasetLicense(Serializable):
    def __init__(self, name, uri):
        self.name = name
        self.uri = uri

class CafeCustomMetadata(Serializable):

    def __init__(self):
        self.derived_from_existing_dataset = False
        self.source_data = [] # DataverseCafeSourceDataset()


class GeospatialMetadataBlock(Serializable):

    def __init__(self):
        self.geographic_unit = []
        self.geographic_bounding_box = None # GeographicBoundingBox() if present


class GeographicBoundingBox(Serializable):

    def __init__(self):
        self.west = ""
        self.east = ""
        self.north = ""
        self.south = ""

class CitationMetadataBlock(Serializable):
    def __init__(self):
        self.display_name = "Citation Metadata"
        self.title = "" # resource.name
        self.subtitle = "" # not used
        self.alternative_title = [] # unused
        self.alternative_url = "" # resource.url
        self.depositor = "" # submission.submitter_name
        self.other_id = [] # unused
        self.author = [] # array of AccelPersonnelModelEntry derived from project sponsor
        self.dataset_contact = [] # duplicate author for now
        self.dataset_description = [] #
        self.subject = [] # hard coded
        self.keyword = [] # resource.resource_keywords
        self.topic_classification = [] # measure
        self.publication = [] # AccelPublicationModel from AccelIntermediateResourceModel.publication
        self.notes_text = "" # resource.description (should I add other textual fields?)
        self.language = [] # skipped for now
        self.producer = [] # skipped for now (redundant with author?)
        self.production_date = "" # skipped for now
        self.production_place = [] # skipped for now
        self.contributor = [] # skipped for now
        self.grant = [] # skipped for now
        self.distributor = [] # skipped for now
        self.distribution_date = "" # skipped for now
        self.date_of_deposit = ""
        self.time_period = [] # data resource time_extent_start and time_extent_end needs to be YYYY-MM-DD
        self.date_of_collection = [] # skipped for now
        self.kind_of_data = [] # use resource type for now
        self.series = [] # skipped for now
        self.software = [] # skipped for now
        self.related_material = [] # resource reference and resource reference link
        self.related_datasets = [] # our data links
        self.other_references = [] # skipped for now
        self.data_sources = [] # skipped may actually be what we are using related_datasets for ???
        self.origin_of_sources = ""
        self.characteristics_of_sources_noted = "" # uses, strengths, limitations are concatenated strings


class CitationAuthor(Serializable):
    def __init__(self):
        self.author_name = ""
        self.author_affiliation = ""
        self.author_identifier_scheme = ""
        self.author_identifier = ""
        self.author_email = "noreply@chordsdata.org"


class DatasetContact(Serializable):
    def __init__(self):
        self.contact_name = ""
        self.contact_affiliation = ""
        self.contact_email = ""


class OtherId(Serializable):
    def __init__(self):
        self.agency = ""
        self.value = ""


class DatasetDescription(Serializable):
    def __init__(self):
        self.description = ""
        self.description_date = ""


class DatasetKeyword(Serializable):
    def __init__(self):
        self.keyword = ""
        self.keyword_uri = ""
        self.vocabulary = ""
        self.vocabulary_uri = ""


class TopicClassification(Serializable):
    def __init__(self):
        self.topic_name = ""
        self.vocabulary = ""
        self.vocabulary_uri = ""


class Publication(Serializable):
    def __init__(self):
        self.publication_relation_type = ""
        self.citation = ""
        self.id_type = ""
        self.id_number = ""
        self.url = ""


class Producer(Serializable):
    def __init__(self):
        self.name = ""
        self.affiliation = ""
        self.abbreviation = ""
        self.url = ""
        self.logo_url = ""


class Contributor(Serializable):
    def __init__(self):
        self.type = ""
        self.name = ""


class Grant(Serializable):
    def __init__(self):
        self.agency = ""
        self.number = ""


class Distributor(Serializable):
    def __init__(self):
        self.name = ""
        self.affiliation = ""
        self.abbreviation = ""
        self.url = ""
        self.logo_url = ""


class TimePeriod(Serializable):
    def __init__(self):
        self.start = ""
        self.end = ""


class Series(Serializable):
    def __init__(self):
        self.name = ""
        self.information = ""


class Software(Serializable):
    def __init__(self):
        self.name = ""
        self.version = ""


class License(Serializable):
    def __init__(self):
        self.name = ""
        self.uri = ""

class ComputationalWorkflow(Serializable):
    def __init__(self):
        self.tool_type = []

class DatasetFile(Serializable):
    def __init__(self):
        self.description = ""
        self.label = ""
        self.restricted = False
        self.version = ""
        self.dataset_version_id = ""
        self.file_id = ""
        self.file_name = ""
        self.content_type = ""
        self.filesize = 0
        self.description = ""
        self.storage_identifier = ""
        self.original_format_label = ""
        self.root_data_file_id = ""
        self.checksum_type = ""
        self.checksum_value = ""
