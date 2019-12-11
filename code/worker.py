import math
import rasterio
import sys

import numpy as np

from glob import glob
from PIL import Image
from pyhdf.SD import SD, SDC

from rasterio.io import MemoryFile
from rasterio.enums import ColorInterp
from rasterio.warp import calculate_default_transform, reproject, Resampling

DST_CRS = { 'init': 'EPSG:4326' }
HIGH_THRES = 1600
LOW_THRES = 100

LINEAR_STRETCH = 'linear'
LOG_STRETCH = 'log'
STRETCHES = [LINEAR_STRETCH, LOG_STRETCH]

LINEAR_LOW_VAL = 0
LOG_LOW_VAL = 1
HIGH_VAL = 255.

LANDSAT_ID = 'L30'
SENTINEL_ID = 'S30'

LANDSAT_BANDS = ['band04', 'band03', 'band02']
SENTINEL_BANDS = ['B04', 'B03', 'B02']

NUM_CHANNELS = 3

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
        self.high_thres = HIGH_THRES
        self.low_thres = LOW_THRES
        self.low_value = LINEAR_LOW_VAL
        if self.stretch == LOG_STRETCH:
            self.high_thres = math.log(self.high_thres)
            self.low_thres = math.log(self.low_thres)
            self.low_value = LOG_LOW_VAL
        self.diff = self.high_thres - self.low_thres

    def select_constelletion(self):
        self.bands = LANDSAT_BANDS
        if SENTINEL_ID in self.file_name:
            self.bands = SENTINEL_BANDS

    def prepare(self):
        data_file = SD(self.file_name, SDC.READ)
        extracted_data = list()
        for band in self.bands:
            band_data = data_file.select(band)
            extracted_data.append(band_data.get())
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
        thumbnail_file_name = file_name.replace('.hdf', '.png')
        tiff_file_name = TRUE_COLOR_LOCATION.format(file_name.replace('.hdf', '.tiff'))
        # removing alpha values for now, will revisit this on later time.
        # alpha_values = (255 * (extracted_data[:, :, :] == 0).all(0)).astype(rasterio.uint8)
        with rasterio.open(self.file_name) as src_file:
            with MemoryFile() as memfile:
                src_profile = src_file.profile
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
                    resampling=Resampling.nearest
                )

    def prepare_thumbnail(self, extracted_data, file_name):
        thumbnail_file_name = file_name.replace('.hdf', '.png')
        extracted_data = np.rollaxis(extracted_data, 0, 3)
        img = Image.fromarray(extracted_data)
        thumbnail_file_name = THUMBNAIL_LOCATION.format(thumbnail_file_name)
        img.save(thumbnail_file_name)
        return thumbnail_file_name

    def rasterio_meta(self, src, channel_num):
        """Form the meta for the new projection using source profile
        Args:
            src (rasterio object): source rasterio.Dataset object
            channel_num (integer): number of channels included in the GeoTIFF
        Returns:
            rasterio.Dataset.profile: modified meta file
        """
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds
        )
        meta = src.profile
        meta.update(
            crs=DST_CRS,
            transform=transform,
            width=width,
            height=height
        )
        return meta

if __name__ == "__main__":
    file_name = sys.argv[1]
    browse = Browse(file_name, stretch='log')
    geotiff_file_name, thumbnail_file_name = browse.prepare()
    print(geotiff_file_name)
    print(thumbnail_file_name)
