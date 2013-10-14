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

import os
from imapfs import message
from imapfs.debug_print import debug_print
import uuid
import time

FS_BLOCK_SIZE = 262144

class File:
  """Represents a file
  """
  def __init__(self, msg, ctime, mtime, size, blocks):
    self.message = msg
    self.ctime = ctime
    self.mtime = mtime
    self.size = size
    self.blocks = blocks
    self.dirty = False

    self.pos = 0

    self.open_messages = {}

  def create_block(self, block_id):
    """Create a block
    """
    name = str(uuid.uuid4())
    block = message.Message(self.message.conn, name, "")
    block.dirty = True
    self.blocks[block_id] = block.name
    self.open_messages[block_id] = block
    self.dirty = True
    return block

  def open_block(self, block_id):
    """Open a block
    """
    if block_id in self.open_messages:
      return self.open_messages[block_id]
    else:
      debug_print("Opening block %d" % block_id)
      if block_id not in self.blocks:
        # Create first
        block = self.create_block(block_id)
        return block
      else:
        block_key = self.blocks[block_id]
        msg = message.Message.open(self.message.conn, block_key)
        self.open_messages[block_id] = msg
        return msg

  def close_block(self, block_id):
    """Close a block
    """
    if block_id not in self.open_messages:
      return
    debug_print("Closing open block %d" % block_id)
    self.open_messages[block_id].close()
    self.open_messages.pop(block_id)

  def delete_block(self, block_id):
    """Delete a block
    """
    if block_id not in self.blocks:
      return
    if block_id in self.open_messages:
      self.close_block(block_id)

    # Delete
    message.Message.unlink(self.message.conn, self.blocks[block_id])
    self.blocks.pop(block_id)
    self.dirty = True

  def truncate(self, size=None):
    """Resize the file
    """
    if size is None:
      return

    self.size = size

    # Close and delete truncated blocks
    end_block = self.size / FS_BLOCK_SIZE
    for block_id in self.blocks:
      if block_id > end_block:
        self.delete_block(block_id)
        # We leave the entire last block intact, even if it got trimmed a little

    self.dirty = True

  def seek(self, offset, whence=os.SEEK_SET):
    """Seek to an offset in the file
    """
    old_pos = self.pos
    if whence == os.SEEK_SET:
      new_pos = offset
    elif whence == os.SEEK_CUR:
      new_pos = old_pos + offset
    elif whence == os.SEEK_END:
      new_pos = self.size - offset

    # Get block we are moving from and to
    old_block_id = old_pos / FS_BLOCK_SIZE
    new_block_id = new_pos / FS_BLOCK_SIZE

    # If we exit a block into a new one, we close the old block
    # to write changes and free memory
    if old_block_id != new_block_id and old_block_id in self.open_messages:
      self.close_block(old_block_id)

    self.pos = new_pos

  def read(self, size):
    """Read a set of bytes from a file
    Size must be specified
    """
    # read only as much as is available
    if self.pos + size > self.size:
      size = self.size - self.pos

    # Get block the start point and end points are in
    start_block_id = self.pos / FS_BLOCK_SIZE
    end_block_id = (self.pos + size) / FS_BLOCK_SIZE + 1

    buf = bytearray()

    # For each block containing data we need
    for i in range(start_block_id, end_block_id):
      # Where in this block does the data start?
      current_block_offset = self.pos % FS_BLOCK_SIZE
      # How much data can we read out of this block?
      read_size = FS_BLOCK_SIZE - current_block_offset

      # Read only as much as we need
      if len(buf) + read_size > size:
        read_size = size - len(buf)

      # Open block, seek to position, read
      block = self.open_block(i)
      block.seek(current_block_offset)

      buf += block.read(read_size)

      # Update seek position.
      self.seek(read_size, os.SEEK_CUR)

    return buf

  def write(self, buf):
    """Write data to the file
    """
    size = len(buf)
    # Increase size if we need to
    if self.pos + size > self.size:
      self.truncate(self.pos + size)

    # Determine starting and ending blocks
    start_block_id = self.pos / FS_BLOCK_SIZE
    end_block_id = (self.pos + size) / FS_BLOCK_SIZE + 1

    write_offset = 0

    # For each block we need to write to
    for i in range(start_block_id, end_block_id):
      # Find where our write starts in the current block
      current_block_offset = self.pos % FS_BLOCK_SIZE
      # Figure out how much we can write in this block
      write_size = FS_BLOCK_SIZE - current_block_offset
      # Write only as much as in buf
      if write_size > size - write_offset:
        write_size = size - write_offset

      # Open, seek, write.
      block = self.open_block(i)
      block.seek(current_block_offset)
      block.write(buf[write_offset:write_offset + write_size])

      write_offset += write_size

      # Update seek pos
      # This also flushes/closes the open block if we are done
      self.seek(write_size, os.SEEK_CUR)

  def flush(self):
    """Flush changes to this file
    """
    if self.dirty:
      self.message.truncate(0)
      self.message.write("f\r\n%d\t%d\t%d\r\n" % (self.ctime, self.mtime, self.size))
      for block_id, block_key in self.blocks.items():
        self.message.write("%d\t%s\r\n" % (block_id, block_key))

      self.message.flush()
      self.dirty = False

  def close(self):
    """Close this file
    Flushes and closes all open blocks
    """

    # Close all blocks
    for block_id, block in self.open_messages.items():
      debug_print("Closing open block %d" % block_id)
      block.close()
    self.open_messages = {}
    self.flush()
    self.message.close()

  def delete(self):
    """Delete this file
    Goes through and also deletes all blocks
    """
    # Delete all blocks
    for block_key in self.blocks.values():
      message.Message.unlink(self.message.conn, block_key)

    # Unlink own block
    message.Message.unlink(self.message.conn, self.message.name)

  @staticmethod
  def create(conn):
    """Create a file
    """
    msg = message.Message.create(conn)
    f = File(msg, time.time(), time.time(), 0, {})
    f.dirty = True
    return f

  @staticmethod
  def from_message(msg):
    """Create a file object from a message
    """
    data = str(msg.read())

    lines = data.split("\r\n")
    info = lines[1].split("\t")

    blocks = {}

    for line in lines[2:]:
      if not line:
        continue
      line_info = line.split("\t")
      blocks[int(line_info[0])] = line_info[1]

    f = File(msg, int(info[0]), int(info[1]), int(info[2]), blocks)
    return f

