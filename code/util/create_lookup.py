import json
import datetime

from collections import OrderedDict
from shapely.geometry import Polygon

with open("GIBS_grid.json","r") as f:
    gibs_json = json.load(f)

with open("S2_grid.json","r") as f:
    s2_json = json.load(f)

gibs_features = gibs_json["features"]
s2_features = s2_json["features"]

count = 0
mapping = OrderedDict()
for feature in gibs_features:
    GID = feature["properties"]["identifier"]
    mapping[GID] = set()
    gibs_polygon = Polygon(feature["geometry"]["coordinates"][0])
    for s2_feature in s2_features:
        for geometry in s2_feature["geometry"]["geometries"]:
            s2_polygon = Polygon(geometry["coordinates"][0])
            if s2_polygon.intersects(gibs_polygon):
                mapping[GID].add(s2_feature["properties"]["identifier"])
                break
    mapping[GID] = list(mapping[GID])
    if len(mapping[GID]) == 0:
        del mapping[GID]
    if count % 1000 == 0:
        print("Count: ", count)
        print("GIBS Grid ID: ", GID)
        print(datetime.datetime.utcnow())
    count +=1
with open("S2toGIBS_mapping.json","w") as f:
    json.dump(mapping,f)
