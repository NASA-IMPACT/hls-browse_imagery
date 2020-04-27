# creates lookup that allows to get the GIBS id and bounds from an S2 tile
import geopandas
import json

basedir=""

gibs = geopandas.read_file(f"{basedir}GIBS_grid.json")
gibs.set_index("identifier", inplace=True)
s2 = geopandas.read_file(f"{basedir}S2_grid.json")
s2.set_index("identifier", inplace=True)

j = geopandas.sjoin(gibs, s2, how='inner')
lookup={}
for index, row in j.iterrows():
    minlon, minlat, maxlon, maxlat = row.geometry.bounds
    s2id=row.index_right
    gid=index
    if s2id not in lookup:
        lookup[s2id] = []
    lookup[s2id].append({
        'GID':gid,
        'minlon':minlon,
        'minlat':minlat,
        'maxlon':maxlon,
        'maxlat':maxlat,
    })
with open(f'{basedir}lookup.json', 'w') as outfile:
    json.dump(lookup, outfile)