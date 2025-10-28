# This code is extracted from IBL.Utils.Formats

from typing import Optional

class I18N:
    """
    Fake internationalization class
    """
    @staticmethod
    def tr(obj, text):
        return text

class ASCII:

    SOH = b"\x01"
    ETX = b"\x03"
    CR = b"\x0D"
    LF = b"\x0A"
    CRCRLF = b"\x0D\x0D\x0A"

############ WMO writer #########################################################
"""
WMO file formats description can be found in
Manual on the Global Telecommunication System (WMO-No. 386),
chapter SFTP/FTP procedures and file naming convention, page 137

Basic syntax of WMO files

WMO 00 with CSN (Channel Sequence Number)
00000000-00-SOH-CRCRLF-CSN(NN)-CRCRLF-heading-CRCRLF-body-CRCRLF-ETX

WMO 00 without CSN
00000000-00-SOH-CRCRLF-heading-CRCRLF-body-CRCRLF-ETX

WMO01
00000000-01-CRCRLF-heading-CRCRLF-body

"""

class WMOWriter:
    """
    ### Creates WMO00 and WMO01 files. ###
    Usage is as follows:
    * open the writer <br>
    `WMOWriter writer(fname)`
    * wite the data
    ```
        writer.write(mymessage, sequence_number<optional>)
        writer.write(_otherwmomessage_)
    ```
    * close the writer
        `writer.close()`
    """

    def __init__(self, fname=None, file=None, formatId: int = 0) -> None:
        self.m_f = None
        if fname is not None:
            self.m_f = open(fname, "w+b")
            self.mb_fileOwner = True
        else:
            self.m_f = file
            self.mb_fileOwner = False
        self.i_formatId = formatId
        self.i_csn: Optional[int] = None
        self.b_zeroTail = True

    def _formatIdAsBytes(self) -> bytes:
        if self.i_formatId > 0:
            return b"01"
        return b"00"

    @property
    def formatId(self) -> int:
        """
        Format identifier
        """
        return self.i_formatId

    @formatId.setter
    def formatId(self, value: int):
        self.i_formatId = value

    @property
    def zeroTail(self) -> bool:
        """
        Specifies if zero tail should be written
        """
        return self.b_zeroTail

    @zeroTail.setter
    def zeroTail(self, value: bool):
        self.b_zeroTail = value

    def __del__(self):
        self.close()

    def buildFromHeaderBody(self, s_header: bytes, s_body: bytes, i_csn: Optional[int] = None) -> bytes:
        msgAsByteArray = self.joinHeaderAndBody(s_header, s_body)
        return self.buildContent(msgAsByteArray, i_csn)

    def writeFromHeaderBody(self, s_header: bytes, s_body: bytes, i_csn: Optional[int] = None) -> None:
        if self.m_f is None:
            raise RuntimeError(I18N.tr(self, "WMO {self.formatId:02d} Writer is already closed"))
        content = self.buildFromHeaderBody(s_header, s_body, i_csn)
        self.m_f.write(content)

    def write(self, s_headerAndBody: bytes, i_csn: Optional[int] = None) -> None:
        if self.m_f is None:
            raise RuntimeError(I18N.tr(self, "WMO {self.formatId:02d} Writer is already closed"))
        content = self.buildContent(s_headerAndBody, i_csn)
        self.m_f.write(content)

    def close(self) -> None:
        if self.m_f is None:
            return
        if self.b_zeroTail:
            self.m_f.write(b"00000000")
            self.m_f.write(self._formatIdAsBytes())
        if self.mb_fileOwner:
            self.m_f.close()
        self.m_f = None

    def buildContent(self, s_headerAndBody: bytes, i_csn: Optional[int] = None) -> bytes:
        A = ASCII
        oneMessage = bytearray()
        message = bytearray()
        if self.i_formatId == 0:
            # build WMO00
            message.extend(A.SOH)
            message.extend(A.CRCRLF)
            if i_csn is not None:
                # 00000000-00-SOH-CRCRLF-NNN(NN)-CRCRLF-heading-CRCRLF-body-CRCRLF-ETX
                if i_csn > 999:
                    s_csn = bytes(f"{i_csn:05d}", "ascii")
                else:
                    s_csn = bytes(f"{i_csn:03d}", "ascii")
                message.extend(s_csn)
                message.extend(A.CRCRLF)
            # else 00000000-00-SOH-CRCRLF-heading-CRCRLF-body-CRCRLF-ETX
            message.extend(s_headerAndBody)
            message.extend(A.CRCRLF)
            message.extend(A.ETX)
        else:
            # build WMO01
            # 00000000-01-CRCRLF-heading-CRCRLF-body
            message.extend(A.CRCRLF)
            message.extend(s_headerAndBody)
        oneMessage.extend(bytes(f"{len(message):08d}", "ascii"))
        oneMessage.extend(self._formatIdAsBytes())
        oneMessage.extend(message)  # body
        return bytes(oneMessage)

    def joinHeaderAndBody(self, s_header: bytes, s_body: bytes) -> bytes:
        msgAsByteArray = bytearray(s_header)
        msgAsByteArray.extend(ASCII.CRCRLF)
        msgAsByteArray.extend(s_body)
        return bytes(msgAsByteArray)


############ WMO 01 format writer #########################################################


class WMO01Writer:
    """
    WMO01 writer of data.

    Usage is as follows:
        # open the writer
        WMO01Writer writer(fname)
        # write the data
        writer.write(mymessage)
        writer.write(otherwmomessage)
        # close the writer
        writer.close()
    """

    def __init__(self, fname=None, file=None):
        self.writer = WMOWriter(fname, file, formatId=1)

    @property
    def formatId(self):
        return self.writer.formatId

    def close(self):
        self.writer.close()

    def write(self, s_headerAndBody: bytes):
        self.writer.write(s_headerAndBody)

    def writeFromHeaderBody(self, s_header: bytes, s_body: bytes) -> None:
        self.writer.writeFromHeaderBody(s_header, s_body, i_csn=None)

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