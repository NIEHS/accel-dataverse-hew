import json
import csv
import logging
from optparse import OptionParser


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s: %(filename)s:%(funcName)s:%(lineno)d: %(message)s"

)
logger = logging.getLogger(__name__)


def convert_json_to_tsv(json_file, tsv_directory):
    with open(json_file, "r") as f:
        blocks = json.load(f)

    for block in blocks["data"]:
        process_block(block, tsv_directory)


def process_block(block, tsv_directory):
    block_name = block["name"]
    fields = block["fields"]
    tsv_file = f"{tsv_directory}/{block_name}.tsv"
    with open(tsv_file, "w", newline="") as tsvfile:
        writer = csv.writer(tsvfile, delimiter="\t")

        # Header row
        writer.writerow([
            "Block Name", "Field Name", "Display Name", "Title",
            "Field Type", "Field TypeClass", "Multiple",
            "Facetable", "Advanced Search Field",
            "Allow Controlled Vocabulary", "Controlled Vocabulary Values"
        ])

        # Write one row per field
        for field in fields.values():
            vocab_values = ",".join(field.get("controlledVocabularyValues", [])) if field.get(
                "isControlledVocabulary") else ""
            writer.writerow([
                block_name,
                field["name"],
                field.get("displayName", ""),
                field.get("title", ""),
                field.get("type", ""),
                field.get("typeClass", ""),
                field.get("multiple", False),
                field.get("facetable", False),
                field.get("advancedSearchField", False),
                field.get("isControlledVocabulary", False),
                vocab_values
            ])


def setup_arguments():
    parser = OptionParser()
    parser.add_option('-i', "--json_input", action='store', dest='json_input', default=None)
    parser.add_option('-t', "--tsv_output_directory", action='store', dest='tsv_output', default=None)

    return parser.parse_args()[0]


def main():
    logger.info('Main function execution started.')
    global args
    args = setup_arguments()

    json_file = args.json_input
    tsv_directory = args.tsv_output

    convert_json_to_tsv(json_file=json_file, tsv_directory=tsv_directory)

if __name__ == "__main__":
    main()