from imapfs.fs import IMAPFS

fs = IMAPFS()
fs.multithreaded = 0

fs.parser.add_option(mountopt="host", metavar="HOSTNAME", default="localhost", help="Hostname of IMAP server")
fs.parser.add_option(mountopt="port", metavar="PORT", default=993, help="Port of IMAP server [default: %default]")
fs.parser.add_option(mountopt="user", metavar="USERNAME", help="IMAP username to use")
fs.parser.add_option(mountopt="password", metavar="PASSWORD", help="IMAP password to use")
fs.parser.add_option(mountopt="key", metavar="KEY", help="Encryption key")
fs.parser.add_option(mountopt="rounds", metavar="ROUNDS", default=10000, help="Number of PBKDF2 iterations [default: %default]")
fs.parser.add_option(mountopt="mailbox", metavar="MAILBOX", default="INBOX", help="Mailbox name the files are stored in [default: %default]")

fs.parse(values=fs, errex=1)
ret = fs.main()
exit(ret)
