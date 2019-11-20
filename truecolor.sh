#!/bin/bash

# Generate true color browse image of an S2 or L8 HDF. 
# 
# Gdal_translate extracts the RGB bands as plain binary from HDF, and the
# C code does a contrast stretch and writes the intermediate image in TIFF, 
# and finally gdal_translate can resize it and convert it to other formats.
#
# Requires:
#   a) gdal_translate,  test on GDAL 2.2.2, released 2017/09/15
#   b) possibly tiff library.  The executable from C should work; if not 
#      recompile using the TIFF library.
#
# Junchang Ju
# Aug 1, 2019:  No longer relies on the HDF tools and ImageMagick, but switch 
# to the more versatile gdal_translate.

if [ $# -ne 2 ]
then
    echo "$0 <inHDF> <outIMG>" >&2
    echo "Use suffix to indicate output image type" >&2
    exit 1 
fi
inhdf=$1
outimg=$2

set -e
set -o pipefail

CODE_DIR=$(dirname $0)

### Apply the same contrast stretch to the RGB bands of the input image
blu_low=100
blu_high=1600

grn_low=$blu_low
grn_high=$blu_high

red_low=$blu_low
red_high=$blu_high

### The band names.  Gdal can use either band index or SDS names. 
# Band index. Same for L30 and S30.
bluidx=1
grnidx=2
redidx=3

# Use SDS names, not band index
case $inhdf in 
  *L30*) 	blusdsname=band02;
         	grnsdsname=band03;
	 	redsdsname=band04;
		;;
  *S30*) 	blusdsname=B02;
         	grnsdsname=B03;
	 	redsdsname=B04;
		;;
  *) echo "Not sure of the input file type. Exit..."; exit 1;;
esac

### Get image dimension from gdalinfo. Gdalinfo may not be able to get the dimension at all, 
# but we use the nrow/ncol metadata of HLS files.
set $(gdalinfo $inhdf | awk '$0 ~ /NROWS=[1-9]*/ {split($0, a, "="); nrow=a[2]}
		       	     $0 ~ /NCOLS=[1-9]*/ {split($0, a, "="); ncol=a[2]}
		             END {print nrow, ncol}')
nrow=$1
ncol=$2

### Extract the band as plain int16 binary.
base=$(basename $inhdf .hdf)
trap 'rm -f /tmp/tmp.*${base}.*' 0
gdal_translate -q -of ENVI -ot Int16  HDF4_EOS:EOS_GRID:"$inhdf":Grid:$blusdsname   /tmp/tmp.blu.bin.${base}.$$ 
gdal_translate -q -of ENVI -ot Int16  HDF4_EOS:EOS_GRID:"$inhdf":Grid:$grnsdsname   /tmp/tmp.grn.bin.${base}.$$ 
gdal_translate -q -of ENVI -ot Int16  HDF4_EOS:EOS_GRID:"$inhdf":Grid:$redsdsname   /tmp/tmp.red.bin.${base}.$$ 

### Contrast stretch
type=linear
tmptiff=/tmp/tmp.${base}.$$.tiff
$CODE_DIR/truecolor.asTIFF       	$type \
					$nrow $ncol\
					/tmp/tmp.blu.bin.${base}.$$   $blu_low $blu_high\
					/tmp/tmp.grn.bin.${base}.$$   $grn_low $grn_high\
					/tmp/tmp.red.bin.${base}.$$   $red_low $red_high\
					$tmptiff

### Final conversion, resize
case $outimg in
  *.jpg) OF=JPEG;;
  *.png) OF=PNG;;
  *.tiff | *.tif) OF=Gtiff;;
esac
resize=10
gdal_translate -q  -outsize $resize% $resize% -of $OF $tmptiff $outimg

exit 0

