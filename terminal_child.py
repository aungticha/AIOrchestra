"""Acquire a controlling PTY without preexec_fn in the threaded server."""
import os
import sys
import fcntl
import termios
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
