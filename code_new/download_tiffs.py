import boto3
import glob
import os
import s2tile_to_gibstiles as s2toGIBS
import update_credentials

from collections import OrderedDict
import s2tile_to_gibstiles as s2toGIBS

def get_granules(bucket_name, prefix):
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
    for obj in list(bucket.objects.filter(Bucket=bucket_name,Prefix=prefix)):
        granule_name_new = obj.key.split('/')[3]
        if granule_name_new != granule_name_old:
            granule_name_old = granule_name_new
            b02 = obj.key.replace("ACmask","B02")
            bucket.download_file(b02, "files/" + granule_name_new + ".B02.tif")
            b03 = obj.key.replace("ACmask","B03")
            bucket.download_file(b03, "files/" + granule_name_new + ".B03.tif")
            b04 = obj.key.replace("ACmask","B04")
            bucket.download_file(b04, "files/" + granule_name_new + ".B04.tif")
            s2toGIBS.create_gibs_tiles(granule_name_new)
            #os.remove(x) for x in glob.glob("files/" + granule_name_new)

    return granule_name_new

data_day = "2020097"
bucket_name = "hls-global"
product = "S30"
data_type = "data"
granule = "HLS.S30.T17T"
object_path = "/".join([product,data_type,data_day,granule])
granule_list = get_granules(bucket_name,object_path)

