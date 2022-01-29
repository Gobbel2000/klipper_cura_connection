import email
import logging
import os

logger = logging.getLogger("klipper_cura_connection")

class MimeParser:
    """
    Parser for MIME messages which directly writes attached files.

    When calling parse() this class will parse all parts of a multipart
    MIME message, converting the parts to email.Message objects.
    If a part contains a file it is not added as a payload to that
    Message object but instead directly written to the directory
    specified by out_dir.
    If the file already exists and overwrite is set to False, it will
    be renamed (see _unique_path() for details).

    Arguments:
    fp          The file pointer to parse from
    boundary    The MIME boundary, as specified in the main headers
    length      Length of the body, as specified in the main headers
    out_dir     The directory where any files will be written into
    overwrite   In case a file with the same name exists overwrite it
                if True, write to a unique, indexed name otherwise.
                Defaults to True.
    """

    HEADERS = 0
    BODY = 1
    FILE = 2

    def __init__(self, fp, boundary, length, out_dir, overwrite=True):
        self.fp = fp
        self.boundary = boundary.encode()
        self.bytes_left = length
        self.out_dir = out_dir
        self.overwrite = overwrite
        self.submessages = []
        self.written_files = [] # All files that were written

        # What we are reading right now. One of:
        # self.HEADERS, self.BODY, self.FILE (0, 1, 2)
        self._state = None
        self._current_headers = b""
        self._current_body = b""
        self.fpath = "" # Path to the file to write to

    def parse(self):
        """
        Parse the entire file, returning a list of all submessages
        including headers and bodies, except for transmitted files
        which are directly written to disk.
        """
        while True:
            line = self.fp.readline()
            self.bytes_left -= len(line)
            try:
                self._parse_line(line)
            except StopIteration:
                break
        return self.submessages, self.written_files

    def _parse_line(self, line):
        """
        Parse a single line by first checking for self._state changes.
        Raising StopIteration breaks the loop in self.parse().
        """
        # Previous message is finished
        if line.startswith(b"--" + self.boundary):
            if self._current_body:
                self.submessages[-1].set_payload(
                        self._current_body.rstrip(b"\r\n"))
                self._current_body = b""
            self._state = self.HEADERS # Read headers next
            # This is the last line of the MIME message
            if line.strip() == b"--" + self.boundary + b"--":
                raise StopIteration()
        # Parse dependent on _state
        elif self._state == self.HEADERS:
            self._parse_headers(line)
        elif self._state == self.BODY:
            self._parse_body(line)

        # FILE state is set after parsing headers and should be
        # handled before reading the next line.
        if self._state == self.FILE:
            self._write_file()

    def _parse_headers(self, line):
        """Add the new line to the headers or parse the full header"""
        if line == b"\r\n": # End of headers
            headers_message = email.message_from_bytes(self._current_headers)
            self._current_headers = b""
            self.submessages.append(headers_message)
            self._start_body(headers_message)
        else:
            self._current_headers += line

    def _parse_body(self, line):
        self._current_body += line

    def _write_file(self):
        """
        Write the file following in fp directly to the disk.
        This does not happen line by line because with a lot of very
        short lines that is quite inefficient. Instead the file is copied
        in blocks with a size of 1024 bytes.
        Then parse the remaining lines that have been read into the
        buffer but do not belong to the file (everything past the first
        occurance of boundary).
        """
        # Write to this first to avoid the file browser crashing
        temp_path = self.fpath + ".part"

        logger.debug("Writing file: %s", self.fpath)
        self.written_files.append(self.fpath)

        # Use two buffers in case the boundary gets cut in half
        buf1 = self._safe_read()
        buf2 = self._safe_read()
        with open(temp_path, "wb") as write_fp:
            while self.boundary not in buf1 + buf2:
                write_fp.write(buf1)
                buf1 = buf2
                buf2 = self._safe_read()
            if self.bytes_left != 0:
                # Catch the rest of the last line
                remaining_lines = (
                        buf1 + buf2 + self.fp.readline()).splitlines(True)
            else:
                remaining_lines = (buf1 + buf2).splitlines(True)

            # We need an exception for the last line of the file to strip
            # the trailing "\r\n" (<CR><LF>)
            prev_line = b""
            # We take the index with us so we know where to pick up below
            for i, line in enumerate(remaining_lines):
                if self.boundary not in line:
                    write_fp.write(prev_line)
                    prev_line = line
                else:
                    # Now write the last line, but stripped
                    write_fp.write(prev_line.rstrip(b"\r\n"))
                    break
        # Rename the written file from [fpath].part to [fpath]
        os.rename(temp_path, self.fpath)

        # Parse all other lines left in the buffer normally
        # When reaching the end, StopIteration will be propagated up to parse()
        for line in remaining_lines[i:]:
            self._parse_line(line)

    def _safe_read(self):
        """Read a chunk that will not go past EOF"""
        buflen = min(self.bytes_left, 1024)
        self.bytes_left -= buflen
        return self.fp.read(buflen)

    def _start_body(self, headers):
        """Initiate reading of the body depending on whether it is a file"""
        name = headers.get_param("name", header="Content-Disposition")
        if name == "file":
            self.fpath = os.path.join(self.out_dir, headers.get_filename())
            if not self.overwrite:
                self.fpath = self._unique_path(self.fpath)
            self._state = self.FILE
        else:
            self._state = self.BODY

    @staticmethod
    def _unique_path(path):
        """
        Adjust a filename so that it doesn't overwrite an existing file.
        For example, if /path/to/file.txt exists, this function will
        return '/path/to/file-1.txt', then '/path/to/file-2.txt'
        and so on.
        """
        if not os.path.exists(path):
            return path
        root, ext = os.path.splitext(path)
        index = 1
        path = "{}-{}{}".format(root, index, ext)
        while os.path.exists(path):
            path = "{}-{}{}".format(root, index, ext)
            index += 1
        return path
