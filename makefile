dir = /root/sdpk/lib
TGT:
	gcc truecolor.asTIFF.c -o truecolor.asTIFF  -ltiff -ltiffxx -lm \
    	-I $(dir)/lib/libgeotiff-1.4.2  -I $(dir)/lib/libgeotiff-1.4.2/libxtiff  \
	-L $(dir)/lib/libgeotiff-1.4.2/.libs -L $(dir)/lib/tiff-4.0.9/libtiff/.libs   

#TGT:
#	gcc truecolor.asTIFF.c -o truecolor.asTIFF  -ltiff -ltiffxx -lm \
#    	-I /u/jju/code/geotiff/tiff-3.8.2/include -L /u/jju/code/geotiff/tiff-3.8.2/lib 
