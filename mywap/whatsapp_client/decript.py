import base64
from Crypto.Cipher import AES
from Crypto import Random

import hmac
import hashlib
import sys
import json

import binascii
import StringIO

class PKCS7Encoder(object):
    def __init__(self, k=16):
       self.k = k

    ## @param text The padded text for which the padding is to be removed.
    # @exception ValueError Raised when the input padding is missing or corrupt.
    def decode(self, text):
        '''
        Remove the PKCS#7 padding from a text string
        '''
        nl = len(text)
        val = int(binascii.hexlify(text[-1]), 16)
        if val > self.k:
            raise ValueError('Input is not padded or padding is corrupt')

        l = nl - val
        return text[:l]

    ## @param text The text to encode.
    def encode(self, text):
        '''
        Pad an input string according to PKCS#7
        '''
        l = len(text)
        output = StringIO.StringIO()
        val = self.k - (l % self.k)
        for _ in xrange(val):
            output.write('%02x' % val)
        return text + binascii.unhexlify(output.getvalue())


def cleanpkcs7(txt):
    lastbyte = ord(txt[-1])
    if len(txt) <= lastbyte:
        return txt

    found = True
    for i in xrange(lastbyte - 1):
        if ord(txt[-(i + 1)]) != lastbyte:
            found = False
    if found:
        return txt[:-lastbyte]
    else:
        return txt


iv = Random.new().read(AES.block_size)
encoder = PKCS7Encoder()


def loadkeys(fname):
    j = json.load(open(fname, "r"))
    for i in j:
        j[i] = base64.b64decode(j[i])
    return j


def encryptmessage(tag, d, keys):
    decr = AES.new(keys['encKey'], AES.MODE_CBC, iv)
    o = iv + decr.encrypt(encoder.encode(d))
    sig = hmac.new(keys['macKey'], msg=o, digestmod=hashlib.sha256).digest()
    return tag + "," + sig + o

