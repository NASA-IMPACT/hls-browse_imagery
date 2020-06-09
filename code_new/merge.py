import boto3
import datetime
import glob
import json
import multiprocessing 
import os
from dicttoxml import dicttoxml
from multiprocessing import Pool
from osgeo import gdal, osr

def generate_metadata(start_dates,end_dates,output_file):
    with open("util/format_params.json","r") as f:
        metadata = json.load(f)["metadata_template"]
    file_params = output_file.split(".")
    metadata["ProviderProductId"] = output_file.split("/")[-1]
    metadata["PartialId"] = file_params[2]
    metadata["DataStartDateTime"] = min(start_dates)
    metadata["DataEndDateTime"] = max(end_dates)
    metadata["ProductionDateTime"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    metadata["DataDay"] = file_params[3]

    with open(output_file.replace("tiff","xml"), "wb") as meta_file:
        meta_file.write(dicttoxml({"ImageryMetadata":metadata},root=False,attr_type=False))

def assume_role(role_arn,role_session_name):
    '''
    This method allows users to assume roles using boto3.
    Requires the role_arn and a session name. Returns
    the credentials dictionary (Note that this is not
    the default dictionary we return creds['Credentials']
    which means extracting the AWS_ACCESS_KEY_ID should be done
    simply by providing ['AccessKeyId']. AWS_SECRET_ACCESS_KEY,
    and AWS_SESSION_TOKEN are extracted similarly using
    ['SecretAccessKey'],['SessionToken'] respectively.
    '''
    client = boto3.client('sts')
    creds = client.assume_role(RoleArn=role_arn, RoleSessionName=role_session_name)
    return creds['Credentials']

def zip_and_push(folder_name, file_name):
    date = file_name.split(".")[3]
    product = file_name.split(".")[1]
    zip_file = "_".join([product,"NBAR", date[0:4],date[4:7]]) + ".tgz"
    os.chdir(folder_name)
    os.system("tar -czvf " + zip_file + " *")
    creds = assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
    s3 = boto3.client('s3',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
            )
    key = "/".join([product,date[0:4],date[4:7],zip_file])
    print(key)
    s3.upload_file(zip_file,"hls-browse-imagery",key)

#for GID in sorted(GIDs):
def merge_files(GID):
    #print("start time: ", datetime.datetime.now())
    files = glob.glob("/".join([file_dir,f"*{GID}*.tif"]))
    start_dates = [] ; end_dates = []
    for file in sorted(files):
        tiff = gdal.Open(file)
        start_dates.append(tiff.GetMetadata()["START_DATE"])
        end_dates.append(tiff.GetMetadata()["END_DATE"])
        tiff = None
    file_string = " ".join(files)
    output_file = files[0].split(".")
    output_file[0] = output_file[0].replace(file_dir,output_dir)
    output_file[2] = GID
    output_file[3] = output_file[3].split("T")[0]
    output_file[5] = output_file[5].split("_")[0]
    output_file[6] = "tiff"
    output_file = ".".join(output_file)
    print(output_file)
    #'''
    vrt_options = gdal.BuildVRTOptions(resampleAlg='cubic',)
    vrt = gdal.BuildVRT("", files, options=vrt_options)
    driver = gdal.GetDriverByName('GTiff')
    output = driver.CreateCopy(output_file, vrt, options=["TILED=YES", "COMPRESS=LZW"])
    vrt = None # Close out the vrt 
    output = None # Needed to flush the tiff to disk
    #print("end time: ", datetime.datetime.now())
    '''
    command = "gdal_merge.py -o " + output_file + " -of gtiff -co TILED=YES -co COMPRESS=LZW " + file_string
    os.system(command)
    print("end time: ", datetime.datetime.now())
    '''
    generate_metadata(start_dates, end_dates, output_file)
    return output_file

file_dir = "output_files"
output_dir = "merged"
files = glob.glob("/".join([file_dir,"*.tif"]))
GIDs = set()

for file in sorted(files):
        GIDs.add(file.split("_")[-1].split(".")[0])
start = f"Processing started: {datetime.datetime.now()}"
p = Pool(1)
with p:
    output_file = p.map(merge_files,GIDs)

zip_and_push(output_dir, output_file)
end = f"Processing finished: {datetime.datetime.now()}"
print(start)
print(end)
