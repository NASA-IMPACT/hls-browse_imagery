import glob
import rasterio
import rasterio.merge as merge

file_dir = "output_files"
output_dir = "merged"
files = sorted(glob.glob("/".join([file_dir,"*17T*.tif"])))
GIDs = set()

for file in files:
    GIDs.add(file.split("_")[-1].split(".")[0])

for GID in GIDs:
    files = sorted(glob.glob("/".join([file_dir,f"*{GID}*.tif"])))
    tiffs = []
    print(GID)
    for file in files:
        tiffs.append(rasterio.open(file,"r"))
    profile = tiffs[0].profile
    profile.update(count=4,
                nodata=0)
    data, output_meta = merge.merge(tiffs, nodata=0)
    output_file = file.split(".")
    output_file[0] = output_file[0].replace(file_dir,output_dir)
    output_file[2] = GID
    output_file[3] = output_file[3].split("T")[0]
    output_file[5] = output_file[5].split("_")[0]
    output_file[6] = "tiff"
    output_file = ".".join(output_file)
    alpha_values = (255 * (data[:,:,:] != 0).all(0).astype(rasterio.int16))
    with rasterio.open(output_file, "w", **profile) as geotiff_file:
        for index in range(1,profile["count"]):
            geotiff_file.write(data[index-1],index)
        geotiff_file.write(alpha_values,4)
