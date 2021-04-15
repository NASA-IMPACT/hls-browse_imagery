import json
import requests
import xmltodict

from collections import OrderedDict

with open("mgrs_gibs_intersection_params.json", "r") as f:
    params = json.load(f)["S2"]

S2_kml = requests.get(params["kml_s2_url"]).text
s2_tiles = xmltodict.parse(S2_kml)
objects = s2_tiles["kml"]["Document"]["Folder"][0]["Placemark"]
s2_grid = {
    "type": "FeatureCollection",
    "features": []
}

S2_HLS_tiles = requests.get(params["s2_tile_url"]).text.split("\n")

for obj in objects:
    if obj["name"] in S2_HLS_tiles:
        feature = OrderedDict({"type": "Feature",
                               "properties": {"type": "S2"},
                               "geometry": {}
                               })
        feature["properties"]["identifier"] = obj["name"]
        feature["geometry"]["type"] = "MultiPolygon"
        feature["geometry"]["coordinates"] = []
        polys = obj["MultiGeometry"]["Polygon"]
        polys = [polys] if not isinstance(polys, list) else polys

        for poly in polys:
            boundary = poly["outerBoundaryIs"]["LinearRing"]["coordinates"]
            boundary = boundary.split(" ")
            coordinates = []
            for coord in boundary:
                ll = [float(x) for x in coord.split(",")]
                coordinates.append([ll[0], ll[1], ll[2]])
            feature["geometry"]["coordinates"].append([coordinates])
        s2_grid["features"].append(feature)

# sort dictionary
S2_sorted = sorted(s2_grid["features"], key=lambda x: x["properties"]["identifier"])
s2_grid["features"] = S2_sorted

with open("gibs_reference_layers/s2_grid.json", "w") as f:
    json.dump(s2_grid, f)
