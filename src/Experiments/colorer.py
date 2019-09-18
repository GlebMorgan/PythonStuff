from __future__ import annotations as annotations_feature
from enum import Enum
from functools import wraps, partial, partialmethod
from typing import Union, Dict, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette, QValidator
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from Utils import Logger

log = Logger("Colorer")


# TODO: choose colors for blinking

# TODO: Replace TEMPvar with statement containing BLINKING_DURATION and BLUR_RADIUS (compute delay out of these two)


BACKGROUND_COLOR = 'white'
BLINKING_DURATION = 120  # ms
BLUR_RADIUS = 15
TEMP = 10  # TEMP

class DisplayColor(Enum):
    Normal = 'black'
    Red = 'red'
    Green = 'lime'  # TEMP 'forestgreen'
    Blue = 'mediumblue'
    Black = 'black'
    White = 'white'
    Background = BACKGROUND_COLOR


class BlinkingValidator(QValidator):
    def __init__(self, owner):
        super().__init__()
        self.colorer = owner
        self.targetValidator = self.colorer.owner.validator()

    def validate(self, text, pos):
        state, text, pos = self.targetValidator.validate(text, pos)
        if state == QValidator.Invalid: self.colorer.blink(DisplayColor.Red)
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
    """

    def __init__(self, widget: QWidget, base: QWidget = None):
        self.owner: QWidget = widget
        self.ownerBase: QWidget = base if base is not None else widget

        timer = QTimer(self.owner)
        timer.setInterval(TEMP)
        timer.timeout.connect(self.unblink)
        self.blinkingTimer: QTimer = timer

        QTimer().singleShot(0, self.patchValidator)

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor, str]):
        """ Update 'owner' widget color component 'role' (text, selection, background, etc.)
                with color 'color' """
        if isinstance(color, DisplayColor): color = color.value
        palette = self.ownerBase.palette()
        palette.setColor(role, QColor(color))
        self.ownerBase.setPalette(palette)

    def glow(self, color: Union[DisplayColor, QColor, str]):
        if isinstance(color, DisplayColor): color = color.value
        # TODO: ▼ convert this to Chain() statement
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0)
        effect.setBlurRadius(BLUR_RADIUS)
        effect.setColor(QColor(color))
        self.owner.setGraphicsEffect(effect)

    def removeGlow(self):
        log.debug(f"○")
        self.owner.setGraphicsEffect(None)
        QTimer().singleShot(BLINKING_DURATION // 4,
                            lambda: setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None)

    def blink_old(self, color: DisplayColor):
        """ Blink background with specified color for BLINKING_DURATION ms """

        if not self.blinkingTimer:
            log.debug(f'☼ ({color.name})')
            self.blinkingTimer = QTimer(self.owner)
            self.blinkingTimer.setInterval(BLINKING_DURATION // 4 * 3)
            self.blinkingTimer.setSingleShot(True)
            self.blinkingTimer.timeout.connect(self.removeGlow)
        elif self.blinkingTimer.color != color:
            log.debug(f'↺ ({color.name})')
        else:
            log.debug('↓')
            return
        self.blinkingTimer.color: DisplayColor = color
        self.blinkingTimer.start()
        self.glow(color)

    def blink(self, color: DisplayColor):
        self.glow(color)
        self.blinkingTimer.start()

    def unblink(self):
        effect = self.owner.graphicsEffect()
        if effect.blurRadius() <= 1:
            self.owner.setGraphicsEffect(None)
            self.blinkingTimer.stop()
        else:
            effect.setBlurRadius(effect.blurRadius() - 1)

    def patchValidator(self):
        validator = self.owner.validator()
        log.debug(f"Owner validator is {validator}")
        if validator is not None:
            self.owner.setValidator(BlinkingValidator(self))

    setBaseColor = partialmethod(setColor, QPalette.Base)

    blinked = partial(colored, blink)  # decorator
    colorized = partial(colored, setBaseColor)  # decorator
