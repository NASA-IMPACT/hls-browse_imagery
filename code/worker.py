import math
import os
import rasterio
import sys

import datetime
import numpy as np
import rasterio.merge as merge
import xmltodict

from glob import glob
from mgrs import MGRS
from mgrs_converter import lat_lon_boundary
from PIL import Image
from pyhdf.SD import SD, SDC

from rasterio.io import MemoryFile
from rasterio.enums import ColorInterp
from rasterio.warp import calculate_default_transform, reproject, Resampling

from dicttoxml import dicttoxml


# Calculation configurations
HIGH_THRES = 7500
HIGH_VAL = 255.

LINEAR_LOW_VAL = 0
LOG_LOW_VAL = math.e
LOW_THRES = 100

LINEAR_STRETCH = 'linear'
LOG_STRETCH = 'log'

STRETCHES = [LINEAR_STRETCH, LOG_STRETCH]


# Instrument based configurations
LANDSAT_ID = 'L30'
SENTINEL_ID = 'S30'


# Image configurations
# based off of Browse Image ICD for GIBS
DEST_RES = 2.74658203125e-4
DST_CRS = { 'init': 'EPSG:4326' }

IMG_SIZE = 1000
NUM_CHANNELS = 4


# File related constants
DATE_PATTERN = '%Y-%m-%dT%H:%M:%S.%f'

METADATA_FORMAT = {
    "ProviderProductId": "",
    "ProductionDateTime": "",
    "DataStartDateTime": "",
    "DataEndDateTime": "",
    "DataDay": "",
    "PartialId": ""
}

ROOT_KEY = 'ImageryMetadata'


# for lambda
FILE_LOCATION = "./{}"
TRUE_COLOR_LOCATION = FILE_LOCATION.format("true_color/{}")

