import json
import math
import numpy as np
import os
import click
import xmltodict
from osgeo import gdal
from pkg_resources import resource_stream
from hls_browse_imagery_creator.create_gibs_metadata import create_gibs_metadata

dir_path = os.path.dirname(os.path.realpath(__file__))
gdal.UseExceptions()

basedir = dir_path

params = json.load(
    resource_stream("hls_browse_imagery_creator", "data/format_params.json")
)

lookup = json.load(
    resource_stream("hls_browse_imagery_creator", "data/mgrs_gibs_intersection.json")
)

# Pixel Function Template
low_thresh = math.log(params["lower_threshold"])
high_thresh = math.log(params["upper_threshold"])
low_value = params["min_DN"]
high_value = params["max_DN"]
thresh_diff = high_thresh - low_thresh


def get_metadata(inpath, granulename):
    meta = os.path.join(inpath, "{}.cmr.xml".format(granulename))
    with open(meta, "r") as infile:
        meta_dict = xmltodict.parse(infile.read())
    dates = meta_dict["Granule"]["Temporal"]["RangeDateTime"]
    start_date = dates["BeginningDateTime"]
    end_date = dates["EndingDateTime"]
    return start_date, end_date


@click.command()
@click.argument("inputdir", type=click.Path(exists=True,))
@click.argument("outputdir", type=click.Path(writable=True,))
@click.argument("basename", type=click.STRING)
def granule_to_gibs(inputdir, outputdir, basename):
    start_date, end_date = get_metadata(inputdir, basename)

    files = [
        os.path.join(inputdir, "{}.B04.tif".format(basename)),
        os.path.join(inputdir, "{}.B03.tif".format(basename)),
        os.path.join(inputdir, "{}.B02.tif".format(basename)),
    ]
    options = gdal.BuildVRTOptions(separate=True,)
    granule = gdal.BuildVRT("", files, options=options)

    mgrs = basename.split(".")[2][1:]
    gibs_tiles = lookup[mgrs]

    for gibs_tile in gibs_tiles:
        gid = gibs_tile["GID"]
        minlon = gibs_tile["minlon"]
        minlat = gibs_tile["minlat"]
        maxlon = gibs_tile["maxlon"]
        maxlat = gibs_tile["maxlat"]

        gibs_tile_dir = os.path.join(outputdir, gid)
        os.mkdir(gibs_tile_dir)
        tif = os.path.join(gibs_tile_dir, "{}_{}.tif".format(basename, gid))
        xml = os.path.join(gibs_tile_dir, "{}_{}.xml".format(basename, gid))
        productid = "{}_{}".format(basename, gid)

        vrt = gdal.Warp(
            tif,
            granule,
            dstSRS="+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",
            format="VRT",
            outputBounds=(minlon, minlat, maxlon, maxlat),
            xRes=2.74658203125e-4,
            yRes=2.74658203125e-4,
            dstAlpha=True,
        )

        cols = vrt.RasterXSize
        rows = vrt.RasterYSize

        d = gdal.GetDriverByName("GTiff")
        out = d.Create(tif, cols, rows, 4, gdal.GDT_Byte, ["TILED=YES", "COMPRESS=LZW"])

        out.SetGeoTransform(vrt.GetGeoTransform())
        out.SetProjection(vrt.GetProjection())

        # Rescale Data
        alpha_arr = np.zeros((cols, rows))
        alpha_arr.fill(255)
        for i in [1, 2, 3]:
            band = vrt.GetRasterBand(i)
            nodata = band.GetNoDataValue()
            arr = band.ReadAsArray()
            nodata_indices = np.where((arr == nodata) | (arr == 0))
            alpha_arr[nodata_indices] = 0
            arr = np.ma.masked_equal(arr, nodata)
            if not np.any(arr):
                out = None
                os.unlink(tif)
                break
            arr = np.ma.log(arr)

            arr[np.where(arr <= low_thresh)] = low_value
            arr[np.where(arr >= high_thresh)] = high_value
            indices = np.where((arr > low_thresh) & (arr < high_thresh))
            arr[indices] = high_value * (arr[indices] - low_thresh) / thresh_diff
            arr[nodata_indices] = 0

            # Write the data out to new band in tif
            new_band = out.GetRasterBand(i)
            new_band.WriteArray(arr, 0, 0)
            new_band.SetNoDataValue(0)
            new_band.GetStatistics(0, 1)

            band = None

        if out is not None:
            new_band = out.GetRasterBand(4)
            new_band.WriteArray(alpha_arr, 0, 0)
            new_band.GetStatistics(0, 1)

            out.SetMetadata(
                {"START_DATE": start_date, "END_DATE": end_date, }
            )
            create_gibs_metadata(productid, xml, gid, start_date, end_date)
        else:
            os.rmdir(gibs_tile_dir)

        out = None
        band = None
        arr = None
        alpha_arr = None

    granule = None  # make sure to deallocate memory for layer
