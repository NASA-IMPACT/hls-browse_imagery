import boto3
import json
import math
import numpy as np
import os
import xml.etree.ElementTree as ET
import xmltodict

from botocore.exceptions import ClientError
from osgeo import gdal, osr

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
#print(params, low_thresh, high_thresh, low_value, high_value, thresh_diff)


def basepath(basename):
    if os.path.isdir(basename):
        #print("found directory", basename)
        return basename

    tstfile = "files/{}.B04.tif".format(basename)
    if os.path.isfile(tstfile):
        indir = os.path.dirname(tstfile)
        #print("found file in directory", indir)
        return indir

def get_metadata(inpath, granulename):
    meta = os.path.join(inpath, "{}.cmr.xml".format(granulename))
    with open(meta,"r") as infile:
        meta_dict = xmltodict.parse(infile.read())
    dates = meta_dict["Granule"]["Temporal"]["RangeDateTime"]
    start_date = dates["BeginningDateTime"]
    end_date = dates["EndingDateTime"]
    return start_date, end_date

def assume_role(role_arn,role_session_name):
    client = boto3.client('sts')
    creds = client.assume_role(RoleArn=role_arn, RoleSessionName=role_session_name)
    return creds['Credentials']

def movetoS3(tempfile,bucket,tif_file):
    creds = assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
    client = boto3.client('s3',
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken']
        )
    try:
        response = client.upload_file(tempfile,bucket,tif_file)
        os.remove(tempfile)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_gibs_tiles(basename, savevrt=False, local=True, bucket=None, outpath=None):
    inpath = basepath(basename)
    granulename = os.path.basename(basename)
    start_date, end_date = get_metadata(inpath, granulename)
    if outpath is None:
        output_path = os.path.join(basedir, "output_files")
    else:
        output_path = outpath
    if local == False:
        filename_components = basename.split(".")
        product = filename_components[1]
        date = filename_components[3].split("T")[0]
        yyyy = date[0:4]
        ddd = date[4:7]
        output_path = "/".join([product, yyyy, ddd, outpath])
        bucket_name = bucket

    #print('saving data to', outpath)

    if savevrt == True:
        merge_vrt = os.path.join(output_path, "{}-color.vrt".format(granulename))
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
    #print("finding grid for", grid)
    gibs_tiles = lookup[grid]

    for g in gibs_tiles:
        gid = g["GID"]
        minlon = g["minlon"]
        minlat = g["minlat"]
        maxlon = g["maxlon"]
        maxlat = g["maxlat"]
        if savevrt == True:
            vrt_file = os.path.join(output_path, "{}_{}.vrt".format(granulename, gid))
        else:
            vrt_file = ""

        tif_file = os.path.join(output_path, "{}_{}.tif".format(granulename, gid))
        if local == False:
            tempfile = "{}_{}.tif".format(granulename, gid)
            tempvrt = ""
        #print(outpath, tif_file)

        #print("creating warped vrt for", gid, minlon, minlat, maxlon, maxlat)
        vrt = gdal.Warp(
            tempvrt,
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
            tempfile, cols, rows, 4, gdal.GDT_Byte, ["TILED=YES", "COMPRESS=LZW"]
        )

        out.SetGeoTransform(vrt.GetGeoTransform())
        out.SetProjection(vrt.GetProjection())

        # Rescale Data
        valid = True
        alpha_arr = np.zeros((cols, rows))
        alpha_arr.fill(255)
        #print("stretching bands for ", gid)
        for i in [1, 2, 3]:
            band = vrt.GetRasterBand(i)
            nodata = band.GetNoDataValue()
            arr = band.ReadAsArray()
            nodata_indices = np.where((arr == nodata) | (arr == 0))
            alpha_arr[nodata_indices] = 0
            arr = np.ma.masked_equal(arr, nodata)
            if not np.any(arr):
                #print("no data found in band", i, gid)
                out = None
                os.unlink(tempfile)
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
                    {
                        "START_DATE": start_date,
                        "END_DATE": end_date,
                }
            )

            result = movetoS3(tempfile, bucket, tif_file)

        out = None
        band = None
        arr = None
        alpha_arr = None

    granule = None  # make sure to deallocate memory for layer
