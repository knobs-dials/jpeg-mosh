# jpeg-mosh

Code that mildly corrupts JPEGs for a moshing-like effect, 
as e.g. used on https://mosh.scarfboy.com/

The test.jpg is from https://commons.wikimedia.org/wiki/File:Jpeg_thumb_artifacts_test.jpg


## cli corrupter

Usage: mosh-jpeg [options] jpegfilenames

Options:
  -h, --help            show this help message and exit
  -q QT, --corrupt-qt=QT
                        How much to corrup tthe quantization tables.
                        E.g. 3,1 means 'pick a random byte three times, flip
                        one bit in it'.               For these tables, 1,1 is
                        often subtler, 10,1 is a bunch. Use 0,0 to not do so
                        at all.
  -i IM, --corrupt-im=IM
                        How much to corrupt the image data. Same
                        interpretation as --corrupt-qt. Try 0,0 (nothing),
                        2,1, 100,2. Larger will probably just break the image
                        early, and make an empty/patterned rest of the image.
