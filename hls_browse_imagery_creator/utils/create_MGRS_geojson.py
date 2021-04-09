import fiona
import json
import requests

from collections import OrderedDict
from operator import getitem

with open("mgrs_gibs_intersection_params.json","r") as f:
    params = json.loads(f.read())["S2"]

#Shapefiles downloaded from - https://hub.arcgis.com/datasets/esri::world-utm-grid?geometry=0.000%2C-88.438%2C-0.000%2C88.438
shape = fiona.open(params["path_to_mgrs_shp"])
MGRS_grid = {}
MGRS_grid["type"] = "FeatureCollection"
MGRS_grid["features"] = []

#read in HLS grid
HLStiles = requests.get(params["s2_tile_url"]).text.split("\n")
HLSgrid = set([x[:-2] for x in HLStiles])

#generate MGRS grid geojson file
for tile in shape:
    feature = {}
    tileid = f'{tile["properties"]["ZONE"]:02}{tile["properties"]["ROW_"]}'
    if tileid in HLSgrid:
        feature["type"] = tile["type"]
        feature["properties"] = {
	    "identifier": f'{tile["properties"]["ZONE"]:02}{tile["properties"]["ROW_"]}',
            "type": "MGRS"
        }
        feature["geometry"] = tile["geometry"]
        MGRS_grid["features"].append(feature)

#sort dictionary
MGRS_sorted = sorted(MGRS_grid["features"], key=lambda x:x["properties"]["identifier"])
MGRS_grid["features"] = MGRS_sorted

with open("gibs_reference_layers/MGRS_Grid.json", "w") as f:
    json.dump(MGRS_grid,f)

