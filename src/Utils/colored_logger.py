import logging
import os
import sys
from contextlib import contextmanager
from typing import Callable, Collection, Dict, Union

import colorama
from coloredlogs import ColoredFormatter, converter as AnsiToHtmlConverter
from verboselogs import VerboseLogger

from .utils import classproperty


# ✓ Add support for custom formatters (or choices from ones defined by this module) in Logger()

# ✓ Do not add one-and-the-same handler to logger instance in Logger()
#           (to eliminate duplicate logging output when running module via -m)

# FIXME: Logging is not thread-safe for some reason...

ROOT = 'Root'

try:
    from PyQt5.QtCore import QObject, pyqtSignal
except (ImportError, ModuleNotFoundError):
    pass
else:
    class QtHandler(logging.Handler, QObject):
        logEmittedHtml = pyqtSignal(str)

        def __init__(self, slot, *args, **kwargs):
            logging.Handler.__init__(self, *args, **kwargs)
            QObject.__init__(self)
            self.logEmittedHtml.connect(slot)

        def emit(self, record):
            s = AnsiToHtmlConverter.convert(self.format(record), code=False)
            self.logEmittedHtml.emit(s)


class LogStyle:
    """ Style dictionaries for log records and log format fields
        Used by `ColoredFormatter` to set colors and other style options
    """

    pyCharmRecords = dict(
            spam={'color': 90},
           debug={'color': 'white'},
         verbose={'color': 98},
            info={'color': 'blue'},
          notice={'color': 'magenta'},
         warning={'color': 'yellow'},
         success={'color': 'green'},
           error={'color': 'cyan'},
        critical={'color': 'red'},
    )

    cmdRecords = dict(
            spam={'color': 90},
           debug={'color': 0},
         verbose={'color': 97},
            info={'color': 'blue', 'bold': True},
          notice={'color': 'cyan', 'bold': True},
         warning={'color': 'yellow', 'bold': True},
         success={'color': 'green', 'bold': True},
           error={'color': 'red', 'bold': True},
        critical={'color': 'red', 'bold': True},
    )

    qtRecords = dict(
            spam={'color': 246},
           debug={'color': 240},
         verbose={'color': 234},
            info={'color': 39},
          notice={'color': 21},
         warning={'color': 214},
         success={'color': 34},
           error={'color': 202},
        critical={'color': 196},
    )

    fields = dict(
         asctime={'color': 'white'},
          module={'color': 'white'},
        function={'color': 'white'},
       levelname={'color': 'white'},
            name={'color': 'white'},
    )

    _isRunningInsidePyCharm_ = "PYCHARM_HOSTED" in os.environ
    records = pyCharmRecords if _isRunningInsidePyCharm_ else cmdRecords


LogRecordFormat = '[{asctime}.{msecs:03.0f} {module}:{funcName} {name}] {message}'
DateLogRecordFormat = '[{asctime}.{msecs:03.0f}] {message}'
SimpleLogRecordFormat = '{message}'
LogDateFormat = '%H:%M:%S'


class Formatters:
    basic = logging.Formatter(
            fmt=LogRecordFormat, datefmt=LogDateFormat, style='{')

    colored = ColoredFormatter(
            fmt=LogRecordFormat, datefmt=LogDateFormat, style='{',
            level_styles=LogStyle.records, field_styles=LogStyle.fields)

    simpleColored = ColoredFormatter(
            fmt=SimpleLogRecordFormat, style='{',
            level_styles=LogStyle.records, field_styles=LogStyle.fields)

    qtColored = ColoredFormatter(
            fmt=LogRecordFormat, datefmt=LogDateFormat, style='{',
            level_styles=LogStyle.qtRecords, field_styles=LogStyle.fields)

    simpleQtColored = ColoredFormatter(
            fmt=DateLogRecordFormat, datefmt=LogDateFormat, style='{',
            level_styles=LogStyle.qtRecords, field_styles=LogStyle.fields)


