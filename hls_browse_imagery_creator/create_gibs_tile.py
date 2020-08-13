import os
import glob
import click
from osgeo import gdal


@click.command()
@click.argument("inputdir", type=click.Path(exists=True,))
@click.argument("outputbasename", type=click.STRING)
@click.argument("gibsid", type=click.STRING)
def create_gibs_tile(inputdir, outputbasename, gibsid):
    pattern = "*_" + gibsid + ".tif"
    globpath = os.path.join(inputdir, pattern)
    files = glob.glob(globpath)
    outputfile = outputbasename + "_" + str(len(files)) + ".tif"
    vrt_options = gdal.BuildVRTOptions(resampleAlg="cubic",)
    vrt = gdal.BuildVRT("", files, options=vrt_options)
    driver = gdal.GetDriverByName("GTiff")
    output = driver.CreateCopy(outputfile, vrt, options=["TILED=YES", "COMPRESS=LZW"])
    vrt = None  # Close out the vrt
    output = None  # Needed to flush the tiff to disk
    click.echo(outputfile, nl=False)
