#!/usr/bin/python
# -*- coding: utf-8 -*-

import base64
import hashlib
import getpass
import os

from Crypto import Random
from Crypto.Cipher import AES

from logger import *
from helpers import *

class AESCipher(object):
    def __init__(self, key):
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = bytes(Random.new().read(AES.block_size))
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        r = cipher.decrypt(enc[AES.block_size:])
        return self._unpad(r)

    def _pad(self, s):
        length = AES.block_size - (len(s) % AES.block_size)
        return (s + bytes([length])*length)
    def _unpad(self, r):
        return r[:-r[-1]]

def encrypt_file(path, password):
    c = AESCipher(password)
    f = open(path, "rb")
    not_encrypted = f.read()
    f.close()
    encrypted = c.encrypt(not_encrypted)
    f = open(path, "wb")
    f.write(encrypted)
    f.close()

def decrypt_file(path, password):
    c = AESCipher(password)
    f = open(path, "rb")
    encrypted = f.read()
    f.close()
    not_encrypted = c.decrypt(encrypted)
    f = open(path, "wb")
    f.write(not_encrypted)
    f.close()
