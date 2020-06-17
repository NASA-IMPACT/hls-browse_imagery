import json
import math
import numpy as np
import os
import click
import xmltodict
from osgeo import gdal

dir_path = os.path.dirname(os.path.realpath(__file__))
gdal.UseExceptions()

basedir = dir_path

with open(os.path.join(basedir, "data", "format_params.json")) as f:
    params = json.load(f)

with open(os.path.join(basedir, "data", "mgrs_gibs_intersection.json")) as f:
    lookup = json.load(f)


# Pixel Function Template
low_thresh = math.log(params["lower_threshold"])
high_thresh = math.log(params["upper_threshold"])
low_value = params["min_DN"]
high_value = params["max_DN"]
thresh_diff = high_thresh - low_thresh
# print(params, low_thresh, high_thresh, low_value, high_value, thresh_diff)


def get_metadata(inpath, granulename):
    meta = os.path.join(inpath, "{}.cmr.xml".format(granulename))
    with open(meta, "r") as infile:
        meta_dict = xmltodict.parse(infile.read())
    dates = meta_dict["Granule"]["Temporal"]["RangeDateTime"]
    start_date = dates["BeginningDateTime"]
    end_date = dates["EndingDateTime"]
    return start_date, end_date


@click.command()
@click.argument('inputdir', type=click.Path(exists=True,))
@click.argument('outputdir', type=click.Path(writable=True,))
@click.argument('basename', type=click.STRING)
def granule_to_gibs(inputdir, outputdir, basename):
    start_date, end_date = get_metadata(inputdir, basename)

    # if savevrt:
        # merge_vrt = os.path.join(outputdir, "{}-color.vrt".format(basename))
    # else:
        # merge_vrt = ""
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

        tif = os.path.join(outputdir, "{}_{}.tif".format(basename, gid))
        # print(outpath, tif_file)

        # print("creating warped vrt for", gid, minlon, minlat, maxlon, maxlat)
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
        out = d.Create(
            tif, cols, rows, 4, gdal.GDT_Byte, ["TILED=YES", "COMPRESS=LZW"]
        )

        out.SetGeoTransform(vrt.GetGeoTransform())
        out.SetProjection(vrt.GetProjection())

        # Rescale Data
        alpha_arr = np.zeros((cols, rows))
        alpha_arr.fill(255)
        # print("stretching bands for ", gid)
        for i in [1, 2, 3]:
            band = vrt.GetRasterBand(i)
            nodata = band.GetNoDataValue()
            arr = band.ReadAsArray()
            nodata_indices = np.where((arr == nodata) | (arr == 0))
            alpha_arr[nodata_indices] = 0
            arr = np.ma.masked_equal(arr, nodata)
            if not np.any(arr):
                # print("no data found in band", i, gid)
                out = None
                os.unlink(tif)
                break
            arr = np.ma.log(arr)

            arr[np.where(arr <= low_thresh)] = low_value
            arr[np.where(arr >= high_thresh)] = high_value
            indices = np.where((arr > low_thresh) & (arr < high_thresh))
            arr[indices] = high_value * (arr[indices] - low_thresh) / thresh_diff
            arr[nodata_indices] = 0

            # write the data out to new band in tif
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

        out = None
        band = None
        arr = None
        alpha_arr = None

    granule = None  # make sure to deallocate memory for layer
