FROM osgeo/gdal:ubuntu-full-3.0.3

# Required for click with Python 3.6
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update
RUN apt-get install python3-pip python3-venv git -y

RUN pip3 install tox tox-venv
RUN pip3 install --upgrade setuptools
COPY ./ ./hls-browse_imagery_creator

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["cd hls-browse_imagery_creator && tox -r"]


