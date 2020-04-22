import math
import os
import rasterio
import sys
import tempfile
import json

import datetime
import numpy as np
import rasterio.merge as merge
import xmltodict
import update_credentials
import boto3

from glob import glob
from PIL import Image

from rasterio.io import MemoryFile
from rasterio.enums import ColorInterp
from rasterio.warp import calculate_default_transform, reproject, Resampling

from dicttoxml import dicttoxml
from pyproj import Proj

class Browse:

    def __init__(self, file_name, GID, params):
        self.file_name = file_name
        self.attributes = {}
        self.bands = ["B04","B03","B02"]
        self.params = params
        self.GIBS_id = GID
        with open("util/GIBS_coordinates.json","r") as json_file:
            GIBS_tiles = json.load(json_file)
        self.bounds = GIBS_tiles[self.GIBS_id]
        print(self.bounds)
        self.tmpfile = self.prepare()

    def prepare(self):
        """
        Public:
            Handles reprojection of file, conversion of hdf into GeoTIFF
        """
        extracted_data = list()
        # resetting credentials
        creds = update_credentials.assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
        for band in self.bands:
            data_file = self.file_name.format(band)
            with rasterio.open(data_file) as src:
                band_data = src.read()
            extracted_data.append(np.squeeze(band_data))
        self.src_profile = src.meta
        extracted_data = np.array(extracted_data)
        low_thresh = math.log(self.params["lower_threshold"])
        high_thresh = math.log(self.params["upper_threshold"])
        low_value = self.params["min_DN"]
        high_value = self.params["max_DN"]
        diff = high_thresh - low_thresh
        extracted_data = np.log(extracted_data)
        extracted_data[np.where(extracted_data <= low_thresh)] = low_value
        extracted_data[np.where(extracted_data >= high_thresh)] = high_value
        indices = np.where(
            (extracted_data > low_thresh) & (extracted_data < high_thresh)
        )
        extracted_data[indices] = (
            high_value * (extracted_data[indices] - low_thresh) / diff
        )
        extracted_data = extracted_data.astype(rasterio.uint8)
        file_name = self.file_name.split('/')[-1]
        tmpfile = self.prepare_geotiff(extracted_data, file_name)
        return tmpfile

    def prepare_geotiff(self, extracted_data, file_name):
        """
        Public:
            Prepare Geotiff based on extracted_data and store it in file_name
        Args:
            extracted_data - numpy array from granule file
            file_name - Name of the granule file
        """
        tiff_file_name = self.params["intermediate_storage_path"].format(file_name.replace('.{}',''))
        alpha_values = (255 * (extracted_data[:, :, :] != 0).all(0)).astype(rasterio.uint8)
         
        print("Starting TIFF file", tiff_file_name, datetime.datetime.utcnow())

        UTMproj = Proj(self.src_profile["crs"])
        min_lon, min_lat = UTMproj(self.bounds[0],self.bounds[1])
        max_lon, max_lat = UTMproj(self.bounds[2],self.bounds[3])
        self.bounds = [min_lon, min_lat, max_lon, max_lat]

        self.src_profile.update(
            dtype=rasterio.uint8,
            count=self.params['number_of_bands'],
            nodata=0,
            driver='GTiff',
            interleave='pixel',
            compress='deflate'
            )
        with rasterio.open(tiff_file_name,"w",**self.src_profile) as tmpfile:
            for index, band in enumerate(extracted_data, start=1):
                tmpfile.write_band(index,band)
            tmpfile.write_band(self.params["number_of_bands"],alpha_values)
        print(tmpfile.bounds)
        print("TIFF file written", tiff_file_name, datetime.datetime.utcnow())
        #self.reproject_geotiff(memfile, tiff_file_name)
        return tiff_file_name

    def reproject_geotiff(self, data, tiff_file_name):
        """
        Public:
            Reproject GeoTIFF from memfile to tiff_file_name
        Args:
            memfile - rasterio memory file
            tiff_file_name - tiff file being written
        """

        with MemoryFile() as memfile:
            with memfile.open(**self.src_profile) as bands:
                bands.write(data)
            print("Memory file written: ", datetime.datetime.utcnow())
            bands = memfile.open()
            nbands, data_height, data_width = data.shape
            print("starting transform: ", datetime.datetime.utcnow())
            transform, width, height = calculate_default_transform(
                    src_crs=self.src_profile["crs"],
                    dst_crs=self.params["destination_CRS"],
                    width=data_width,
                    height=data_height,
                    left = bands.bounds[0],
                    bottom = bands.bounds[1],
                    right = bands.bounds[2],
                    top = bands.bounds[3],
                    resolution=(self.params["destination_resolution"],self.params["destination_resolution"])
                )
            print(bands.bounds)
            print("Finished transform: ", datetime.datetime.utcnow())
            print(transform, width, height)
            self.src_profile.update(
                crs = self.params["destination_CRS"],
                transform=transform,
                width = width,
                height = height,
            )
            exit()
            print("starting reprojection: ", datetime.datetime.utcnow())
            with rasterio.open(tiff_file_name, 'w', **self.src_profile) as geotiff_file:
                for index in range(1, self.params["number_of_bands"] + 1):
                    reproject(
                        source=rasterio.band(bands,index),
                        destination=rasterio.band(geotiff_file, index),
                        src_transform=bands.transform,
                        src_crs=bands.crs,
                        dst_transform=transform,
                        dst_crs=self.params['destination_CRS'],
                        dst_resolution=(self.params["destination_resolution"],self.params["destination_resolution"]),
                        resampling=Resampling.bilinear
                    )
                print(geotiff_file.profile)
            print("finished reprojection: ", datetime.datetime.utcnow())
    def put_to_grid(self, tiff_file_name, files):
        """
        Public:
            Puts the granules into grid based on lat lon boundary of the file
        Args:
            tiff_file_name - file to be put into grid
        """
        tiffs = []
        for file in files:
            tiffs.append(rasterio.open(file,"r"))
        print("Merging now: ", datetime.datetime.utcnow())
        print(self.bounds)
        data, output_meta = merge.merge(tiffs, bounds=self.bounds, nodata=0.0)
        print("Merge complete: ", datetime.datetime.utcnow())
        nbands, height, width = data.shape
        self.src_profile.update(
            transform=output_meta,
            width = width,
            height = height,
        )
        self.reproject_geotiff(data, tiff_file_name)
        self.extract_metadata(tiff_file_name)
        print('merge done')

    def extract_metadata(self, file_name):
        """
        Public:
            Extract metadata from the tiff file together with xml file
                and writes it backout.
        Args:
            file_name - set default values for metadata extracted.
        Returns:
            Dict: { 'ProviderProductId': 'bigger_HLS.L30.T17M.2016005.v1.5.tiff' ... }
        Examples
          browse = Browse(<sampledata>)
          browse.default_value(<merged_product_filename>)
          # => { 'ProviderProductId': 'bigger_HLS.L30.T17M.2016005.v1.5.tiff' ... }
        """
        metadata_file_name = file_name.replace("tiff","xml")
        bucket = self.file_name.split('/')[2]
        key = "/".join(self.file_name.split('/')[3:])
        key = key.format("cmr.xml").replace(".tif","")
        creds = update_credentials.assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
        s3 = boto3.resource('s3',
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken']
            )
        obj = s3.Object(bucket,key)
        granule_metadata = xmltodict.parse(obj.get()["Body"].read().decode('utf-8'))
        metadata = self.params["metadata_template"]
        start_time = self.datetime_from_str(granule_metadata["Granule"]["Temporal"]["RangeDateTime"]["BeginningDateTime"], self.params["date_format"])
        end_time = self.datetime_from_str(granule_metadata["Granule"]["Temporal"]["RangeDateTime"]["EndingDateTime"], self.params["date_format"])
        created_timestamp = os.path.getctime(file_name)
        created_date = datetime.datetime.fromtimestamp(created_timestamp)\
            .replace(tzinfo=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        partial_id, data_day = file_name.split('.')[2:4]
        metadata['ProviderProductId'] = os.path.basename(file_name)
        metadata['PartialId'] = partial_id
        metadata['DataDay'] = data_day.split('T')[0]
        # read data that already exists for the given file
        if os.path.exists(metadata_file_name):
            with open(metadata_file_name) as metadata_file:
                existing_metadata = xmltodict.parse(metadata_file.read())[self.params["root_key"]]

            file_start_time = self.datetime_from_str(existing_metadata['DataStartDateTime'], self.params["date_format"])
            file_end_time = self.datetime_from_str(existing_metadata['DataEndDateTime'], self.params["date_format"])

            # overwrite dates if necessary
            start_time = file_start_time if file_start_time < start_time else start_time
            end_time = file_end_time if file_end_time > end_time else end_time

        metadata['DataStartDateTime'] = start_time
        metadata['DataEndDateTime'] = end_time
        metadata['ProductionDateTime'] = created_date

        with open(metadata_file_name, 'wb') as metadata_file:
            metadata_file.write(dicttoxml({ self.params["root_key"]: metadata }, root=False, attr_type=False))

    @classmethod
    def datetime_to_str(cls, datetime_obj):
        """
        Public:
            Create datetime string from datetime object in UTC time and ISO format
        Args:
            datetime_obj - Datetime object
        Returns:
            extracted datetime object
        """
        return datetime_obj.replace(tzinfo=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

    @classmethod
    def datetime_from_str(cls, datetime_str,date_format):
        """
        Public:
            Create datetime object from string
        Args:
            datetime_str - Datetime string in ISO format
        Returns:
            extracted datetime object
        """
        return datetime.datetime.strptime(datetime_str.replace('Z', '')[:26], date_format)