class ColoredLogger(VerboseLogger):
    """ Custom logger class for supplying some convenience features

            .all       - dict with all currently existing loggers (maps name to logger)
            .levels    - dict mapping all logger level names (including extra ones
                             injected by verboselogs module) to their respective levels
            .levelname - returns currently set logging level as string
            .log()     - formats errors as 'ErrorClass: message'
                         provides 'traceback' kwarg as an alias for 'exc_info'
            .disable() - turns all (or all-but-current) loggers off
                         if no args provided, works as CM to temporarily disable logging
            TODO: update this
    """

    consoleHandler: logging.StreamHandler
    fileHandler: logging.FileHandler
    qtHandler: QtHandler

    @property
    def levelname(self):
        """ Returns current logging level as string """
        return logging.getLevelName(self.level)

    def suppressed(self, level: str = None):
        return Logger.suppressed(self.name, level)

    def setFormatting(self, **handlers: logging.Handler):
        """ Set custom logger formatters from given '<handler>=<formatter>' kwargs """
        for name, formatter in handlers.items():
            try:
                handler = getattr(self, f'{name}Handler')
            except AttributeError:
                raise ValueError(f"Logger {self.name} does not have {name} handler")
            handler.setFormatter(formatter)

    def setConsoleHandler(self, formatter=Formatters.colored):
        """ Add StreamHandler with given formatter set (default - verbose colored)
        """
        if hasattr(self, 'consoleHandler'):
            self.handlers.remove(self.consoleHandler)
        self.consoleHandler = logging.StreamHandler()
        if self.name == ROOT:
            self.consoleHandler.setFormatter(Formatters.simpleColored)
        else:
            self.consoleHandler.setFormatter(formatter)
        self.addHandler(self.consoleHandler)

    def setFileHandler(self, path: str, formatter=Formatters.basic):
        """ Add FileHandler with given formatter set (default - verbose w/o coloring)
        """
        if hasattr(self, 'fileHandler'):
            self.handlers.remove(self.fileHandler)
        self.fileHandler = logging.FileHandler(path)
        if self.name != ROOT:
            self.fileHandler.setFormatter(formatter)
        self.addHandler(self.fileHandler)

    def setQtHandler(self, slot: Callable, formatter=Formatters.simpleQtColored):
        if hasattr(self, 'qtHandler'):
            self.handlers.remove(self.qtHandler)
        try:
            self.qtHandler = QtHandler(slot)
        except NameError:
            raise TypeError("QT handler is not available as PyQt5 module has not been found")
        self.qtHandler.setFormatter(formatter)
        self.addHandler(self.qtHandler)

    def _log(self, level, msg, *args, traceback=None, **kwargs):
        """ Override. Formats errors in 'ErrorClass: message' format.
            'traceback' kwarg is an alias for 'exc_info'
        """

        if isinstance(msg, Exception):
            err = msg
            if err.args and err.args[0].strip():
                msg = f'{msg.__class__.__name__}: {msg}'
            else:
                msg = msg.__class__.__name__

        if traceback is True:
            kwargs['exc_info'] = True

        return super()._log(level, msg, *args, **kwargs)


class Logger:
    """ Factory generating loggers with pre-assigned handlers and formatters

        name - Logger name. If not provided, is set to ROOT + record format is just
                   colored message with no format fields set (simpleColorFormatter is used)
        Handlers:
            console - boolean enabling StreamHandler with colored output (colorFormatter is used)
            file    - path providing log file path for FileHandler (basicFormatter is used)
            qt      - PyQt callback to trigger when LogRecord is emitted (htmlColorFormatter is used)
    """

    # Mapping {logger level name: level number value}
    levels: Dict[str, int] = logging._nameToLevel

    # Mapping {logger name: logger-like object} - contains whatever it is in Manager.loggersDict
    all: Dict[str, logging.Logger] = logging.getLoggerClass().manager.loggerDict

    # Mapping {logger name: logger object} - contains only loggers
    loggers: Dict[str, logging.Logger]

    def __new__(cls, name: str = ROOT, console: bool = True, file: str = None, qt: Callable = None):
        """ Create new ColoredLogger or return existing """

        # ▼ Prevent duplicate initializing when Logger() with name provided already exists
        if name in Logger.all:
            return logging.getLogger(name)
        else:
            this: ColoredLogger = logging.getLogger(name)

        if console: this.setConsoleHandler()
        if file: this.setFileHandler(file)
        if qt: this.setQtHandler(qt)

        return this

    @classproperty
    def loggers(cls) -> Dict[str, logging.Logger]:
        """ Dict with all currently existing loggers (maps name to logger)
            All non-logger classes are excluded (like 'PlaceHolder' and 'Adapter')
        """
        return {name: logger for name, logger in cls.all.items() if isinstance(logger, logging.Logger)}

    @classmethod
    @contextmanager
    def suppressed(cls, target: Union[str, Collection[str]] = 'all', level: str = None):
        """ Disables all existing to-the-moment loggers inside its context
                and enables back those which were enabled initially
                TODO: update this
        """

        if target == 'all':
            loggers = cls.loggers.values()
        elif target == 'others':
            loggers = tuple(logger for logger in cls.loggers.values() if logger is not cls)
        elif target is None:
            # Return empty context manager, used if suppression is chosen dynamically
            yield; return
        elif isinstance(target, Collection):
            loggers = tuple(cls.loggers[name] for name in target)
        else:
            loggers = (cls.loggers[target],)

        if level is None:
            savedState = (logger.disabled for logger in loggers)
            for logger in loggers:
                logger.disabled = True
            yield
            for logger, value in zip(loggers, savedState):
                logger.disabled = value

        else:
            savedState = (logger.level for logger in loggers)
            for logger in loggers:
                logger.setLevel(level.upper())
            yield
            for logger, value in zip(loggers, savedState):
                logger.setLevel(value)


logging.setLoggerClass(ColoredLogger)
colorama.init() if sys.stdout.isatty() else colorama.deinit()


if __name__ == '__main__':
    log = Logger('Test')
    log.error("Azaza")
    log.debug("will not show up")

    log2 = Logger('Test2', console=False, qt=print)
    log2.warning('QT!')

    logRoot = Logger()
    logRoot.setLevel('SPAM')
    logRoot.success('Message')
    logRoot.spam('Spam')
    logRoot.notice('Important')

    from .utils import formatDict
    print(f"Logger.all: {formatDict(Logger.all)}")

    print('Sample:')


    if "PYCHARM_HOSTED" not in os.environ:
        input('Type to exit...')
