from __future__ import annotations as annotations_feature
from enum import Enum
from functools import wraps, partial, partialmethod
from typing import Union, Dict, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette, QValidator
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QPushButton
from Utils import Logger, legacy

log = Logger("Colorer")


# TESTME: buttons colorizing

# TODO: choose colors for blinking


BACKGROUND_COLOR = 'white'
BLINKING_DURATION = 120  # ms
BLUR_RADIUS = 10
FADE_TIME = 200  # ms
FADE_STAGES = 20


class DisplayColor(Enum):

    White = 'white'
    Black = 'black'
    Red = 'orangered'
    Green = 'forestgreen'
    Blue = 'mediumblue'

    HighlightGreen = 'limegreen'
    HighlightBlue = 'deepskyblue'
    HighlightRed = 'red'

    Normal = 'black'
    Background = BACKGROUND_COLOR


class BlinkingValidator(QValidator):
    def __init__(self, owner):
        super().__init__()
        self.colorer = owner
        self.targetValidator = self.colorer.owner.validator()

    def validate(self, text, pos):
        state, text, pos = self.targetValidator.validate(text, pos)
        if state == QValidator.Invalid: self.colorer.blink(DisplayColor.HighlightRed)
        return state, text, pos

    def fixup(self, text):
        return self.targetValidator.fixup(text)


class colored:  # TESTME
    """ Decorator """
    def __init__(self, colorerMethod: Callable, colorer: QWidget, colorsMapping: Dict[str, DisplayColor]):
        self.colorer = colorer
        self.colorerMethod: Callable = colorerMethod
        self.colorsMapping: Dict[str, DisplayColor] = colorsMapping

    def __call__(self, method: Callable):
        @wraps(method)
        def colorizedMethod(*args, **kwargs):
            result = method(*args, **kwargs)
            try: color = self.colorsMapping[result]
            except KeyError: pass
            else: self.colorerMethod(self.colorer, color)
            return result

        return colorizedMethod


class Colorer():
    """ ... TODO
        Should be initialized after validator is set.
            .patchValidator() should be called each time validator is changed
        Change widget color with this object, direct .palette maniputations will break everything
    """

    def __init__(self, widget: QWidget, base: QWidget = None):
        self.owner: QWidget = widget
        self.ownerBase: QWidget = base if base is not None else widget
        self.bgColorRole = QPalette.Button if isinstance(self.ownerBase, QPushButton) else QPalette.Base
        self.bgColor: QColor = self.ownerBase.palette().color(self.bgColorRole)
        self.savedBgColor: QColor = self.bgColor
        self.blinkHaloTimer: QTimer = self._createTimer_(BLINKING_DURATION//BLUR_RADIUS, self.unblinkHalo)
        self.blinkTimer: QTimer = self._createTimer_(FADE_TIME // FADE_STAGES, self.unblink)

        QTimer().singleShot(0, self.patchValidator)

    def _createTimer_(self, period: int, callback: Callable) -> QTimer:
        timer = QTimer(self.owner)
        timer.setInterval(period)
        timer.timeout.connect(callback)  # TODO: change function to proper one (does not exist yet)
        timer.savedWidgetColor: QColor = None
        timer.blinkingWidgetColor: QColor = None
        timer.blinkingStage: int = 0
        return timer

    @staticmethod
    def blendColor(base: QColor, overlay: QColor, stage: int):
        if not 0 <= stage <= FADE_STAGES:
            raise ValueError(f"Invalid stage: {stage}, expected [0..{FADE_STAGES}]")
        ratio = stage / FADE_STAGES
        red = base.red()*(1-ratio) + overlay.red()*ratio
        green = base.green()*(1-ratio) + overlay.green()*ratio
        blue = base.blue()*(1-ratio) + overlay.blue()*ratio
        return QColor(red, green, blue)

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor, str], preserve=True):
        """ Update `.owner` widget color component `role` with color `color` """
        if isinstance(color, DisplayColor): color = color.value
        palette = self.ownerBase.palette()
        palette.setColor(role, QColor(color))
        self.ownerBase.setPalette(palette)
        if preserve is True and role == self.bgColorRole:
            self.savedBgColor = palette.color(role)

    def blink(self, color: DisplayColor):
        self.blinkTimer.stage = FADE_STAGES
        self.blinkTimer.savedWidgetColor = self.savedBgColor
        print(self.blinkTimer.savedWidgetColor.name())
        self.blinkTimer.widgetBlinkColor = QColor(color.value)

        self.setColor(self.bgColorRole, color, preserve=False)
        self.blinkTimer.start()

    def unblink(self):
        timer = self.blinkTimer
        timer.stage -= 1
        if timer.stage <= 0:
            timer.stop()
            self.setColor(self.bgColorRole, timer.savedWidgetColor, preserve=False)
        else:
            self.setColor(self.bgColorRole, self.blendColor(
                    timer.savedWidgetColor, timer.widgetBlinkColor, timer.stage), preserve=False)

    def setHalo(self, color: Union[DisplayColor, QColor, str]):
        if isinstance(color, DisplayColor): color = color.value
        # TODO: ▼ convert this to Chain() statement
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0)
        effect.setBlurRadius(BLUR_RADIUS)
        effect.setColor(QColor(color))
        self.owner.setGraphicsEffect(effect)

    def blinkHalo(self, color: DisplayColor):
        self.setHalo(color)
        self.blinkHaloTimer.start()

    def unblinkHalo(self):
        effect = self.owner.graphicsEffect()
        if effect.blurRadius() <= 1:
            self.owner.setGraphicsEffect(None)
            self.blinkHaloTimer.stop()
        else:
            effect.setBlurRadius(effect.blurRadius() - 1)

    def patchValidator(self):
        validator = self.owner.validator()
        log.debug(f"Owner validator is {validator}")
        if validator is not None:
            self.owner.setValidator(BlinkingValidator(self))

    def setBaseColor(self, color: Union[DisplayColor, QColor, str]):
        return self.setColor(self.bgColorRole, color)

    def resetBaseColor(self):
        return self.setColor(self.bgColorRole, self.bgColor)

    blinked = partial(colored, setHalo)  # decorator
    colorized = partial(colored, setBaseColor)  # decorator
