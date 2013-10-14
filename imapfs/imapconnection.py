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

import email.mime.text
import imaplib
import re
import time


class IMAPConnection:
  """Class that manages a connection to an IMAP server
  """

  def __init__(self, host, port, enc):
    """Connects to host:port
    """
    self.conn = imaplib.IMAP4_SSL(host, port)
    self.enc = enc
    self.mailbox = "INBOX"
    self.uid_cache = {}

  def login(self, user, passwd):
    """Log in using user and passwd
    """
    self.conn.login(user, passwd)

  def logout(self):
    """Log out of the server
    """
    self.conn.logout()

  def select(self, mailbox):
    """Select a mailbox to use
    """
    results = self.conn.select(mailbox)
    if results[0] != "OK":
      raise Exception()
    self.mailbox = mailbox


  def get_message(self, uid):
    """Get a message's text by its UID
    Returns None if not found
    """
    if not uid:
      return None

    params = self.conn.uid("FETCH", uid, "(BODY[1])")
    if not params[1]:
      # Clear from cache
      for subject, s_uid in self.uid_cache.items():
        if s_uid == uid:
          self.uid_cache.pop(subject)
      return None

    data = params[1][0][1]
    dec_data = self.enc.decrypt_message(data)
    return dec_data

  def put_message(self, subject, data):
    """Store a message
    subject is stored as the message's subject
    """

    # Invalidate cache
    if subject in self.uid_cache:
      self.uid_cache.pop(subject)

    enc_data = self.enc.encrypt_message(data)

    msg = email.mime.text.MIMEText(enc_data)
    msg['Subject'] = subject

    results = self.conn.append(self.mailbox, "(\\Seen \\Draft)", time.time(), msg.as_string())

    # Attempt to cache new UID
    # Requires the server to provide APPENDUID statement
    info = results[1][0]
    match = re.search("APPENDUID [0-9]+ ([0-9]+)", info, re.I)
    if match:
      new_uid = match.group(1)
      self.uid_cache[subject] = new_uid


  def delete_message(self, uid):
    """Delete a message by UID
    """
    self.conn.uid("STORE", uid, "+FLAGS", "\\Deleted")

    # Invalidate cache
    for subject, s_uid in self.uid_cache.items():
        if s_uid == uid:
          self.uid_cache.pop(subject)

    # self.conn.expunge()

  def search_by_subject(self, subject):
    """Returns a list of UIDs of messages with given subject
    """
    results = self.conn.uid("SEARCH", "SUBJECT", "\"%s\"" % subject)
    if not results[1]:
      return None
    uids = results[1][0].split(" ")
    if len(uids) == 1 and uids[0] == '':
      return None

    return uids

  def get_uid_by_subject(self, subject):
    """Get the UID of a single message with subject subject
    """
    # Check cache
    if subject in self.uid_cache:
      return self.uid_cache[subject]

    results = self.search_by_subject(subject)
    if not results:
      return None

    self.uid_cache[subject] = results[-1]

    return results[-1]
