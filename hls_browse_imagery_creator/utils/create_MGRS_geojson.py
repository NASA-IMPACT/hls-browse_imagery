import json
import requests
import xmltodict

with open("mgrs_gibs_intersection_params.json", "r") as f:
    params = json.loads(f.read())["S2"]

# UTM dataset available at the following link:
# https://hub.arcgis.com/datasets/esri::world-utm-grid?geometry=0.000%2C-88.438%2C-0.000%2C88.438
utm_tiles = requests.get(params["kml_mgrs_url"]).text
utm_objects = xmltodict.parse(utm_tiles)["kml"]["Document"]["Folder"]["Placemark"]

# initialize MGRS grid dictionary
MGRS_grid = {
    "type": "FeatureCollection",
    "features": []
}

# read in HLS grid
HLStiles = requests.get(params["s2_tile_url"]).text.split("\n")
HLSgrid = set([x[:-2] for x in HLStiles])

# generate MGRS grid geojson file
for obj in utm_objects:
    meta = obj["ExtendedData"]["SchemaData"]["SimpleData"]
    tileid = f'{int(meta[1]["#text"]):02}{meta[2]["#text"]}'
    if tileid in HLSgrid:
        feature = {"type": "Feature"}
        feature["properties"] = {
            "identifier": tileid,
            "type": "MGRS"
        }
        coord_string = obj["Polygon"]["outerBoundaryIs"]["LinearRing"]["coordinates"]
        coord_string = coord_string.split()
        coordinates = []
        for coord in coord_string:
            coordinates.append(tuple([float(x) for x in coord.split(",")]))
        feature["geometry"] = {
            "type": "Polygon",
            "coordinates": [coordinates]
        }
        MGRS_grid["features"].append(feature)

# sort dictionary
MGRS_sorted = sorted(MGRS_grid["features"], key=lambda x: x["properties"]["identifier"])
MGRS_grid["features"] = MGRS_sorted

with open("gibs_reference_layers/MGRS_Grid.json", "w") as f:
    json.dump(MGRS_grid, f)
