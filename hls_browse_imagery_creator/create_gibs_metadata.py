import dicttoxml
import datetime
from lxml import etree
try:
    from importlib.resources import files as resource_files
except ImportError:  # Python < 3.9
    from importlib_resources import files as resource_files
from io import BytesIO


def create_gibs_metadata(productid, outputfile, gibsid, start_date, end_date):
    metadata = {}
    metadata["ProviderProductId"] = productid
    metadata["ProductionDateTime"] = datetime.datetime.utcnow().strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    metadata["DataStartDateTime"] = start_date
    metadata["DataEndDateTime"] = end_date
    date = datetime.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ")
    year = date.year
    day_of_year = date.timetuple().tm_yday
    day = str(day_of_year).zfill(3)
    metadata["DataDay"] = "{}{}".format(year, day)
    metadata["PartialId"] = gibsid

    xml = dicttoxml.dicttoxml(
        {"ImageryMetadata": metadata}, root=False, attr_type=False
    )
    schema_resource = resource_files("hls_browse_imagery_creator").joinpath(
        "data/schema/ImageMetadata_v1.2.xsd"
    )
    with schema_resource.open("rb") as schema_file:
        xmlschema_doc = etree.parse(schema_file)
    xmlschema = etree.XMLSchema(xmlschema_doc)
    doc = etree.parse(BytesIO(xml))
    xmlschema.assertValid(doc)
    with open(outputfile, "wb") as meta_file:
        meta_file.write(xml)
