/*Do a true color, logarithmic  stretch of the blue, green, and red bands and write the
  result as TIFF.

  The algorithm is simple. First take the log value of input image. Then when the log value
  is below the low threshold, set the pixel to 0 and when it is higher than the high threshold
  set it to 255.  Linearly stretch the log values between the two thresholds to 0 and 255 respectively.
  The base of the logarithm has no effect since the effect of different bases will be
  cancelled out in the ratio used by thye linear stretch.

  Originally MOD09 browse image use:
  log_low = 5.5 and log_high = 9.0. They correspond to scaled reflectance 244.7 and 8103.

  Strictly speaking, a true color stretch requires the same stretch across the bands, but
  for the atmospherically uncorrected TOA reflectance such a stretch would look bad because
  the atmospheric contamination has differential effect on the blue, green and blue bands
  with the most pronounced contamination in blue. As a compromise, the three bands will be
  stretched differently with the low and high ends of the histogram of each bands given on
  commandline. After the eventual atmospheric correction, the low and high ends of the
  histogram will be the same across the bands. In either case, this  stretch will be applied
  with fixed low and high across time. Note the low and high values given at the commandline
  are the reflectance multiplied by 10000, not the log of this value yet.

  Since tiff library conflicts with HDF library, the input has to be plain binary file, not HDF.
  Reading plain binary allows for more input flexibility.


  Junchang Ju, SDSU, April 6, 2009.
		Dec 3, 2014, added linear at NASA (log suppress high value, giving wrong impression)

gcc truecolor.asTIFF.c -o truecolor.asTIFF  -ltiff -ltiffxx -lm \
    -I /usr/include -L /usr/lib

*/

