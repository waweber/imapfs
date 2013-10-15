# IMAPFS - Cloud storage via IMAP
# Copyright (C) 2013 Wes Weber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

import bz2

AES_KEY_SIZE = 32
AES_BLOCK_SIZE = AES.block_size

class IMAPEnc:
  """Class that handles crypto functions
  """

  def __init__(self, passwd, iterations=10000):
    salt = "just a random salt"
    self.key = PBKDF2(passwd, salt, AES_KEY_SIZE, iterations)

  def compress(self, data):
    """Compress data
    """
    compressed = bz2.compress(data)
    # print "Compressed %d bytes to %d (%.2f)" % (len(data), len(compressed), float(len(compressed)) / len(data))
    return compressed

  def decompress(self, data):
    """Decompress data
    """
    return bz2.decompress(data)

  def pad(self, data):
    """Return data padded to AES blocksize
    """
    plain_len = len(data) + 1
    padded_len = plain_len / AES_BLOCK_SIZE * AES_BLOCK_SIZE + (AES_BLOCK_SIZE if plain_len % AES_BLOCK_SIZE > 0 else 0)
    pad_len = padded_len - len(data)

    return data + chr(pad_len) * pad_len

  def unpad(self, data):
    """Return data with padding stripped
    """
    pad_len = ord(data[-1])
    return data[:-pad_len]

  def encode(self, data):
    """Return data base64-encoded
    """
    return data.encode("base64")

  def decode(self, data):
    """Return data base64-decoded
    """
    return data.decode("base64")

  def encrypt(self, data):
    """Return data AES encrypted
    """
    iv = get_random_bytes(AES_BLOCK_SIZE)
    aes = AES.new(self.key, mode=AES.MODE_CBC, IV=iv)
    return iv + aes.encrypt(data)

  def decrypt(self, data):
    """Return data AES decrypted
    """
    iv = data[0:AES_BLOCK_SIZE]
    ciphertext = data[AES_BLOCK_SIZE:]
    aes = AES.new(self.key, mode=AES.MODE_CBC, IV=iv)
    return aes.decrypt(ciphertext)

  def encrypt_message(self, data):
    """Returns data padded, encrypted, and encoded
    """
    return self.encode(self.encrypt(self.pad(data)))

  def decrypt_message(self, data):
    """Returns data decrypted. Handles padding and encoding.
    """
    return self.unpad(self.decrypt(self.decode(data)))
