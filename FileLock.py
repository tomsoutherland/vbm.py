import os
import errno


class FileLockException(Exception):
    pass

class FileLock(object):

    def __init__(self, file_name, timeout=10, delay=.05):
        """ Prepare the file locker. Specify the file to lock and optionally
            the maximum timeout and the delay between each attempt to lock.
        """
        if timeout is not None and delay is None:
            raise ValueError("If timeout is not None, then delay must not be None.")
        self.is_locked = False
        self.lockfile = os.path.join(os.getcwd(), "%s.lock" % file_name)
        self.file_name = file_name

    def acquire(self):
        try:
            self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            self.is_locked = True  # moved to ensure tag only when locked
        except OSError as e:
            print("Unable to acquire lock: ", self.lockfile, "\nOS Error: ", e.strerror)
            exit(1)

    def release(self):
        if self.is_locked:
            os.close(self.fd)
            os.unlink(self.lockfile)
            self.is_locked = False

    def __enter__(self):
        if not self.is_locked:
            self.acquire()
        return self

    def __exit__(self, type, value, traceback):
        if self.is_locked:
            self.release()

    def __del__(self):
        self.release()