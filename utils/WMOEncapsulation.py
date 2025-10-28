# This code is extracted from IBL.Utils.Formats

class I18N:
    """
    Fake internationalization class
    """
    @staticmethod
    def tr(obj, text):
        return text

class WMOReader:
    """
    ### Reads WMO01 and WMO00 files.

    Usage is as follows:
        open the reader:
            WMOReader reader(fname, b_requireZeroTail = False)
        read the messages
            ls_messages = reader.read()
        where:
            fname: name of a WMO file
            ls_messages: list[bytes]
            b_requireZeroTail: specifies if tail i.e. '0000000001' is expected
            Exception with error WMOReader unexpected end of file' will be
            thrown if zero tail will be missing.

        File format identification is determined from the first message in a file and
        is stored in 'reader.wmoFormatId'
    """

    @property
    def formatId(self) -> int:
        """
        Returns WMO file format identifier.
        It is determined from format identifier of the first message in the file.
        """
        return self.i_formatId

    def __init__(self, fname=None, file=None, b_requireZeroTail=True):
        self.b_requireZeroTail = b_requireZeroTail
        self.i_formatId = None  # 0/1 =  WMO file format 00/01
        if fname is not None:
            self.file = open(fname, "rb")
        else:
            self.file = file
        self.s_eofError = I18N.tr(self, "WMOReader unexpected end of file")

    def __del__(self):
        self._close()

    def __iter__(self):
        while True:
            i_messageSize = self._readMessageSize()
            if i_messageSize == 0:
                break
            yield self._readMessage(i_messageSize)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

    def _close(self):
        if self.file:
            self.file.close()
            self.file = None

    def _readMessageSize(self) -> int:
        """
        Returns size of a next message
        """
        buffer = self.file.read(10)
        i_messageSize = -1
        if type(buffer) != bytes:
            raise RuntimeError(I18N.tr(self, "File was not open for reading binary data."))
        if len(buffer) != 10:
            if self.b_requireZeroTail:
                raise RuntimeError(self.s_eofError)
            else:
                return 0
        try:
            i_messageSize = int(buffer[:-2])
            if self.i_formatId is None:
                self.i_formatId = int(buffer[-2:])
        except ValueError:
            raise RuntimeError(I18N.tr(self, "Invalid WMO preamble '{}'.").format(str(buffer, "ascii")))
        # get rid off the trailing \r\r\n sequence if any
        i_pos = self.file.tell()
        buffer = self.file.read(3)
        if buffer == b"\r\r\n":
            i_messageSize -= 3
        else:
            self.file.seek(i_pos)
        return i_messageSize

    def _readMessage(self, i_messageSize) -> bytes:
        buffer = self.file.read(i_messageSize)
        if len(buffer) < i_messageSize:
            raise RuntimeError(self.s_eofError)
        return buffer

    def read(self) -> list[bytes]:
        if self.file is None:
            raise RuntimeError(I18N.tr(self, "WMOReader is already closed"))
        ls_messages = []
        try:
            while True:
                i_messageSize = self._readMessageSize()
                if i_messageSize == 0:
                    # End of file
                    break
                s_message = self._readMessage(i_messageSize)
                ls_messages.append(s_message)
        finally:
            self._close()
        return ls_messages


############ WMO 01 format reader #########################################################


class WMO01Reader(WMOReader):
    """
    WMO01 reader of data.

    This is a sublclass of WMOReader class for backwards compatibility.
    Inherits all methods and varibales.

    Usage is as follows:
        # open the reader
        WMO01reader reader(fname)
        # read the messages
        ls_messages = reader.read()

        b_requireZeroTail = specifies if tail '0000000001' is expected
    """

    def __init__(self, fname=None, file=None, b_requireZeroTail=True):
        super().__init__(fname, file, b_requireZeroTail)