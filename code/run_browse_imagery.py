import boto3
import gc

import os
import shutil
import update_credentials

from worker import Browse
from glob import glob

# bucket_name = name of the bucket where the hdf files are located
# profile_name = aws profile name.

def download_and_create(bucket_name,prefix=''):
    processed_files = glob('*.xml')
    #creds = update_credentials.assume_role('arn:aws:iam::611670965994:role/gcc-S3Test','brian_test')
    s3 = boto3.resource('s3',
#            aws_access_key_id=creds['AccessKeyId'],
#            aws_secret_access_key=creds['SecretAccessKey'],
#            aws_session_token=creds['SessionToken']
            )
    bucket = s3.Bucket(bucket_name)
    granule_name_old = None
    for obj in bucket.objects.all():
        granule_name_new = obj.key.split('/')[0]
        if granule_name_new != granule_name_old:
            granule_name_old = granule_name_new
            file_name = "s3://" + "/".join([bucket_name,obj.key.replace("ACmask","{}")])

            print("running for:", file_name)
            browse = Browse(file_name, stretch='log')
            geotiff_file_name = browse.prepare()
    exit()
    for obj in bucket.objects.filter(Prefix=prefix):
      if obj.key == prefix:
        continue
      file_name = f"./{obj.key}"
      splits = obj.key.split('.')[1:4]
      header_file_name = file_name
      print(file_name)
      exit()
      print("running for:", file_name)
      browse = Browse(file_name, stretch='log')
      geotiff_file_name, _ = browse.prepare()
      del(browse)
      print("Done:", geotiff_file_name)
      os.remove(file_name)
      print("Removed:", file_name)
      os.remove(f"./true_color/{file_name.replace('.hdf', '.tiff')}")
      print('====================')
      gc.collect()


run_option = "debug"

buckets = {
        "debug":"hls-debug-output",
        "prod":"hls-global",
        }

prefixes = {
        "debug":"",
        "prod":"S30/data/"
        }
# download s30 data and create merged geotiffs.
download_and_create(buckets[run_option], prefix=prefixes[run_option])

def create_and_move_to_folders(extension):
  directories = set()
  for file_name in glob(extension):
    print(file_name.split("."))
    date = file_name.split(".")[3]
    split = file_name.split(".")[1]
    folder_name = f"{split}_NBAR_{date[0:4]}_{date[4:]}/"
    directories.add(folder_name)
    if not(os.path.exists(folder_name)):
      os.mkdir(folder_name)
    print(shutil.move(file_name, folder_name))

# move xml files
create_and_move_to_folders('*.xml')
# move tiff files
create_and_move_to_folders('*.tiff')
