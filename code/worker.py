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
HIGH_THRES = 1600
HIGH_VAL = 255.

LINEAR_LOW_VAL = 0
LOG_LOW_VAL = 1
LOW_THRES = 100

LINEAR_STRETCH = 'linear'
LOG_STRETCH = 'log'

STRETCHES = [LINEAR_STRETCH, LOG_STRETCH]


# Instrument based configurations
LANDSAT_BANDS = ['band04', 'band03', 'band02']
LANDSAT_ID = 'L30'

SENTINEL_BANDS = ['B04', 'B03', 'B02']
SENTINEL_ID = 'S30'


# Image configurations
# based off of Browse Image ICD for GIBS
DEST_RES = 2.74658203125e-4
DST_CRS = { 'init': 'EPSG:4326' }

IMG_SIZE = 1000
NUM_CHANNELS = 3


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

ROOT_KEY = 'ImageMetadata'


# for lambda
FILE_LOCATION = "./{}"
TRUE_COLOR_LOCATION = FILE_LOCATION.format("true_color/{}")
THUMBNAIL_LOCATION = FILE_LOCATION.format("thumbnails/{}")

class Browse:

    def __init__(self, file_name, stretch=LINEAR_STRETCH):
        self.file_name = file_name
        if stretch not in STRETCHES:
            exit(0)
        else:
            self.stretch = stretch
        self.define_high_low()
        self.select_constelletion()

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

    def select_constelletion(self):
        """
        Public:
            Based on file name of the granule it decides on which bands to use for image generation
        """
        self.bands = LANDSAT_BANDS
        if SENTINEL_ID in self.file_name:
            self.bands = SENTINEL_BANDS

    def prepare(self):
        """
        Public:
            Handles reprojection of file, conversion of hdf into GeoTIFF
        """
        data_file = SD(self.file_name, SDC.READ)
        extracted_data = list()
        for band in self.bands:
            band_data = data_file.select(band)
            extracted_data.append(band_data.get())
        self.attributes = data_file.attributes()
        data_file.end()
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
        thumbnail_file_name = self.prepare_thumbnail(extracted_data, file_name)
        return [tiff_file_name, thumbnail_file_name]

    def prepare_geotiff(self, extracted_data, file_name):
        """
        Public:
            Prepare Geotiff based on extracted_data and store it in file_name
        Args:
            extracted_data - numpy array from granule file
            file_name - Name of the granule file
        """
        thumbnail_file_name = file_name.replace('.hdf', '.png')
        tiff_file_name = TRUE_COLOR_LOCATION.format(file_name.replace('.hdf', '.tiff'))
        # removing alpha values for now, will revisit this on later time.
        # alpha_values = (255 * (extracted_data[:, :, :] == 0).all(0)).astype(rasterio.uint8)
        src_profile = rasterio.open(self.file_name).profile
        with MemoryFile() as memfile:
            src_profile.update(
                dtype=rasterio.uint8,
                count=NUM_CHANNELS,
                nodata=None,
                driver='GTiff',
                interleave='pixel'
            )
            with memfile.open(**src_profile) as tiff_file:
                for index, data in enumerate(extracted_data, start=1):
                    tiff_file.write(data, index)
                # tiff_file.write(alpha_values, NUM_CHANNELS)
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
        raster_meta = self.rasterio_meta(bands, NUM_CHANNELS)

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

    def prepare_thumbnail(self, extracted_data, file_name):
        """
        Public:
            Creates thumbnail of the granule
        Args:
            extracted_date - numpy array of the image
            file_name - Name of the file being opened
        """
        thumbnail_file_name = file_name.replace('.hdf', '.png')
        extracted_data = np.rollaxis(extracted_data, 0, 3)
        img = Image.fromarray(extracted_data)
        thumbnail_file_name = THUMBNAIL_LOCATION.format(thumbnail_file_name)
        img = img.resize((IMG_SIZE, IMG_SIZE))
        img.save(thumbnail_file_name)
        return thumbnail_file_name

    def rasterio_meta(self, src, channel_num):
        """
        Public:
            Puts the granules into grid based on filenaming convention
        Args:
            tiff_file_name - file to be put into grid
        """
        """
        Public:
            Puts the granules into grid based on lat lon boundary of the file
        Args:
            tiff_file_name - file to be put into grid
        """
        """Form the meta for the new projection using source profile
        Args:
            src (rasterio object): source rasterio.Dataset object
            channel_num (integer): number of channels included in the GeoTIFF
        Returns:
            rasterio.Dataset.profile: modified meta file
        """
        transform, width, height = calculate_default_transform(
            src.crs,
            DST_CRS,
            src.width,
            src.width,
            *src.bounds,
            resolution=(DEST_RES, DEST_RES)
        )
        meta = src.profile
        meta.update(
            crs=DST_CRS,
            transform=transform,
            width=width,
            height=height
        )
        return meta

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
        """
        Public: Extract metadata from the tiff file together with xml file
                and writes it backout.
        Args:
            file_name - Name of the file whose metadata is being created

        Examples
          browse = Browse(<sampledata>)
          browse.extract_metadata()
        """

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
    geotiff_file_name, thumbnail_file_name = browse.prepare()
    print(geotiff_file_name)
    print(thumbnail_file_name)
