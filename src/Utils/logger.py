import logging
import sys
import traceback
from os import linesep

from .color_handler import ColorHandler
from .utils import bytewise


# - ALREADY EXISTS - Add sub-loggers to enable/disable logging of specific parts of code

# ✗ Coloring option based on logger instance, not logging level


C = CRITICAL = FATAL = logging.CRITICAL
E = ERROR = logging.ERROR
W = WARN = WARNING = logging.WARNING
I = INFO = logging.INFO
D = DEBUG = logging.DEBUG
N = NOTSET = logging.NOTSET


class Logger:

    LOGGERS = {}
    LEVELS = logging._nameToLevel
    LEVELS_SHORT = {
        'C': 'CRITICAL',
        'F': 'FATAL',
        'E': 'ERROR',
        'W': 'WARNING',
        'I': 'INFO',
        'D': 'DEBUG',
        'N': 'NOTSET',
    }

    def __new__(cls, name, mode=None):
        logging.setLoggerClass(cls.MyLogger)
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        if mode == 'noFormatting': format = ''
        else: format = "[{name}: {module} → {funcName}] {message}"
        handler = ColorHandler(colorize=log.insidePyCharm, format=format)
        log.addHandler(handler)

        cls.LOGGERS[log.name] = log
        return log

    class MyLogger(logging.Logger):

        def __init__(self, loggerName):
            super().__init__(loggerName)
            self.insidePyCharm = not sys.stdout.isatty()
            self.noNewlineAdded = False
            self.colorHandler = None

        def showError(self, error, level='error'):
            self.log(logging._nameToLevel[level.upper()],
                     f"{error.__class__.__name__}: {error.args[0] if error.args else '<No details>'}" +
                     linesep + (f"{error.dataname}: {bytewise(error.data)}" if hasattr(error, 'data') else ''))

        def showStackTrace(self, error, level='ERROR'):
            info = f"{error.__class__.__name__}: {error.args[0] if error.args else '<No details>'}"
            info += linesep + (f"{error.dataname}: {bytewise(error.data)}" if hasattr(error, 'data') else '') + linesep
            info += linesep.join(line.strip() for line in traceback.format_tb(error.__traceback__) if line)
            error.__traceback__ = None  # ◄ NOTE: if remove this line, traceback recursively repeats itself
                                        #         under undefined circumstances (when in a loop, s)
            self.log(logging._nameToLevel[level.upper()], info)

        def _log(self, *args, repeat=False, **kwargs):
            """ Adds carriage return before log entry if repeat is integer > 0 """
            if self.insidePyCharm:
                super()._log(*args, **kwargs)
            else:
                if not self.colorHandler:
                    self.colorHandler = next((handler for handler in self.handlers if isinstance(handler, ColorHandler)))
                if repeat is False:
                    self.colorHandler.terminator = '\n'
                    if self.noNewlineAdded:
                        self.colorHandler.stream.write('\n')
                        self.noNewlineAdded = False
                else:
                    if not self.noNewlineAdded:
                        self.colorHandler.terminator = ''
                        self.noNewlineAdded = True
                    else:
                        self.colorHandler.stream.write('\r')
                super()._log(*args, **kwargs)

        @property
        def levelName(self): return logging._levelToName[self.level]

        dataerror = showError
        stacktrace = showStackTrace

        def disableOthers(self):
            for logger in Logger.LOGGERS.values():
                if logger is not self:
                    logger.disabled = True

        def setOthersTo(self, level):
            for logger in Logger.LOGGERS.values():
                if logger is not self:
                    logger.setLevel(level)


getLogger = Logger


if __name__ == '__main__':
    from time import sleep
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

    print(f"Inside PyCharm: {l.insidePyCharm}")

    for i in range(5):
        l.info(f"Message #{i+1}", repeat=i)
        sleep(0.1)
    l.info("END")

'''
import time
from logger import Logger
l = Logger("CMD")

def f():
  for i in range(10):
    l.info("Msg #" + str(i+1), repeat = i)
    import time
    time.sleep(0.05)
  l.info("DONE")
'''