import os
from osgeo import gdal, osr
import json
import numpy as np
import math
import xml.etree.ElementTree as ET

dir_path = os.path.dirname(os.path.realpath(__file__))
gdal.UseExceptions()

basedir = dir_path

with open(os.path.join(basedir, "util", "format_params.json")) as f:
    params = json.load(f)

with open(os.path.join(basedir, "util", "lookup.json")) as f:
    lookup = json.load(f)


# Pixel Function Template
low_thresh = math.log(params["lower_threshold"])
high_thresh = math.log(params["upper_threshold"])
low_value = params["min_DN"]
high_value = params["max_DN"]
thresh_diff = high_thresh - low_thresh
print(params, low_thresh, high_thresh, low_value, high_value, thresh_diff)


def basepath(basename):
    if os.path.isdir(basename):
        print("found directory", basename)
        return basename

    tstfile = "{}.B04.tif".format(basename)
    if os.path.isfile(tstfile):
        indir = os.path.dirname(tstfile)
        print("found file in directory", indir)
        return indir


def create_gibs_tiles(basename, savevrt=False, outpath=None):
    inpath = basepath(basename)
    granulename = os.path.basename(basename)
    if outpath is None:
        outpath = os.path.join(basedir, "files")
    print('saving data to', outpath)

    if savevrt:
        merge_vrt = os.path.join(outpath, "{}-color.vrt".format(granulename))
    else:
        merge_vrt = ""
    files = [
        os.path.join(inpath, "{}.B04.tif".format(granulename)),
        os.path.join(inpath, "{}.B03.tif".format(granulename)),
        os.path.join(inpath, "{}.B02.tif".format(granulename)),
    ]
    options = gdal.BuildVRTOptions(separate=True,)
    granule = gdal.BuildVRT(merge_vrt, files, options=options)

    grid = granulename.split(".")[2][1:]
    print("finding grid for", grid)
    gibs_tiles = lookup[grid]

    for g in gibs_tiles:
        gid = g["GID"]
        minlon = g["minlon"]
        minlat = g["minlat"]
        maxlon = g["maxlon"]
        maxlat = g["maxlat"]
        if savevrt:
            vrt_file = os.path.join(outpath, "{}_{}.vrt".format(granulename, gid))
        else:
            vrt_file = ""

        tif_file = os.path.join(outpath, "{}_{}.tif".format(granulename, gid))
        print(outpath, tif_file)

        print("creating warped vrt for", gid, minlon, minlat, maxlon, maxlat)
        vrt = gdal.Warp(
            vrt_file,
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
            tif_file, cols, rows, 4, gdal.GDT_Byte, ["TILED=YES", "COMPRESS=LZW"]
        )

        out.SetGeoTransform(vrt.GetGeoTransform())
        out.SetProjection(vrt.GetProjection())

        # Rescale Data
        valid = True
        alpha_arr = np.zeros((cols, rows))
        alpha_arr.fill(255)
        print("stretching bands for ", gid)
        for i in [1, 2, 3]:
            band = vrt.GetRasterBand(i)
            nodata = band.GetNoDataValue()
            arr = band.ReadAsArray()
            nodata_indices = np.where((arr == nodata) | (arr == 0))
            alpha_arr[nodata_indices] = 0
            arr = np.ma.masked_equal(arr, nodata)
            if not np.any(arr):
                print("no data found in band", i, gid)
                out = None
                os.unlink(tif_file)
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

        out = None
        band = None
        arr = None
        alpha_arr = None

    granule = None  # make sure to deallocate memory for layer
