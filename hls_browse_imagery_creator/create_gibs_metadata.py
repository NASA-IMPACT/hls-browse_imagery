import os
import dicttoxml
import datetime
import glob
import click
from osgeo import gdal


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
    metadata["PartialId"] = gibsid
    metadata["DataStartDateTime"] = min(start_dates)
    metadata["DataEndDateTime"] = max(end_dates)
    metadata["ProductionDateTime"] = datetime.datetime.utcnow().strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    metadata["DataDay"] = day

    with open(outputfile, "wb") as meta_file:
        meta_file.write(
            dicttoxml.dicttoxml(
                {"ImageryMetadata": metadata}, root=False, attr_type=False
            )
        )
