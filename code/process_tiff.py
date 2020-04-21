import math
import os
import rasterio
import sys

import datetime
import numpy as np
import rasterio.merge as merge
import xmltodict
import update_credentials
import boto3

from glob import glob
from mgrs import MGRS
from mgrs_converter import lat_lon_boundary
from PIL import Image
from pyhdf.SD import SD, SDC

from rasterio.io import MemoryFile
from rasterio.enums import ColorInterp
from rasterio.warp import calculate_default_transform, reproject, Resampling

from dicttoxml import dicttoxml


class Browse:

    def __init__(self, file_name, GID, params):
        self.file_name = file_name
        self.attributes = {}
        self.bands = ["B04","B03","B02"]
        self.params = params
        self.GIBS_id = GID
        self.prepare()

    def prepare(self):
        """
        Public:
            Handles reprojection of file, conversion of hdf into GeoTIFF
        """
        #data_file = SD(self.file_name, SDC.READ)
        extracted_data = list()
        # resetting crednetials
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
        tiff_file_name = self.prepare_geotiff(extracted_data, file_name)
        self.put_to_grid(tiff_file_name)
        return tiff_file_name

    def prepare_geotiff(self, extracted_data, file_name):
        """
        Public:
            Prepare Geotiff based on extracted_data and store it in file_name
        Args:
            extracted_data - numpy array from granule file
            file_name - Name of the granule file
        """
        tiff_file_name = self.params["intermediate_storage_path"].format(file_name.replace('.{}',''))
        print(tiff_file_name)
        alpha_values = (255 * (extracted_data[:, :, :] != 0).all(0)).astype(rasterio.uint8)
        with MemoryFile() as memfile:
            self.src_profile.update(
                dtype=rasterio.uint8,
                count=self.params['number_of_bands'],
                nodata=0,
                driver='GTiff',
                interleave='pixel',
                compress='deflate'
            )
            with memfile.open(**self.src_profile) as tiff_file:
                for index, data in enumerate(extracted_data, start=1):
                    tiff_file.write(data,index)
                # removing alpha values for now, will revisit this on later time.
                tiff_file.write(alpha_values, self.params['number_of_bands'])
            bands = memfile.open()
            raster_meta = self.rasterio_meta(bands)
            with rasterio.open(tiff_file_name,"w", **raster_meta) as geotiff_file:
                geotiff_file.write(alpha_values, self.params['number_of_bands'])
            print("TIFF file written", tiff_file_name)
            #self.reproject_geotiff(memfile, tiff_file_name)
        return tiff_file_name

    def reproject_geotiff(self, memfile, tiff_file_name):
        """
        Public:
            Reproject GeoTIFF from memfile to tiff_file_name
        Args:
            memfile - rasterio memory file
            tiff_file_name - tiff file being written
        """
        bands = memfile.open()
        src_profile = bands.profile
        raster_meta = self.rasterio_meta(bands)
        with rasterio.open(tiff_file_name, 'w', **raster_meta) as geotiff_file:
            for index in range(1, self.params["number_of_bands"] + 1):
                reproject(
                    source=rasterio.band(bands, index),
                    destination=rasterio.band(geotiff_file, index),
                    src_transform=src_profile['transform'],
                    src_crs=src_profile['crs'],
                    dst_transform=raster_meta['transform'],
                    dst_crs=raster_meta['crs'],
                    resampling=Resampling.bilinear
                )

    def put_to_grid(self, tiff_file_name):
        """
        Public:
            Puts the granules into grid based on lat lon boundary of the file
        Args:
            tiff_file_name - file to be put into grid
        """
        src = rasterio.open(tiff_file_name)
        #raster_meta = self.rasterio_meta(src, bounds)
        #size = [raster_meta['width'], raster_meta['height']]
        file_name = tiff_file_name.split('/')[-1].split('.')
        file_name[2] = self.GIBS_id
        file_name[3] = file_name[3][:7] 
        file_name = '.'.join(file_name)
        print(file_name)
        exit()
        if not os.path.exists(file_name):
            with rasterio.open(file_name, "w", **raster_meta) as output_file:
                for index in list(range(1, 4)):
                    output_file.write(np.zeros((src.profile['width'], src.profile['height'])).astype(rasterio.uint8), index)
        output = rasterio.open(file_name)
        print('merge start')
        data, output_meta = merge.merge([src, output], bounds, (DEST_RES, DEST_RES), nodata=0)
        with rasterio.open(file_name, "w", **raster_meta) as output_file:
            output_file.write(data)
        print('merge done')

    def rasterio_meta(self, src, bounds=None):
        """Form the meta for the new projection using source profile
        Args:
            src (rasterio object): source rasterio.Dataset object
        Returns:
            rasterio.Dataset.profile: modified meta file
        """
        bounds = bounds or src.bounds
        transform, width, height = calculate_default_transform(
            src.crs,
            self.params["destination_CRS"],
            src.width,
            src.width,
            *bounds,
            resolution=(self.params["destination_resolution"], self.params["destination_resolution"])
        )
        meta = src.profile
        meta.update(
            crs=self.params["destination_CRS"],
            transform=transform,
            width=width,
            height=height,
            nodata=0
        )
        return meta

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
        metadata = METADATA_FORMAT
        start_time = self.datetime_from_str(granule_metadata["Granule"]["Temporal"]["RangeDateTime"]["BeginningDateTime"])
        end_time = self.datetime_from_str(granule_metadata["Granule"]["Temporal"]["RangeDateTime"]["EndingDateTime"])
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
                existing_metadata = xmltodict.parse(metadata_file.read())[ROOT_KEY]

            file_start_time = self.datetime_from_str(existing_metadata['DataStartDateTime'])
            file_end_time = self.datetime_from_str(existing_metadata['DataEndDateTime'])

            # overwrite dates if necessary
            start_time = file_start_time if file_start_time < start_time else start_time
            end_time = file_end_time if file_end_time > end_time else end_time

        metadata['DataStartDateTime'] = start_time
        metadata['DataEndDateTime'] = end_time
        metadata['ProductionDateTime'] = created_date

        with open(metadata_file_name, 'wb') as metadata_file:
            metadata_file.write(dicttoxml({ ROOT_KEY: metadata }, root=False, attr_type=False))

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
    def datetime_from_str(cls, datetime_str):
        """
        Public:
            Create datetime object from string
        Args:
            datetime_str - Datetime string in ISO format
        Returns:
            extracted datetime object
        """
        return datetime.datetime.strptime(datetime_str.replace('Z', '')[:26], DATE_PATTERN)

