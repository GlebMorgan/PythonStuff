import logging
import sys
import traceback
from os import linesep

from colored_logger import ColorHandler
from utils import bytewise


C = CRITICAL = FATAL = logging.CRITICAL
E = ERROR = logging.ERROR
W = WARN = WARNING = logging.WARNING
I = INFO = logging.INFO
D = DEBUG = logging.DEBUG
N = NOTSET = logging.NOTSET


class Logger:

    LOGGERS = {}

    def __new__(cls, name):
        if (not sys.stdout.isatty()):
            handler = ColorHandler(format="[{name}: {module} → {funcName}] {message}")
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[{name}: {module} → {funcName}] {message}", style='{'))
        logging.setLoggerClass(cls.MyLogger)
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)
        cls.LOGGERS[log.name] = log
        return log

    class MyLogger(logging.Logger):

        def __init__(self, loggerName):
            super().__init__(loggerName)

        def showError(self, error):
            self.error(f"{error.__class__.__name__}: {error.args[0] if error.args else '<No details>'}" +
                       (linesep + f"{error.dataname}: {bytewise(error.data)}" if hasattr(error, 'data') else ''))

        def showStackTrace(self, error):
            info = f"{error.__class__.__name__}: {error.args[0] if error.args else '<No details>'}"
            info += linesep + f"{error.dataname}: {bytewise(error.data)}" if hasattr(error, 'data') else '' + linesep
            info += linesep.join(line.strip() for line in traceback.format_tb(error.__traceback__) if line)
            self.error(info)

        dataerror = showError
        stacktrace = showStackTrace


getLogger = Logger


if __name__ == '__main__':
    l = Logger("Test")
    l.debug("Debug msg")
    l.dataerror(Exception("test exception"))

    def f(): raise Exception("test stack trace")

    try:
        f()
    except Exception as e:
        l.stacktrace(e)

    print(f"LOGGERS: {Logger.LOGGERS}")

    Logger.LOGGERS['Test'].setLevel(INFO)
    l.debug("Test debug msg")
    l.warning("Test warning msg")
    l.critical("Test critical msg")
