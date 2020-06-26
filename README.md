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
```bash
create_gibs_tile inputdir HLS.S30.T01LAH.2020097.v1.5.tiff T01LAH
```
```bash
generate_metadata inputdir HLS.S30.T01LAH.2020097.v1.5.xml T01LAH HLS.S30.T01LAH.2020097T222759.v1.5 2020097
```

Run Tests on Python 3.7 
```bash
tox
```
