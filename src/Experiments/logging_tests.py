import logging

import sys
import os

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton, QPlainTextEdit
from PyQt5Utils import install_exhook

sys.path.insert(0, r"D:\GLEB\Python\PyUtils\src")

import colorama

# all = log.manager.loggerDict
# levels = logging._nameToLevel
# .levelname = log.getLevelName(log.level)
# .disableOthers()
# .setOthersTo()

pyCharmMsgsStyle = dict(
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

cmdMsgsStyle = dict(
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

qtMsgsStyle = dict(
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

fieldsStyle = dict(
    asctime    ={'color': 'white'},
    module     ={'color': 'white'},
    function   ={'color': 'white'},
    levelname  ={'color': 'white'},
    name       ={'color': 'white'},
)

logRecordFormat = '[{asctime}.{msecs:03.0f} {module}:{funcName} {name}] {message}'
logDateFormat = '%H:%M:%S'

isRunningInPyCharm = "PYCHARM_HOSTED" in os.environ
msgsStyle = pyCharmMsgsStyle if isRunningInPyCharm else cmdMsgsStyle


def main():
    import colorlog
    if not sys.stdout.isatty():
        colorama.deinit()

    handler = colorlog.StreamHandler()
    h = logging.FileHandler('temp.txt')
    fmtstr = '[{asctime}.{msecs:03.0f} {module}:{funcName} {name}] {log_color}{message}'
    handler.setFormatter(colorlog.ColoredFormatter(fmtstr, datefmt='%H:%M:%S', style='{'))
    h.setFormatter(logging.Formatter('{name}: {message}', style='{'))
    log = colorlog.getLogger('Test')
    log.addHandler(handler)
    log.addHandler(h)
    log.setLevel("DEBUG")

    log.debug('db')
    log.info('info')
    log.warning('warn')
    log.error(RuntimeError('error'))
    log.fatal('fatal')
    print('\x1b[34mTEXT\x1b[0m')
    sys.stdout.write('\x1b[32mLOOOL\x1b[0m\n')

    for i in range(0, 16):
        for j in range(0, 16):
            code = str(i * 16 + j)
            sys.stdout.write("\x1b[38;5;" + code + "m " + code.ljust(4))
        print("\x1b[0m")


def coloredLoggerTest():
    import coloredlogs
    import verboselogs

    verboselogs.install()
    coloredlogs.install(
        level='SPAM',
        style='{',
        fmt=logRecordFormat,
        datefmt=logDateFormat,
        level_styles=msgsStyle,
        field_styles=fieldsStyle,
    )

    if not sys.stdout.isatty():
        colorama.deinit()

    logger = logging.getLogger("Test")
    logger.spam("SPAM")
    logger.debug("DEBUG")
    logger.verbose("VERBOSE")
    logger.info("INFO")
    logger.notice("NOTICE")
    logger.warning("WARNING")
    logger.success("SUCCESS")
    logger.error("ERROR")
    logger.critical("CRITICAL")
    print("PRINT")

    from coloredlogs import converter
    print(converter.convert('\x1b[34mTEXT\x1b[0m', code=False))


def coloredFormatterTest():
    import coloredlogs
    import verboselogs

    verboselogs.install()

    if sys.stdout.isatty():
        colorama.init()
    else:
        colorama.deinit()

    logger = logging.getLogger("Test")
    cmdHandler = logging.StreamHandler()
    colorFormatter = coloredlogs.ColoredFormatter(
            fmt=logRecordFormat, datefmt=logDateFormat, style='{', level_styles=msgsStyle, field_styles=fieldsStyle)
    cmdHandler.setFormatter(colorFormatter)
    fileHandler = logging.FileHandler('testlog.txt')
    fileHandler.setFormatter(logging.Formatter(
            fmt=logRecordFormat, datefmt=logDateFormat, style='{'))
    logger.addHandler(cmdHandler)
    logger.addHandler(fileHandler)
    logger.setLevel('SPAM')

    logger.debug('')
    logger.spam("SPAM")
    logger.debug("DEBUG")
    logger.verbose("VERBOSE")
    logger.info("INFO")
    logger.notice("NOTICE")
    logger.warning("WARNING")
    logger.success("SUCCESS")
    logger.error("ERROR")
    logger.critical("CRITICAL")
    try: raise RuntimeError('DEBUG_EXCEPTION')
    except Exception as e: logger.debug(e, exc_info=True)
    print("PRINT")

    runQtEnv(logger)

    print('end.')


class QtHandler(logging.Handler, QObject):

    logEmittedHtml = pyqtSignal(str)

    def __init__(self, parent, slot, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        QObject.__init__(self, parent)
        self.logEmittedHtml.connect(slot)

    def emit(self, record):
        from coloredlogs import converter
        s = converter.convert(self.format(record), code=False)
        print(s)
        self.logEmittedHtml.emit(s)


def runQtEnv(logger):
    from itertools import cycle
    import coloredlogs

    install_exhook()
    logMethods = ('spam', 'debug', 'verbose', 'info', 'notice', 'warning', 'success', 'error', 'critical', 'exception')
    cycleLvl = cycle(logMethods)

    def log():
        lvl = cycleLvl.__next__()
        getattr(logger, lvl)(f"Button clicked with {lvl.upper()}")

    app = QApplication([])
    app.setStyle('fusion')

    # parent
    p = QWidget()
    p.layout = QHBoxLayout()
    p.layout.setContentsMargins(*(p.layout.spacing(),) * 4)
    p.setLayout(p.layout)

    te = QPlainTextEdit(p)
    te.setReadOnly(True)
    b = QPushButton("Log", p)

    qtHandler = QtHandler(p, te.appendHtml)
    htmlColorFormatter = coloredlogs.ColoredFormatter(
            fmt=logRecordFormat, datefmt=logDateFormat, style='{', level_styles=qtMsgsStyle, field_styles=fieldsStyle)
    qtHandler.setFormatter(htmlColorFormatter)
    logger.addHandler(qtHandler)
    b.clicked.connect(log)

    p.layout.addWidget(te)
    p.layout.addWidget(b)
    p.layout.addWidget(QPushButton("Dummy", p))

    p.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    try:
        coloredFormatterTest()
    except Exception as e:
        print(e)
    finally:
        if "PYCHARM_HOSTED" not in os.environ: input('...')