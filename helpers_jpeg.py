#!/usr/bin/python3
''' Most of this code splits a JPEG file bytestring into its constituent parts - segments, in JPEG parlance.

 
    read_structure() parses a relatively simple JPEG file into its constituent segments.
    - ...which is less than you were probably looking for.
    - (it originated in somthing even simpler, verying that the mars rover images were indeed an unusual JPEG flavour)
    
    mosh_jpeg_data() takes the segments from read_structure() and corrupts a few specific segments

    Pure-python, meaning it won't be the fastest out there.

        
    Some interesting reading:
      - https://helpful.knobs-dials.com/index.php/Image_file_format_notes#Notes_on_JPEG_file_structure
      - http://www.opennet.ru/docs/formats/jpeg.txt
      - http://www.tex.ac.uk/ctan/support/jpeg2ps/readjpeg.c
      - https://svn.xiph.org/experimental/giles/jpegdump.c
      - http://fotoforensics.com/tutorial-estq.php  'estimating quality based on quantization tables"
      - http://en.wikibooks.org/wiki/JPEG_-_Idea_and_Practice/The_header_part
      - http://www.digitalpreservation.gov/formats/fdd/fdd000017.shtml
      - https://web.archive.org/web/20240406182506/https://koushtav.me/jpeg/tutorial/2017/11/25/lets-write-a-simple-jpeg-library-part-1/

          
    A lot of JPEGs out there, in terms of segments, look a lot like:
     - SOI  (0xD8) - start of image
     - APP0 (0xE0), including
     - a SOF variant (SOF0..SOF15 are 0xC0..0xCF), usually either SOF0 (baseline sequential, huffman) or SOF2 (progressive, huffman)
     - DQT (DB) - quantization tables, one or more (and can come before SOF)
     - DHT (C4) - huffman tables (DHT), one or more
     - SOS (DA) - start of scan
       - compressed image data following the SOS
     - EOI (D9) - end of image (sometimes omitted) 

    ...which also means you can strip out half the code below and have it still work fine for our currently-only-corrupting needs.
'''

import io
import random

SOI   = 0xd8
APP0  = 0xe0
APP1  = 0xe1
APP2  = 0xe2
APP3  = 0xe3
APP4  = 0xe4
APP5  = 0xe5
APP6  = 0xe6
APP7  = 0xe7
APP8  = 0xe8
APP9  = 0xe9
APP10 = 0xea
APP11 = 0xeb
APP12 = 0xec
APP13 = 0xed
APP14 = 0xee
APP15 = 0xef
SOF0  = 0xc0
SOF2  = 0xc2
SOF1  = 0xc1
SOF9  = 0xc9
HQT   = 0xc4
DQT   = 0xdb
SOS   = 0xda
EOI   = 0xd9
COM   = 0xFE

