#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Paul Sladen, 2014-12-04, Seaward GAR PAT testing file format debug harness
# Hereby placed in the public domain in the hopes of improving
# electrical safety and interoperability.

# == GAR ==
# GAR files are a container format used for importing/exporting
# filesets to and from some Seaward PAT testing machines ("Apollo"
# series?).  As of 2014-12-05 I have seen three examples of '.GAR'
# files; one purporting to contain an .SSS file and a selection of
# JPEGs and two purporting to contain just an .SSS file.
#
# == File Header ==
# There is a single file-header that begins 0xcabcab (CAB CAB;
# cabinet?) for identification purposes, followed by single byte
# version number.  There is no-end of file marker or overall checksum.
#
# == Archive records ==
# Each file stored within the container is prefixed by a record header
# giving the overall size of the record,
# a variable length human-readable string (the filename),
# a monotonically increasingly truncated semi-timestamp,
# plus the original pre-compression length.
#
# == Compression ==
# Compression is straight Deflate (aka zlib)---as is used in zipfiles
# and PNG images.  This reduces the largely fixed-field .SSS files to
# ~10% of their input size, while the already-compressed JPEG files
# remain ~99% of their input size.  Each file's payload is compressed
# separately.
#
# == Deflate ==
# The QByteArray::qCompress() convention is used, this prepends an
# extra four-byte header containing the little-endian uncompressed
# size, followed by the two-byte zlib header, deflate
# streamed, and four-byte zlib footer:
# http://ehc.ac/p/ctypes/mailman/message/23484411/
#
# Note that as the contained files are likely to be well-under 65k in
# length, the first 2 bytes are be nulls, which is a handy way to
# sanity test the next step.  :-D
# 
# == Obfuscation ==
# The qCompress-style compressed Deflate streams (with length prefix)
# are additively perturbed (bytewise ADD/SUB, not XOR) using the
# bottom 8-bits from Marsaglia xorshift PNR, seeded from the
# pseudo-timestamp and payload length of the corresponding file.
#
# == Integrity checking ==
# The Zlib checksum provides the only defacto integrity checking in
# the GAR file-format; however the presence of the duplicate
# (obfuscated) file length is a useful double-check.

import struct
import sys
import numpy

# Marsaglia xorshift
# https://en.wikipedia.org/wiki/Xorshift
# http://stackoverflow.com/questions/4508043/on-xorshift-random-number-generator-algorithm
def marsaglia_xorshift_128(x = 123456789, y = 362436069, z = 521288629, w = 88675123):
    while True:
        t = (x ^ (x << 11)) & 0xffffffff
        x, y, z = y, z, w
        w = (w ^ (w >> 19) ^ (t ^ (t >> 8)))
        yield w

# The lower 8-bits from the Xorshift PNR are subtracted from byte values
def deobfuscate_string(pnr, obfuscated):
    return ''.join([chr((ord(c) - pnr.next()) & 0xff) for c in obfuscated])

def gar_extract(filename):
    f = open(filename, 'rb')
    header = struct.unpack('>L', f.read(4))[0]
    cabcab = header >> 8
    version = header & 0xff
    assert cabcab == 0xcabcab and version == 1
    files = 1
    while True:
        s = f.read(4)
        # There is no End-of-file marker, just no more packets
        if len(s) < 4: break
        sub_filename_length, = struct.unpack('>L', s)
        sub_filename = f.read(sub_filename_length)
        compressed_length, = struct.unpack('>L', f.read(4))
        contents = f.read(compressed_length)
        header_length, compression_method, checksum, payload_length = struct.unpack('>HHLL', contents[:12])
        assert header_length == 0x0c and compression_method == 0x01
        print '"%s" (%d characters): %d bytes, %d uncompressed (%+d bytes %2.2f%%), checksum/timestamp?: %#10x' % \
            (sub_filename,
             sub_filename_length,
             compressed_length,
             payload_length,
             payload_length - compressed_length - header_length,
             100.0 * float(compressed_length) / (payload_length),
             checksum)

        # histogram shows even spread, which means either compressed
        # input (probably zlib) or input XOR'ed with a pseudo-random stream
        a, b = numpy.histogram(map(ord,contents), bins=xrange(257))
        #print dict(zip(b,a))
        #print sorted(a, reverse=True)[0]

        # test for simple XORing (now disproved)
        #for i in 0x00,:
        #    new = ''.join([chr(ord(c) ^ i) for c in contents ])
        #    g = open('output/' + str(files) + "." + str(i) + '.test', 'wb')
        #    g.write(new)
        #    g.close()

        files += 1

def main():
    for gar in sys.argv[1:]:
        print 'CAB/GAR filename "%s"' % gar
        gar_extract(f)

if __name__=='__main__':
    main()
