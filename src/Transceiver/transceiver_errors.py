import serial
from Utils import alias


class VerboseError:
    def __init__(self, *args, data=None, dataname=None):
        if (data is not None):
            if (dataname is None): self.dataname = "Bytes"
            else: self.dataname = dataname
            self.data = data
        super().__init__(*args)


SerialError = alias(serial.serialutil.SerialException)


SerialWriteTimeoutError = alias(serial.serialutil.SerialTimeoutException)
SerialWriteTimeoutError.__doc__ = """ Error: failed to send data for 'Serial().write_timeout' seconds """


class SerialReadTimeoutError(SerialError):
    """ Error: no data is received for 'Serial().timeout' seconds """


class AddressMismatchError(SerialError):
    """ Error: address defined in header does not match with host address """


class SerialCommunicationError(VerboseError, SerialError):
    """ Error: failure in packet transmission process (data-link layer) """


class BadDataError(SerialCommunicationError):
    """ Error: data received over serial port is corrupted """


class BadCrcError(SerialCommunicationError):
    """ Error: checksum validation failed """


class BadRfcError(BadCrcError):
    """ Error: RFC checksum validation failed """


class BadLrcError(BadCrcError):
    """ Error: LRC checksum validation failed """
