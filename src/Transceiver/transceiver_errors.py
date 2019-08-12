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
SerialWriteTimeoutError.__doc__ = """ Failed to send data for 'Serial().write_timeout' seconds """


class SerialReadTimeoutError(SerialError):
    """ No data is received for 'Serial().timeout' seconds """


class AddressMismatchError(SerialError):
    """ Address defined in header does not match with host address """


class SerialCommunicationError(VerboseError, SerialError):
    """ Communication-level error, indicate failure in packet transmission process """


class BadDataError(SerialCommunicationError):
    """ Data received over serial port is corrupted """


class BadRfcError(SerialCommunicationError):
    """ RFC checksum validation failed """


class BadLrcError(SerialCommunicationError):
    """ DSP protocol: LRC checksum validation failed """
