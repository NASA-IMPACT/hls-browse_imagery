import os
from osgeo import gdal, osr
import json
import xml.etree.ElementTree as ET

dir_path = os.path.dirname(os.path.realpath(__file__))
gdal.UseExceptions()
gdal.SetConfigOption("GDAL_VRT_ENABLE_PYTHON", "YES")


basedir = "dir_path"
basedir = "/home/ubuntu/hls-browse_imagery/code_new"
basename = "HLS.S30.T01LAH.2020097T222759.v1.5"

with open(os.path.join(basedir, "util", "format_params.json")) as f:
    params = json.load(f)

with open(os.path.join(basedir, "util", "lookup.json")) as f:
    lookup = json.load(f)


# Pixel Function Template
low_thresh = params["lower_threshold"]
high_thresh = params["upper_threshold"]
low_value = params["min_DN"]
high_value = params["max_DN"]

pixelfunc = f"""<![CDATA[
import numpy as np
def threshold(in_ar, out_ar, xoff, yoff, xsize, ysize, raster_xsize,
                raster_ysize, buf_radius, gt, **kwargs):
    low_thresh = np.log({low_thresh})
    high_thresh = np.log({high_thresh})
    low_value = {low_value}
    high_value = {high_value}
    diff = high_thresh - low_thresh
    extracted_data = np.log(in_ar[0])
    extracted_data[np.where(extracted_data <= low_thresh)] = low_value
    extracted_data[np.where(extracted_data >= high_thresh)] = high_value
    indices = np.where(
        (extracted_data > low_thresh) & (extracted_data < high_thresh)
    )
    extracted_data[indices] = (
        high_value * (extracted_data[indices] - low_thresh) / diff
    )
    out_ar = extracted_data
]]>"""


def granule_vrt(basename):
    out_file = "{}-color.vrt".format(basename)
    files = [
        os.path.join(basedir,"files","{}.B04.tif".format(basename)),
        os.path.join(basedir,"files","{}.B03.tif".format(basename)),
        os.path.join(basedir,"files","{}.B02.tif".format(basename)),
    ]
    options = gdal.BuildVRTOptions(separate=True,)
    ds = gdal.BuildVRT(out_file, files, options=options)
    ds = None
    return out_file


def create_gibs_tiles(basename):
    granule = gdal.Open(granule_vrt(basename))
    grid = basename.split(".")[2][1:]
    gibs_tiles = lookup[grid]
    for g in gibs_tiles:
        gid = g["GID"]
        minlon = g["minlon"]
        minlat = g["minlat"]
        maxlon = g["maxlon"]
        maxlat = g["maxlat"]

        vrt_file = "{}_{}.vrt".format(basename, gid)
        pix_file = "{}_{}_pix.vrt".format(basename, gid)
        tif_file = "{}_{}.tiff".format(basename, gid)

        vrt = gdal.Warp(
            vrt_file,
            granule,
            dstSRS="EPSG:4326",
            format="VRT",
            outputBounds=(minlon, minlat, maxlon, maxlat),
            xRes=2.74658203125e-4,
            yRes=2.74658203125e-4,
            srcNodata=-9999,
            dstNodata=0,
            #workingType=gdal.GDT_Int16,
            #outputType=gdal.GDT_Byte,
            srcAlpha=False,
            dstAlpha=True,
        )
        # check statistics to see if there is any data in this tile
        stats = False
        for band in [1, 2, 3]:
            try:
                print(vrt.GetRasterBand(band).GetStatistics(0, 1))
                stats = True
            except:
                print("no pixels found for ", gid)
                break
        vrt = None  # make sure to deallocate memory for layer
        if not stats:
            print("removing ", vrt_file)
            os.unlink(vrt_file)
            continue

        tree = ET.parse(vrt_file)
        for band in tree.findall("VRTRasterBand"):
            ET.SubElement(band, "PixelFunctionType").text = "thresholds"
            ET.SubElement(band, "PixelFunctionLanguage").text = "Python"
            ET.SubElement(band, "PixelFunctionCode").text = pixelfunc
        tree.write(pix_file)

        d = gdal.GetDriverByName("GTiff")
        ds = gdal.Open(pix_file)
        d.CreateCopy(tif_file, ds, 0, ["TILED=YES", "COMPRESS=LZW", "NBITS=8"])
        ds = None
        d = None

    granule = None  # make sure to deallocate memory for layer
