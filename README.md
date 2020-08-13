# hls-browse_imagery
## Create and merge GIBS browse imagery for HLS products.

Requirements - Requires a system installation of [gdal](https://github.com/OSGeo/gdal) with Python bindings.

### Installation
```bash
$ pip install .
```

### Example Usage
```bash
$ granule_to_gibs inputdir outputdir HLS.S30.T01LAH.2020097T222759.v1.5
```
```bash
$ create_gibs_tile inputdir HLS.S30.2020097.320071.v1.5 320071 
```
The create_gibs_tile command returns the gibs tile name with the count of sub tiles appended to the file name.
```bash
$ generate_gibs_metadata inputdir HLS.S30.2020097.320071.v1.5.xml HLS.S30.2020097.320071.v1.5.tiff  2020097
```

### Run tests in container
```bash
docker build -t hls-browse_imagery . && docker run hls-browse_imagery
```
