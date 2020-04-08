import boto3
import os
import subprocess
import uuid


LIB_DIR = os.path.join(os.getcwd(), 'local', 'lib')
S3_CLIENT = boto3.client('s3')

HLS_BUCKET = "hls-browse-image"
HLS_FILE_NAME = "HLS_CorrectedReflectance_TrueColor_{}"
THUMBNAIL_FILE_NAME = "HLS_CorrectedReflectance_Thumbnail_{}"

def handler(event, context):
    # Method to be called from aws lambda functions
    results = []
    for record in event['Records']:

        # Find input/output buckets and key names
        bucket = record['s3']['bucket']['name']
        file_name = record['s3']['object']['key']
        if '.hdf' not in file_name:
          break
        output_file_name = file_name.replace('.hdf', '.tiff')
        output_file_name = HLS_FILE_NAME.format(output_file_name)

        # Download the file locally
        orig_file_name = "{}-{}".format(uuid.uuid4(), file_name)
        S3_CLIENT.download_file(bucket, file_name, '/tmp/{}'.format(orig_file_name))

        # Call the worker, setting the environment variables
        command = 'LD_LIBRARY_PATH={} python worker.py "{}"'.format(LIB_DIR, orig_file_name)
        output = subprocess.check_output(command, shell=True)

        # Upload the output of the worker to S3
        processed_geotiff = output.strip().split('\n')

        S3_CLIENT.upload_file(processed_geotiff, HLS_BUCKET, output_file_name)
        S3_CLIENT.upload_file(thumbnail.strip(), HLS_BUCKET, thumbnail_file_name)
        results.append(processed_geotiff)

    return results
