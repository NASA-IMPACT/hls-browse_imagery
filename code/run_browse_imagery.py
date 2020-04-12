import boto3
import gc

import os
import shutil
import update_credentials

from worker import Browse
from glob import glob

# bucket_name = name of the bucket where the hdf files are located
# profile_name = aws profile name.

def download_and_create(bucket_name,prefix,process_dateline):
    processed_files = glob('*.xml')
    creds = update_credentials.assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
    s3 = boto3.resource('s3',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
            )
    bucket = s3.Bucket(bucket_name)
    granule_name_old = None
    count = 0
    for obj in bucket.objects.filter(Bucket=bucket_name,Prefix=prefix):
        granule_name_new = obj.key.split('/')[3]
        if granule_name_new != granule_name_old:
            granule_name_old = granule_name_new
            if (granule_name_new.startswith("HLS.S30.T01") or granule_name_new.startswith("HLS.S30.T60")) and not process_dateline:
                pass
            else:
                count +=1
                file_name = "s3://" + "/".join([bucket_name,obj.key.replace("ACmask","{}")])

                print("running for:", file_name)
                browse = Browse(file_name)
                geotiff_file_name = browse.prepare()
                del(browse)
                print("Done:", geotiff_file_name)
                gc.collect()

def create_and_move_to_folders(extension):
    directories = set()
    for file_name in glob(extension):
        date = file_name.split(".")[3]
        split = file_name.split(".")[1]
        folder_name = f"{split}_NBAR_{date[0:4]}{date[4:7]}/"
        directories.add(folder_name)
        if not(os.path.exists(folder_name)):
            os.mkdir(folder_name)
        print(shutil.move(file_name, folder_name))
    return folder_name

def zip_and_push(folder_name):
    date = folder_name.split("_")[-1][:-1]
    split = folder_name.split("_")[0]
    print(split,date)
    zip_file = folder_name[:-1] + ".tgz"
    os.system("tar -czvf " + zip_file + " " + folder_name +  "*")
    creds = update_credentials.assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
    s3 = boto3.client('s3',
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
            )
    key = "/".join([split,date[0:4],date[4:7],zip_file])
    s3.upload_file(zip_file,"hls-browse-imagery",key)

run_option = "prod"
data_day = "2020097"

buckets = {
        "debug":"hls-debug-output",
        "prod":"hls-global",
        }

prefixes = {
        "debug":"",
        "prod":"S30/data/" + data_day + "/"
        }

# download s30 data and create merged geotiffs.
download_and_create(buckets[run_option], prefix=prefixes[run_option], process_dateline=False)

# move xml files
folder_name = create_and_move_to_folders('*.xml')
# move tiff files
folder_name = create_and_move_to_folders('*.tiff')

#zip and push browse imagery to GCC
zip_and_push(folder_name)
