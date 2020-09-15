import dicttoxml
import datetime
from lxml import etree
from pkg_resources import resource_stream
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

    schema_file = resource_stream("hls_browse_imagery_creator",
                                  "data/schema/ImageMetadata_v1.2.xsd")
    xml = dicttoxml.dicttoxml(
        {"ImageryMetadata": metadata}, root=False, attr_type=False
    )
    xmlschema_doc = etree.parse(schema_file)
    xmlschema = etree.XMLSchema(xmlschema_doc)
    doc = etree.parse(BytesIO(xml))
    xmlschema.assertValid(doc)
    with open(outputfile, "wb") as meta_file:
        meta_file.write(xml)
