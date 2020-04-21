import boto3
import json
import update_credentials

from collections import OrderedDict
from process_tiff import Browse

def read_mapping(in_grid, out_grid):
    file_name = "util/{}to{}_mapping.json".format(in_grid,out_grid)
    with open(file_name,"r") as f:
        mapping = json.load(f)
    return mapping

def get_S2_tiles(mapping, GID):
    S2tiles = mapping[GID]
    return S2tiles

def get_params(param_file):
    with open(param_file,"r") as f:
        params = json.load(f)
    return params

def get_granule_list(bucket_name, prefix):
    creds = update_credentials.assume_role(
            'arn:aws:iam::611670965994:role/gcc-S3Test',
            'brian_test'
            )
    s3 = boto3.resource('s3',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
            )
    bucket = s3.Bucket(bucket_name)
    granule_name_old = None
    granule_list = OrderedDict()
    for obj in list(bucket.objects.filter(Bucket=bucket_name,Prefix=prefix)):
        granule_name_new = obj.key.split('/')[3]
        if granule_name_new != granule_name_old:
            granule_name_old = granule_name_new
            granule_list[granule_name_new.split(".")[2][1:]] = "s3://" + "/".join([bucket_name,obj.key.replace("ACmask","{}")])

    return granule_list

mapping = read_mapping("S2","GIBS")

GIDs = mapping.keys()

GIBS_params = get_params("util/format_params.json")

data_day = "2020098"
bucket_name = "hls-global"
product = "S30"
data_type = "data"
data_file  = "HLS.S30.T{}"
object_path = "/".join([product,data_type,data_day])
granule_list = get_granule_list(bucket_name,object_path)

for GID in GIDs:
    S2tiles = get_S2_tiles(mapping, GID)
    for tile in S2tiles:
            file_name = granule_list.get(tile, None)
            if file_name is not None:
                file_name = file_name.replace("ACmask","{}")
                Browse(file_name,GID,GIBS_params)
