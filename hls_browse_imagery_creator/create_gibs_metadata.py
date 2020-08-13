import os
import dicttoxml
import datetime
import glob
import click
from osgeo import gdal
from lxml import etree
from pkg_resources import resource_stream
from io import BytesIO


@click.command()
@click.argument("inputdir", type=click.Path(exists=True,))
@click.argument("outputfile", type=click.Path(writable=True,))
@click.argument("gibsid", type=click.STRING)
@click.argument("mergefilename", type=click.STRING)
@click.argument("day", type=click.STRING)
def create_gibs_metadata(inputdir, outputfile, gibsid, mergefilename, day):
    pattern = "*_" + gibsid + ".tif"
    globpath = os.path.join(inputdir, pattern)
    files = glob.glob(globpath)
    start_dates = []
    end_dates = []
    for file in files:
        tiff = gdal.Open(file)
        start_dates.append(tiff.GetMetadata()["START_DATE"])
        end_dates.append(tiff.GetMetadata()["END_DATE"])
        tiff = None
    metadata = {}
    metadata["ProviderProductId"] = mergefilename
    metadata["ProductionDateTime"] = datetime.datetime.utcnow().strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    # metadata["PartialId"] = gibsid
    metadata["DataStartDateTime"] = min(start_dates)
    metadata["DataEndDateTime"] = max(end_dates)
    metadata["DataDay"] = day

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