class Browse:

    def __init__(self, file_name, stretch=LINEAR_STRETCH):
        self.file_name = file_name
        if stretch not in STRETCHES:
            exit(0)
        else:
            self.stretch = stretch
        self.attributes = {}
        self.bands = ["B04","B03","B02"]
        self.define_high_low()

    def define_high_low(self):
        """
        Public:
            Define High and Low values as thresholds based on the stretch type defined by user.
        """
        self.high_thres = HIGH_THRES
        self.low_thres = LOW_THRES
        self.low_value = LINEAR_LOW_VAL
        if self.stretch == LOG_STRETCH:
            self.high_thres = math.log(self.high_thres)
            self.low_thres = math.log(self.low_thres)
            self.low_value = LOG_LOW_VAL
        self.diff = self.high_thres - self.low_thres

    def prepare(self):
        """
        Public:
            Handles reprojection of file, conversion of hdf into GeoTIFF
        """
        #data_file = SD(self.file_name, SDC.READ)
        extracted_data = list()
        for band in self.bands:
            data_file = self.file_name.format(band)
            with rasterio.open(data_file) as src:
                band_data = src.read()
            extracted_data.append(np.squeeze(band_data))
        self.src_profile = src.meta
        extracted_data = np.array(extracted_data)
        extracted_data[np.where(extracted_data <= self.low_thres)] = self.low_value
        if self.stretch == LOG_STRETCH:
            extracted_data = np.log(extracted_data)
        extracted_data[np.where(extracted_data >= self.high_thres)] = HIGH_VAL
        indices = np.where(
            (extracted_data > self.low_thres) & (extracted_data < self.high_thres)
        )
        extracted_data[indices] = (
            HIGH_VAL * (extracted_data[indices] - self.low_thres) / self.diff
        )
        extracted_data = extracted_data.astype(rasterio.uint8)
        file_name = self.file_name.split('/')[-1]
        tiff_file_name = self.prepare_geotiff(extracted_data, file_name)
        self.put_to_grid_file_based(tiff_file_name)
        return tiff_file_name

    def prepare_geotiff(self, extracted_data, file_name):
        """
        Public:
            Prepare Geotiff based on extracted_data and store it in file_name
        Args:
            extracted_data - numpy array from granule file
            file_name - Name of the granule file
        """
        tiff_file_name = TRUE_COLOR_LOCATION.format(file_name.replace('.{}',''))
        alpha_values = (255 * (extracted_data[:, :, :] != 0).all(0)).astype(rasterio.uint8)
        with MemoryFile() as memfile:
            self.src_profile.update(
                dtype=rasterio.uint8,
                count=NUM_CHANNELS,
                nodata=0,
                driver='GTiff',
                interleave='pixel',
                compress='deflate'
            )
            with memfile.open(**self.src_profile) as tiff_file:
                for index, data in enumerate(extracted_data, start=1):
                    tiff_file.write(data,index)
                # removing alpha values for now, will revisit this on later time.
                tiff_file.write(alpha_values, NUM_CHANNELS)
            print("TIFF file written")
            self.reproject_geotiff(memfile, tiff_file_name)
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
        print(src_profile)
        raster_meta = self.rasterio_meta(bands)
        print(raster_meta)
        exit()
        with rasterio.open(tiff_file_name, 'w', **raster_meta) as geotiff_file:
            for index in range(1, NUM_CHANNELS + 1):
                reproject(
                    source=rasterio.band(bands, index),
                    destination=rasterio.band(geotiff_file, index),
                    src_transform=src_profile['transform'],
                    src_crs=src_profile['crs'],
                    dst_transform=raster_meta['transform'],
                    dst_crs=raster_meta['crs'],
                    resampling=Resampling.bilinear
                )

    def put_to_grid_file_based(self, tiff_file_name):
        """
        Public:
            Puts the granules into grid based on filenaming convention
        Args:
            tiff_file_name - file to be put into grid
        """
        src = rasterio.open(tiff_file_name)
        file_name = tiff_file_name.split('/')[-1].split('.')
        file_name[2] = file_name[2][0:4]
        file_name[-1] = "tiff" if not file_name[-1].endswith("tiff") else file_name[-1]
        file_name = '.'.join(file_name)
        print(file_name)
        if not os.path.exists(file_name):
            with rasterio.open(file_name, "w", **src.profile) as output_file:
                for index in list(range(1, 4)):
                    output_file.write(np.zeros((src.profile['width'], src.profile['height'])).astype(rasterio.uint8), index)
        #self.extract_metadata(file_name)
        output = rasterio.open(file_name)
        bounds = src.bounds
        bounds = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        bounds[0] = bounds[0] if bounds[0] < output.bounds.left else output.bounds.left
        bounds[1] = bounds[1] if bounds[1] < output.bounds.bottom else output.bounds.bottom
        bounds[2] = bounds[2] if bounds[2] > output.bounds.right else output.bounds.right
        bounds[3] = bounds[3] if bounds[3] > output.bounds.top else output.bounds.top
        data, output_transform = merge.merge([output, src], bounds, (DEST_RES, DEST_RES), nodata=0)
        print('Closing files')
        output.close()
        del(output)
        output_meta = self.rasterio_meta(src, bounds)
        src.close()
        del(src)
        with rasterio.open(file_name, "w", **output_meta) as final_output_file:
            final_output_file.write(data)
        print('merge done')

    def put_to_grid(self, tiff_file_name):
        """
        Public:
            Puts the granules into grid based on lat lon boundary of the file
        Args:
            tiff_file_name - file to be put into grid
        """
        src = rasterio.open(tiff_file_name)
        tile_index = MGRS().toMGRS(src.bounds.top, src.bounds.left, MGRSPrecision=0)
        tile_index = tile_index.decode('utf-8')[:-2]
        bounds = lat_lon_boundary(tile_index)
        raster_meta = self.rasterio_meta(src, bounds)
        size = [raster_meta['width'], raster_meta['height']]
        file_name = tiff_file_name.split('/')[-1].split('.')
        file_name[2] = tile_index
        file_name = '.'.join(file_name)
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
            DST_CRS,
            src.width,
            src.width,
            *bounds,
            resolution=(DEST_RES, DEST_RES)
        )
        meta = src.profile
        meta.update(
            crs=DST_CRS,
            transform=transform,
            width=width,
            height=height,
            nodata=0.0
        )
        return meta

    def default_value(self, file_name):
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
        metadata = METADATA_FORMAT
        sensing_time = self.attributes['SENSING_TIME']
        splitter = '+ ' if '+ ' in sensing_time else '; '
        time_strs = self.attributes['SENSING_TIME'].split('; ')
        start_time = self.datetime_from_str(time_strs[0][:26])
        end_time = self.datetime_from_str(time_strs[-1][:26])
        created_timestamp = os.path.getctime(file_name)
        created_date = datetime.datetime.fromtimestamp(created_timestamp)\
            .replace(tzinfo=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        partial_id, data_day = file_name.split('.')[2:4]
        metadata['ProviderProductId'] = os.path.basename(file_name)
        metadata['PartialId'] = partial_id
        metadata['DataDay'] = data_day
        metadata['DataStartDateTime'] = time_strs[0]
        metadata['DataEndDateTime'] = time_strs[-1]
        metadata['ProductionDateTime'] = created_date
        return metadata, start_time, end_time


    def extract_metadata(self, file_name):
        """
        Public: Extract metadata from the tiff file together with xml file
                and writes it backout.
        Args:
            file_name - Name of the file whose metadata is being created

        Examples
          browse = Browse(<sampledata>)
          browse.extract_metadata()
        """
        print(file_name)
        name_array = self.file_name.split('/')
        print(name_array)
        bucket = name_array[2]
        key = "/".join(name_array[3:])
        metadata_file_name = file_name.replace('.tif', '.xml')

        print(self.attributes['SENSING_TIME'])

        metadata, start_time, end_time = self.default_value(file_name)

        # read data that already exists for the given file
        if os.path.exists(metadata_file_name):
            with open(metadata_file_name) as metadata_file:
                metadata = xmltodict.parse(metadata_file.read())[ROOT_KEY]

        file_start_time = self.datetime_from_str(metadata['DataEndDateTime'])
        file_end_time = self.datetime_from_str(metadata['DataEndDateTime'])

        # overwrite dates if necessary
        file_start_time = start_time if file_start_time > start_time else file_start_time
        file_end_time = end_time if file_end_time < end_time else file_end_time

        metadata['DataStartDateTime'] = self.datetime_to_str(file_start_time)
        metadata['DataEndDateTime'] = self.datetime_to_str(file_end_time)

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


if __name__ == "__main__":
    file_name = sys.argv[1]
    browse = Browse(file_name, stretch='log')
    geotiff_file_name  = browse.prepare()
    print(geotiff_file_name)
