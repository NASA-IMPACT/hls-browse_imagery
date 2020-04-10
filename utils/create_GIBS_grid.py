import numpy
import json

from collections import OrderedDict

def create_grid(min_lon,min_lat,max_lon,max_lat,resolution):
    if resolution is None:
        print("resolution is a required field in units of degrees. Exiting now()")
        return
    nx = int((max_lon - min_lon)/resolution)
    ny = int((max_lat - min_lat)/resolution)
    geojson = OrderedDict()
    geojson["type"] = "FeatureCollection"
    geojson["features"] = []
    for i in range(1,nx+1):
        for j in range(1,ny+1):
            GID = f"{i:0>3}""{j:0>3}"
            coordinates = [[
            [min_lon+(i-1)*resolution, min_lat+(j-1)*resolution],
            [min_lon+(i)*resolution, min_lat+(j-1)*resolution],
            [min_lon+(i)*resolution, min_lat+(j)*resolution],
            [min_lon+(i-1)*resolution, min_lat+(j)*resolution],
            [min_lon+(i-1)*resolution, min_lat+(j-1)*resolution]
            ]]

            feature = OrderedDict()
            feature["type"] = "Feature"
            feature["properties"] = {"identifier":GID}
            feature["geometry"] = {
                              "type":"Polygon",
                              "coordinates":coordinates
                              }
            geojson["features"].append(feature)
    with open("GIBS_grid.json","w") as f:
        json.dump(geojson,f)
create_grid(-180,-90,180,90,resolution=1.125)

