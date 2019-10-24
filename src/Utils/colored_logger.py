import logging
import os
import sys
from contextlib import contextmanager
from typing import List, Callable

import colorama
from coloredlogs import ColoredFormatter, converter as AnsiToHtmlConverter
from verboselogs import VerboseLogger

from .utils import classproperty


colorama.init() if sys.stdout.isatty() else colorama.deinit()


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
        spam    ={'color': 90},
        debug   ={'color': 'white'},
        verbose ={'color': 98},
        info    ={'color': 'blue'},
        notice  ={'color': 'magenta'},
        warning ={'color': 'yellow'},
        success ={'color': 'green'},
        error   ={'color': 'cyan'},
        critical={'color': 'red'},
    )

    cmdRecords = dict(
        spam    ={'color': 90},
        debug   ={'color': 0},
        verbose ={'color': 97},
        info    ={'color': 'blue', 'bold': True},
        notice  ={'color': 'cyan', 'bold': True},
        warning ={'color': 'yellow', 'bold': True},
        success ={'color': 'green', 'bold': True},
        error   ={'color': 'red', 'bold': True},
        critical={'color': 'red', 'bold': True},
    )

    qtRecords = dict(
        spam    ={'color': 246},
        debug   ={'color': 240},
        verbose ={'color': 234},
        info    ={'color': 39},
        notice  ={'color': 21},
        warning ={'color': 214},
        success ={'color': 34},
        error   ={'color': 202},
        critical={'color': 196},
    )

    fields = dict(
        asctime    ={'color': 'white'},
        module     ={'color': 'white'},
        function   ={'color': 'white'},
        levelname  ={'color': 'white'},
        name       ={'color': 'white'},
    )

    _isRunningInsidePyCharm_ = "PYCHARM_HOSTED" in os.environ
    records = pyCharmRecords if _isRunningInsidePyCharm_ else cmdRecords


LogRecordFormat = '[{asctime}.{msecs:03.0f} {module}:{funcName} {name}] {message}'
LogDateFormat = '%H:%M:%S'

basicFormatter = logging.Formatter(
        fmt=LogRecordFormat, datefmt=LogDateFormat, style='{')

colorFormatter = ColoredFormatter(
        fmt=LogRecordFormat, datefmt=LogDateFormat, style='{',
        level_styles=LogStyle.records, field_styles=LogStyle.fields)

simpleColorFormatter = ColoredFormatter(
        fmt='{message}', style='{',
        level_styles=LogStyle.records, field_styles=LogStyle.fields)

htmlColorFormatter = ColoredFormatter(
        fmt=LogRecordFormat, datefmt=LogDateFormat, style='{',
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
    """

    """ Mapping {logger level name: respective level value} """
    levels = logging._nameToLevel

    @classproperty
    def all(cls):
        """ Dict with all currently existing loggers (maps name to logger) """
        return cls.manager.loggerDict

    @property
    def levelname(self):
        """ Returns current logging level as string """
        return logging.getLevelName(self.level)

    def log(self, level, msg, *args, traceback=None, **kwargs):
        """ Override. Formats errors in 'ErrorClass: message' format
                'traceback' kwarg is an alias for 'exc_info'
        """
        if isinstance(msg, Exception):
            msg = f'{msg.__class__}: {msg}'
        if traceback is True:
            kwargs['exc_info'] = True
        return super().log(level, msg, *args, **kwargs)

    @classmethod
    def disable(cls, option: str = None):
        """ Disable specified loggers among currently instantiated
            Options: 'all', 'others', <None>
            If no option provided, returns a context manager
                that disables all existing to-the-moment loggers inside its context
        """

        if option is None:
            return cls._disableCM_()
        elif option == 'all':
            for logger in cls.all.values():
                logger.disabled = True
        elif option == 'others':
            for logger in cls.all.values():
                if logger is not cls:
                    logger.disabled = True

    @classmethod
    @contextmanager
    def _disableCM_(cls):
        """ Disables all existing to-the-moment loggers inside its context
                and enables back those which were enabled initially
        """
        saved_states: List[logging.Logger] = []
        for logger in cls.all.values():
            if logger.disabled is False:
                saved_states.append(logger)
                logger.disabled = True
        yield
        for logger in saved_states:
            logger.disabled = False


def Logger(name: str = 'root', console: bool = True, file: str = None, qt: Callable = None):
    """ Factory generating loggers with pre-assigned handlers and formatters

        name - Logger name. If not provided, root logger is used, whose record format
                   is just colored message with no format fields set (simpleColorFormatter is used)
        Handlers:
            console - boolean enabling StreamHandler with colored output (colorFormatter is used)
            file    - path providing log file path for FileHandler (basicFormatter is used)
            qt      - PyQt callback to trigger when LogRecord is emitted (htmlColorFormatter is used)
    """

    logging.setLoggerClass(ColoredLogger)
    this = logging.getLogger(name)

    if console:
        consoleHandler = logging.StreamHandler()
        if name != 'root':
            consoleHandler.setFormatter(colorFormatter)
        else:
            consoleHandler.setFormatter(simpleColorFormatter)
        this.addHandler(consoleHandler)
    if file:
        fileHandler = logging.FileHandler(file)
        if name != 'root':
            fileHandler.setFormatter(basicFormatter)
        this.addHandler(fileHandler)
    if qt:
        try:
            qtHandler = QtHandler(qt)
        except NameError:
            raise TypeError("QT handler is not available as PyQt5 module has not been found")
        qtHandler.setFormatter(htmlColorFormatter)
        this.addHandler(qtHandler)
    return this


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

    if "PYCHARM_HOSTED" not in os.environ:
        input('Type to exit...')