#include <tiffio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define LINEAR 0
#define LOG 1
int main(int argc, char *argv[])
{
	char stype[20];		/* linear or log */
	int nrow;
	int ncol;
 	char fname_b1[1024];
 	double ref_low[3], ref_high[3];   /*The low and high values in the original reflectance that
                                           will be stretched to 0 and 255 respectively*/
	char fname_b2[1024];
	char fname_b3[1024];
	char fname_tif[1024];

	char type;		/* Stretch type */

  FILE *fb1, *fb2, *fb3;
  TIFF *tif;                /*The output TIFF image*/
  unsigned char *raster;    /*The array to store the band interleaved stretched output image*/



  //double log_low[3], log_high[3];  /*The corresponding log value of ref_low and ref_high*/
  double low[3], high[3];  /*The corresponding log value of ref_low and ref_high*/
  double val, tmp_val;

  int i, irow, icol;
  int BGR[3];    /*The stretched output for a single pixel. RGB would be natural, but the input band is in BGR order*/
  int ib;
  int k, pid;

  int16 **bufin;     /*The plain binary input should be int16*/

  if (argc != 14) {
    fprintf(stderr, "Usage: %s  linear|log \n"
  	    "           <nrow> <ncol> \n"
                    "		<fname_b1> <b1.low> <b1.high>\n"
                    "		<fname_b2> <b2.low> <b2.high>\n"
                    "		<fname_b3> <b3.low> <b3.high>\n"
                    "		<out.tif>\n", argv[0]);
    exit(1);
  }

  strcpy(stype, argv[1]);
  nrow = atoi(argv[2]);
  ncol = atoi(argv[3]);

  strcpy(fname_b1, argv[4]);
  ref_low[0]  = atof(argv[5]);
  ref_high[0] = atof(argv[6]);

  strcpy(fname_b2, argv[7]);
  ref_low[1]  = atof(argv[8]);
  ref_high[1] = atof(argv[9]);

  strcpy(fname_b3, argv[10]);
  ref_low[2]  = atof(argv[11]);
  ref_high[2] = atof(argv[12]);

  strcpy(fname_tif, argv[13]);

  fprintf(stderr, "nrow = %d, ncol = %d\n", nrow, ncol);

  if (strcmp(stype, "linear") == 0)
    type = LINEAR;
  else if (strcmp(stype, "log") == 0)
    type = LOG;
  else {
    fprintf(stderr, "Stretching type not supported: %s\n", stype);
    exit(1);
  }

  if ((fb1 = fopen(fname_b1, "r")) == NULL) {
    fprintf(stderr, "Cannot open %s for read\n", fname_b1);
    exit(1);
  }

  if ((fb2 = fopen(fname_b2, "r")) == NULL) {
    fprintf(stderr, "Cannot open %s for read\n", fname_b2);
    exit(1);
  }

  if ((fb3 = fopen(fname_b3, "r")) == NULL) {
    fprintf(stderr, "Cannot open %s for read\n", fname_b3);
    exit(1);
  }

  if((tif = TIFFOpen(fname_tif, "w")) == NULL){
   fprintf(stderr, "Could not create output image %s\n", fname_tif);
   exit(42);
  }

  /*Allocate memory for reading the input bands*/
  if ((bufin = (int16**)calloc(3, sizeof(int16*))) == NULL) {
    fprintf(stderr, "Cannot allocate memory\n");
    exit(1);
  }
  for (ib = 0; ib < 3; ib++) {
    if ((bufin[ib] = (int16*)calloc(nrow*ncol, sizeof(int16))) == NULL) {
       fprintf(stderr, "Cannot allocate memory\n");
       exit(1);
    }
  }

  if ((fread(bufin[0], sizeof(int16), nrow*ncol, fb1) != nrow*ncol) ||
    (fread(bufin[1], sizeof(int16), nrow*ncol, fb2) != nrow*ncol) ||
    (fread(bufin[2], sizeof(int16), nrow*ncol, fb3) != nrow*ncol)) {
      fprintf(stderr, "The file size spec is not consistent with file size\n");
      exit(1);
  }

  if((raster = (unsigned char *) malloc(sizeof(unsigned char) * ncol * nrow * 3)) == NULL){
    fprintf(stderr, "Could not allocate memory\n");
    exit(42);
  }

  for (ib =  0; ib < 3; ib++) {
    if (type == LINEAR) {
    	low[ib] =  ref_low[ib];
    	high[ib] = ref_high[ib];
    }
    if (type == LOG) {
    	low[ib] =  log(ref_low[ib]);
    	high[ib] = log(ref_high[ib]);
    }
  }

  for (irow = 0; irow < nrow; irow++) {
    for (icol = 0; icol < ncol; icol++) {
      k = irow * ncol + icol;
      for (ib =  0; ib < 3; ib++) {
        if (bufin[ib][k] <= 0)
          BGR[ib] = 0;
        else {
          val = bufin[ib][k];
	        if (type == LOG)
            val = log(val);
          if (val <= low[ib])
            BGR[ib] = 0;
          else if (val >= high[ib])
            BGR[ib] = 255;
          else {
            tmp_val = 255.0 * (val - low[ib])/(high[ib]-low[ib]);
            BGR[ib] = ceil(tmp_val);
          }
        }
      }
      pid = k * 3;
      raster[pid] = BGR[2];       /*Output is in RGB order though*/
      raster[pid + 1] = BGR[1];
      raster[pid + 2] = BGR[0];
    }
  }

  /* Write the tiff tags to the file */
  TIFFSetField(tif, TIFFTAG_IMAGEWIDTH, ncol);
  TIFFSetField(tif, TIFFTAG_IMAGELENGTH, nrow);
  TIFFSetField(tif, TIFFTAG_COMPRESSION, 1);   /*No compression*/
  TIFFSetField(tif, TIFFTAG_PLANARCONFIG, PLANARCONFIG_CONTIG);
  TIFFSetField(tif, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
  TIFFSetField(tif, TIFFTAG_BITSPERSAMPLE, 8);
  TIFFSetField(tif, TIFFTAG_SAMPLESPERPIXEL, 3);

  /* Actually write the image */
  TIFFWriteRawStrip(tif, 0, raster, ncol * nrow * 3);

  TIFFClose(tif);

  free(bufin[0]);
  free(bufin[1]);
  free(bufin[2]);
  free(bufin);

  return 0;
}
