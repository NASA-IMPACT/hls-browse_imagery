# hls-browse_imagery
## Create and merge GIBS browse imagery for HLS products.

Requirements - Requires a system installation of [gdal](https://github.com/OSGeo/gdal)

Installation
```bash
pip install .
```

Example Usage
```bash
granule_to_gibs inputdir outputdir HLS.S30.T01LAH.2020097T222759.v1.5
```

Run Tests on Python 3.7 
```bash
tox
```