def read_structure(jpeg_data:bytes, debug:bool=False):
    ''' 
    Given a jpeg file contents as a bytes object, splits it into its constituent segments.
    You wouldn't call this a parser - it does little to no interpretation of what those segments mean.

    @param jpeg_data: the file as bytes object
    @param debug: whether to spit out debug stuff on stdout
    @return: a generator that yields 4-tuples:
      - the segment's marker byte (~= its type)
      - a readable description
      - segment size
      - segment data
    '''
    i = 0
    dsize = len(jpeg_data)

    while i < len(jpeg_data):
        if debug:
            print( 'now at bytepos %d of %d'%(i,dsize) )

        #if debug:
        #    import codecs
        #    print( 'next ten bytes: ', codecs.encode( jpeg_data[i:i+10], 'hex_codec'))

        if jpeg_data[i] != 0xff:
            if debug:
                print(  "    segment didn't start with 0xff, "+
                       f"we probably mis-parsed (next bytes are {repr(jpeg_data[i:i+8])})" )
                print('')
            break

        # each loop sets:   ma, descr, moveon, segdata.
        # The last should be _all_ data including 0xff and marker
        #parsed  = {} # TODO: start using. Informational.
        # TODO: yield these one at a time

        marker = jpeg_data[i+1]
        # first handle markers with fixed-size payloads (because those won't code their own size)
        if debug:
            print( "    marker byte  [%02x]"%(marker))
        if   marker == SOI:
            descr = "Start Of Image"
            moveon = 2
        elif marker == EOI:
            descr = "End Of Image"
            moveon = 2
        elif marker == 0xd0:
            descr = 'restart 0'
            moveon = 2
        elif marker == 0xd1:
            descr = 'restart 1'
            moveon = 2
        elif marker == 0xd2:
            descr = 'restart 2'
            moveon = 2
        elif marker == 0xd3:
            descr = 'restart 3'
            moveon = 2
        elif marker == 0xd4:
            descr = 'restart 4'
            moveon = 2
        elif marker == 0xd5:
            descr = 'restart 5'
            moveon = 2
        elif marker == 0xd6:
            descr = 'restart 6'
            moveon = 2
        elif marker == 0xd7:
            descr = 'restart 7'
            moveon = 2
        elif marker >= 0x30 and marker <= 0x3f:
            descr = 'reserved JP2'
            moveon = 2
        elif marker==0xdd:
            descr = 'restart interval'
            moveon = 6

        elif marker==SOS:
            # Start of Scan.  Unlike other segments, we have to actually _parse its data_ to figure out its size
            #  And note that _which_ Start-of-Frame flavour (SOF0, SOF1, or SOF2) will direct how exactly it should be parsed

            # 2 bytes: length
            #   ...of the header, i.e.
            #    - 0xffda
            #    - 1 byte: numcomponents
            #    - numcomponents*(1+1 byte)
            #    - Ss, Se, Ah/Al
            #  This is followed by compressed data, of which you can only get the length by decoding.
            #  (or guess where the next valid frame starts)
            descr = "start of scan"
            #if debug:
            #    print descr

            datasize = (jpeg_data[i+2]<<8) + jpeg_data[i+3] # seems to be the length of the header?
            if debug:
                print( '  SOS header size: %s'%datasize)
            num_components = jpeg_data[i+4]

            if debug:
                print( "  Components in scan: %d"%num_components)
            for ci in range(num_components):
                if debug:
                    print( "  Component %d of %d"%(ci+1,num_components))
                cid  = jpeg_data[i+4 + 2*ci]
                if debug:
                    print( "   Channel", end='')
                    if   cid==1:
                        print( "Y ")
                    elif cid==2:
                        print( "Cb")
                    elif cid==3:
                        print( "Cr")
                    elif cid==4:
                        print( "I ")
                    elif cid==5:
                        print( "Q ")
                    else:
                        print( cid)
                htab    = jpeg_data[i+4+2*ci+1]
                htab_ac = (htab&0xf0)>>4
                htab_dc = htab&0x0f
                if debug:
                    print( "  Huffman table  AC:%x  DC:%x"%(htab_ac, htab_dc))

            # HACK: just look assume this section ends with an EOI
            if jpeg_data.endswith(b'\xff\xd9'):
                segdata = jpeg_data[i:-2]
                moveon = (len(jpeg_data)-i) - 2
            else: # or sometimes no EOI. Joy.
                segdata = jpeg_data[i:]
                moveon = len(jpeg_data)-i

            #if debug:
            #    print('segdata', repr(segdata))

        else: # assume it's one that codes its length
            if   marker==COM:
                descr = 'comment'

            elif marker >= APP0  and  marker <= APP15:
                descr = 'APP%d %r'%(
                    marker-0xe0,
                    jpeg_data[i+4: jpeg_data.find(b'\x00',i+5) ]
                )

            elif marker==HQT:
                descr = 'huffman tables'
            elif marker==DQT:
                descr = 'quantization tables'

            # almost all JFIFs in the wild are C0, C2, or the occasional C1
            elif marker==SOF0:
                descr = 'start of frame, baseline sequential, huffman'
            elif marker==SOF2:
                descr = 'start of frame, progressive, huffman'
            elif marker == SOF1:
                descr = 'start of frame, extended sequential, huffman'
            elif marker == SOF9:
                descr = 'start of frame, extended sequential, arithmetic'

            # most others are unused
            elif marker == 0xc3:
                descr = '(start of frame? -) lossless'
            elif marker == 0xc5:
                descr = '(start of frame? -) differential sequential DCI'
            elif marker == 0xc6:
                descr = '(start of frame? -) differential progressive DCI'
            elif marker == 0xc7:
                descr = '(start of frame? -) differential lossless'
            elif marker == 0xc8:
                descr = 'JPEG extensions'
            elif marker == 0xca:
                descr = '(start of frame? -) extended progressive DCT'
            elif marker == 0xcb:
                descr = '(start of frame? -) extended lossless'
            elif marker == 0xcc:
                descr = 'arithmetic conditioning table'

            # Dunno, don't really care, could remove for my purposes?
            elif marker >= 0xf0 and marker <= 0xf6:
                descr = 'JPEG extensions, ITU T.84/IEC 10918-3'
            elif marker == 0xf7:
                descr = 'JPEG LS - SOF48'
            elif marker == 0xf8:
                descr = 'JPEG LS - LSE'
            elif marker >= 0xf9 and marker <= 0xffd:
                descr = 'JPEG extensions, ITU T.84/IEC 10918-3'
            elif marker >= 0x4f and marker <= 0x6f:
                descr = 'JPEG extensions, JPEG2000?'
            elif marker >= 0x90 and marker <= 0x93:
                descr = 'JPEG extensions, JPEG2000?'
            elif marker == 0x51:
                descr = 'JPEG extensions, JPEG2000?, image and tile size'
            elif marker == 0x52:
                descr = 'JPEG extensions, JPEG2000?, coding style default'
            elif marker == 0x53:
                descr = 'JPEG extensions, JPEG2000?, coding style component'
            elif marker == 0x5e:
                descr = 'JPEG extensions, JPEG2000?, region of interest'
            elif marker == 0x5c:
                descr = 'JPEG extensions, JPEG2000?, quantization default'
            elif marker == 0x5d:
                descr = 'JPEG extensions, JPEG2000?, quantization component'
            elif marker == 0x5f:
                descr = 'JPEG extensions, JPEG2000?, progression order change'
            elif marker == 0x55:
                descr = 'JPEG extensions, JPEG2000?, tile-part lengths'
            elif marker == 0x57:
                descr = 'JPEG extensions, JPEG2000?, packet length (main header)'
            elif marker == 0x58:
                descr = 'JPEG extensions, JPEG2000?, packet length (tile-part header)'
            elif marker == 0x60:
                descr = 'JPEG extensions, JPEG2000?, packed packet headers (main header)'
            elif marker == 0x61:
                descr = 'JPEG extensions, JPEG2000?, packet packet headers (tile-part header)'
            elif marker == 0x91:
                descr = 'JPEG extensions, JPEG2000?, start of packet'
            elif marker == 0x92:
                descr = 'JPEG extensions, JPEG2000?, end of packet header'
            elif marker == 0x63:
                descr = 'JPEG extensions, JPEG2000?, component reg'
            elif marker == 0x64:
                descr = 'JPEG extensions, JPEG2000?, comment'

            elif marker == 0xfd:
                descr = 'reserved for JPEG extensions'

            elif marker==SOS:
                descr = 'SOS Start Of Scan'

            else:
                descr = 'unknown marker'
                # CONSIDER: raise (maybe on request) so that we can test this on a lot of JPEG images?

            # data size describes the *whole* frame payload, which includes the two datasize bytes
            datasize = (jpeg_data[i+2]<<8) + jpeg_data[i+3]
            #print( '      datasize: %d'%datasize)
            segdata = jpeg_data[i+4: i+2+datasize] # +2 being +4-2
            #print( '      data (len %d): %r %r'%(len(segdata), segdata[:8], segdata[-8:]))
            #print( '      data (len %d): %r'%(len(segdata), segdata))
            #print( '      bytes following this segment: %r'%(jpeg_data[i+2+datasize: i+2+datasize+6]))
            moveon = datasize+2

        if debug:
            #print( "Chunk  size:2+%-3d   type:%02X  %-30s  data:%r"%( moveon-2, ma, descr, segdata ))
            print( "Chunk  size:2+%-3d   type:%02X  %-30s"%( moveon-2, marker, descr ))


        #######
        # So far we've just been separating segments and poking at a few easily parsable things
        # Below is some selective parsing of contents
        if debug:
            if marker==0xe0:
                #print( 'segdata_', len(segdata), repr(segdata) )
                if segdata[0:5] == b'JFIF\x00':
                    units = segdata[7]
                    if units==0:
                        units = 'none (0)'
                    elif units==1:
                        units = 'dpi (1)'
                    elif units==2:
                        units = 'dpcm (2)'
                    else:
                        units = 'unknown (%d)'%units
                    if debug:
                        print( "      Version:    %d.%02d"%(segdata[5],segdata[6]))
                        print( "      Units:      %s"%units)
                        print( "      Xdensity:   %d"%( segdata[8]<<8 + segdata[9] ))
                        print( "      Ydensity:   %d"%( segdata[10]<<8 + segdata[11] ))
                        print( "      XThumbnail: %d"%( segdata[12] )) # If these are nonzero, an uncompressed thumbnail follows in APP0?
                        print( "      YThumbnail: %d"%( segdata[13] ))
                #elif segdata[0:5]=='JFXX\x00':  # Apparently in 1.02.  Used for other thumbnail types
                else:
                    if debug:
                        print( "Don't know APP0 identifier %r, skipping"%segdata[0:5])

            elif marker==SOF0: # start of frame, baseline
                data_precision = segdata[0]
                h     = (segdata[1]<<8) + segdata[2]
                w     = (segdata[3]<<8) + segdata[4]
                comps = segdata[5]
                if debug:
                    print( "      Image is %d by %d px,  %d-channel,  %d bits per channel"%(
                        w,h, comps, data_precision))
                for ci in range(comps):
                    if debug:
                        print( '       ', end='')
                    cid     = segdata[6+ci*3+0]
                    sampfac = segdata[6+ci*3+1]
                    qtnum   = segdata[6+ci*3+2]
                    if debug:
                        if   cid == 1:
                            print( "Y ", end='')
                        elif cid == 2:
                            print( "Cb", end='')
                        elif cid == 3:
                            print( "Cr", end='')
                        elif cid == 4:
                            print( "I ", end='')
                        elif cid == 5:
                            print( "Q ", end='')
                        print( 'hsfac:%d vsfac:%d  qtnum:%d'%( (sampfac&0xf0)>>4, sampfac&0x0f, qtnum) )

            # elif ma==SOF2: # start of frame, progressive
            #    pass

            elif marker==0xfe:
                if debug:
                    print( '      %r'%segdata )

        segdata = jpeg_data[i:i+moveon]
        i += moveon
        yield marker, descr, moveon, segdata



