import json
import requests
import xmltodict

from collections import OrderedDict
from shapely.geometry import Polygon

class gibs_mgrs_intersection:


    def __init__(self):
        with open("mgrs_gibs_intersection_params.json", "r") as f:
            params = json.loads(f.read())
        self.s2_params = params["S2"]
        self.gibs_params = params["GIBS"]
        self.lookup_params = params["Lookup"]
        self.GIBS_grid = OrderedDict({"type": "FeatureCollection", "features": []})

        self.S2_HLS_grid = OrderedDict({"type": "FeatureCollection", "features": []})
        self.get_S2_input()
        if self.s2_params["all_s2_tiles"] == "kml":
            self.get_S2grid_from_kml()
        else:
            self.get_S2grid_from_shp()
        self.GIBS_grid = OrderedDict({"type": "FeatureCollection", "features": []})
        self.get_GIBSgrid()
        self.mgrs_gibs_mapping = OrderedDict()
        self.get_intersection()

    def get_S2_input(self):
        self.S2_HLS_grid = OrderedDict({"type": "FeatureCollection", "features": []})
        self.S2_HLS_tiles = set(requests.get(self.s2_params["s2_tile_url"]).text.split("\n"))
        complete_s2_url = self.s2_params[f"{self.s2_params['all_s2_tiles']}_s2_url"]
        S2_all_tiles = requests.get(complete_s2_url)

        if self.s2_params["all_s2_tiles"] == "shp":
            self.S2_input = self.S2_all_tiles.content.decode("iso-8859-1")
        elif self.s2_params["all_s2_tiles"] == "kml":
            self.S2_input = xmltodict.parse(S2_all_tiles.text)
        else:
            print("This code only handles shp and kml as inputs for all_s2_tiles. Exiting.")
            exit()


    def get_S2grid_from_shp(self):
        print("can't figure this out yet")

    def get_S2grid_from_kml(self):
        objects = self.S2_input["kml"]["Document"]["Folder"][0]["Placemark"]
        for obj in objects:
            if obj["name"] in self.S2_HLS_tiles:
                feature = OrderedDict({"type": "Feature", "properties": {"type":"S2"}, "geometry":{}})
                feature["properties"]["identifier"] = obj["name"]
                feature["geometry"]["type"] = "MultiPolygon"
                feature["geometry"]["coordinates"] = []
                polys = obj["MultiGeometry"]["Polygon"]
                polys = [polys] if not isinstance(polys, list) else polys
                for poly in polys:
                    boundary = poly["outerBoundaryIs"]["LinearRing"]["coordinates"].split(" ")
                    coordinates = []
                    for coord in boundary:
                        ll = [float(x) for x in coord.split(",")]
                        coordinates.append([ll[0], ll[1], ll[2]])
                    feature["geometry"]["coordinates"].append([coordinates])
                self.S2_HLS_grid["features"].append(feature)

        if self.s2_params["write_s2_file"]:
            print(f"Writing reference S2 HLS grid to {self.s2_params['output_filepath']}")
            with open(self.s2_params["s2_output_filepath"], "w") as f:
                json.dump(self.S2_HLS_grid,f)

    def get_GIBSgrid(self):
        min_lon = self.gibs_params.get("min_lon", -180)
        min_lat = self.gibs_params.get("min_lat", -90)
        max_lon = self.gibs_params.get("max_lon", 180)
        max_lat = self.gibs_params.get("max_lat", 90)
        resolution = self.gibs_params.get("resolution_in_degrees", None)
        if resolution is None:
            print("resolution is a required field in units of degrees. Exiting now()")
        filename = self.gibs_params.get("GIBS_grid_file_name", "GIBS_grid.json").format(resolution)
        nx = int((max_lon - min_lon)/resolution)
        ny = int((max_lat - min_lat)/resolution)
        for i in range(1, nx+1):
            for j in range(1, ny+1):
                GID = "{0:0>3}".format(i) + "{0:0>3}".format(j)
                coordinates = [[
                [min_lon+(i-1)*resolution, min_lat+(j-1)*resolution],
                [min_lon+(i)*resolution, min_lat+(j-1)*resolution],
                [min_lon+(i)*resolution, min_lat+(j)*resolution],
                [min_lon+(i-1)*resolution, min_lat+(j)*resolution],
                [min_lon+(i-1)*resolution, min_lat+(j-1)*resolution]
                ]]

                feature = OrderedDict()
                feature["type"] = "Feature"
                feature["properties"] = {"identifier": GID}
                feature["geometry"] = {
                              "type": "Polygon",
                              "coordinates": coordinates
                              }
                self.GIBS_grid["features"].append(feature)

        if self.gibs_params["write_gibs_file"]:
            with open(self.gibs_params["gibs_output_file_name"].format(resolution),"w") as f:
                json.dump(self.GIBS_grid,f)

    def get_intersection(self):
        for s2tile in self.S2_HLS_grid["features"]:
            id = s2tile["properties"]["identifier"]
            self.mgrs_gibs_mapping[id] = []
            print(id)
            for poly in s2tile["geometry"]["coordinates"]:
                s2_poly = Polygon(poly[0])
                for gibstile in self.GIBS_grid["features"]:
                    gibs_poly = Polygon(gibstile["geometry"]["coordinates"][0])
                    if gibs_poly.intersects(s2_poly):
                        tile_info = {
                                "GID": gibstile["properties"]["identifier"],
                                "minlon": gibs_poly.bounds[0],
                                "minlat": gibs_poly.bounds[1],
                                "maxlon": gibs_poly.bounds[2],
                                "maxlat": gibs_poly.bounds[3]
                                }
                        self.mgrs_gibs_mapping[id].append(tile_info)
            if len(self.mgrs_gibs_mapping[id]) == 0:
                print(id)
        if self.lookup_params["create_lookup"]:
            with open(self.lookup_params["lookup_output_filepath"], "w") as f:
                json.dump(self.mgrs_gibs_mapping, f)

if __name__ == "__main__":
    gibs_mgrs_intersection()