def mosh_jpeg_data(jpegdata, typ=3, qt=(2,1), im=(15,1), validate=False, validate_maxtries:int=10):
    """ Takes a JPEG file's byte data, returns a corrupted JPEG file byte data that hopefully still displays

        @param typ: what part(s) to corrupt; 
          - if typ&1, we corrupt quantization tables according to qt (if not, we don't, even if you handed something not 0,0 into the paramters)
          - if typ&2, we corrupt image data according to im   (if not, we don't, even if you handed something not 0,0 into the paramters)

        @param qt: should be a (howmanytimes,howmanybits) tuple, how much to corrupt the quantization tables
        Note that small changes have a lot of effect if early in the table 
        (though we don't currently control where -- that might be interesting to do).

        Eyeballed values used in the app:
         - 0,0: not
         - 1,1: a little
         - 2,2: a little more
         - 4,2: more
         - 6,2: a bunch
         - 12,4: a lot

        @param im: should be a (howmanytimes,howmanybits) tuple, how much to corrupt the image data after the SOS
        You generally want the howmanybits low, because it's easy to cause a "we can't deal with the rest" breakoff 

        Eyeballed values used in the app:
         - 0,0: not
         - 3,1: a little
         - 8,2: a little more
         - 30,2: more
         - 80,2: a bunch
         - 140,3: a lot

        @param validate: if True, we keep generating until PIL can read it, 
        which is a decent estimation of us not having corrupted it beyond being an image anymore.
        Depending on the settings you use, this may take a few tries,
        but is also not guaranteed to be as critical as another image reader.
        If False, it does no checks.

        @param validate_maxtries: if validating, how fast to give up 
        (mostly to avoid indinite loop caused by corrupting too much)
    """
    from PIL import Image # only used to validate that it can still be opened

    # This can be moved to a helpers_corrupt
    def flipbits(data:bytes, howmanytimes:int=10, howmanybits:int=2, skipfirstbytes:int=0, mask=None):
        ''' Takes bytes, and some parameters on how to corrupt those bytes.

            The corruption is based on 
              - picking a byte position (random with some control),
              - flipping a random bit in that byte _howmanybits_ times. 
              - and repeating that _howmanytimes_ times

            Yes, both can pick the same positions and end up not changing the data at all. 
            No, this is not the most efficient way to do this. For my purposes, I don't care yet.

            @param skipfirst: basic construction to not touch the first bytes, to avoid headers at the start

            @param mask: if not None, should be a list of indices - we will work _only_ on those indices
            Note that if mask is set, it overrules skipfirstbytes.

            @return: a bytes object of the same length, and _mostly_ with the same data, y'know.
        '''
        retdata = bytearray( data[:] )
        #retdata = list(ord(by)   for by in data)
        if mask:
            mask = list(index   for index in mask   if index>skipfirstbytes and index<len(data))

        while howmanytimes>0:
            if mask:
                targetbyte = random.choice(mask)
            else:
                targetbyte = random.randint(skipfirstbytes,len(data)-1)
            for _ in range(howmanybits):
                bitnum = random.randint(0,7)
                #print( " flipping byte's %d bit %d"%(victim,bitnum) )
                retdata[targetbyte] ^= 2**bitnum
            howmanytimes -= 1
        return bytes(retdata) #''.join(chr(di) for di in retdata)

    tries = validate_maxtries
    while tries > 0:
        tries -= 1
        ret = []
        for marker, _descr, _moveon, segdata in read_structure( jpegdata ):
            if marker == DQT: # quant tables
                mask = [] # try to only corrupt the table values themselves
                i=4 # skip past ff, marker, and length
                for _ in range(4):
                    i+=1
                    mask.extend( range(i,i+64) ) # current assumes 8-bit quant tables; TODO: fix
                if typ & 0x01:
                    corrupted_segdata = flipbits(
                        segdata, howmanytimes=qt[0], howmanybits=qt[1], skipfirstbytes=4)
                    ret.append(corrupted_segdata)
                else:
                    ret.append(segdata)

            elif marker == SOS: # SOS and image data
                if typ & 0x02:
                    corrupted_segdata = flipbits(
                        segdata, howmanytimes=im[0], howmanybits=im[1], skipfirstbytes=20)
                    ret.append(corrupted_segdata)
                else:
                    ret.append(segdata)

            elif marker >= 0xe1  and  marker <= 0xef: # strip APP1..15
                pass
            else: # other chunk, pass through
                ret.append(segdata)

        retdata = b''.join(ret)

        if not validate:
            return retdata
        else:
            try:
                #print("Attempting to validate")
                validate_im = Image.open( io.BytesIO( retdata ) ) # if that doesn't raise an error, we're probably fine
                validate_im.load()
                return retdata
            except IOError:
                #import sys
                #print( "Image did not parse, retry %d"%tries, file=sys.stderr)
                continue

    raise ValueError("Didn't get valid data after %d tries, you're probably asking for too much corruption."%validate_maxtries)
