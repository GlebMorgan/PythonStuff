from __future__ import annotations as annotations_feature

from enum import Enum
from functools import wraps, partial
from typing import Union, Dict, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette, QValidator
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect, QPushButton
from Utils import Logger


log = Logger("Colorer")


FADE_TIME_HALO = 120  # ms
BLUR_RADIUS = 10      # px
FADE_TIME = 200       # ms
STAGE_DURATION = 10   # ms


class DisplayColor(Enum):

    White = QColor('white')
    Black = QColor('black')
    Red = QColor('red')
    Green = QColor('green')
    Blue = QColor('mediumblue')
    Orange = QColor('darkorange')
    Violet = QColor('blueviolet')
    Yellow = QColor('yellow')
    Cyan = QColor('cyan')

    LightGreen = Green.lighter()
    LightBlue = Blue.lighter()
    LightRed = Red.lighter()


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
    """ Base decorator for blinking widgets based on decorated function output (dev) """
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
    """ Widget background coloring and blinking pseudo-animations module
        Usage:
            `.blink(color)` - blink with background.
            `.blinkHalo(color)` - blink with glowing borders (color display is quite poor)
            `.setBaseColor(color)` - set widget background color (use `DisplayColor.Light<colorname>` colors)
            `.resetBaseColor()` - reset background color with one the widget had when class was instantiated
            `.color([role=background])` - current static color getter (changes caused by blinking are not reflected)
        Limitations:
            • Class should be initialized after validator is set.
                `.patchValidator()` should be called each time validator is changed
            • Widget color must be changed with `.setColor()` and .setBaseColor()`
                Direct `.palette` manipulations WILL BREAK EVERYTHING
    """

    def __init__(self, widget: QWidget, base: QWidget = None, duration: int = FADE_TIME):
        self.owner: QWidget = widget
        self.ownerBase: QWidget = base if base is not None else widget
        self.bgColorRole = QPalette.Button if isinstance(self.ownerBase, QPushButton) else QPalette.Base
        self.bgColor: QColor = self.ownerBase.palette().color(self.bgColorRole)
        self.savedBgColor: QColor = self.bgColor
        self.duration = duration
        self.FADE_STAGES = self.duration // STAGE_DURATION
        self.blinkHaloTimer: QTimer = self._createTimer_(FADE_TIME_HALO // BLUR_RADIUS, self.unblinkHalo)
        self.blinkTimer: QTimer = self._createTimer_(STAGE_DURATION, self.unblink)
        self.blinking: bool = False  # blinking state
        self.blinkingHalo = False  # halo blinking state

        QTimer().singleShot(0, self.patchValidator)

    def _createTimer_(self, period: int, callback: Callable) -> QTimer:
        timer = QTimer(self.owner)
        timer.setInterval(period)
        timer.timeout.connect(callback)
        timer.widgetBlinkColor: QColor = None
        timer.stage: int = 0
        return timer

    def _blendColor_(self, base: QColor, overlay: QColor, stage: int):
        assert 0 <= stage <= self.FADE_STAGES, f"Invalid stage: {stage}, expected [0..{self.FADE_STAGES}]"
        ratio = stage / self.FADE_STAGES
        red = base.red()*(1-ratio) + overlay.red()*ratio
        green = base.green()*(1-ratio) + overlay.green()*ratio
        blue = base.blue()*(1-ratio) + overlay.blue()*ratio
        return QColor(red, green, blue)

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor, str], preserve=True):
        """ Update `.owner` widget color component `role` with color `color`
            Background color changes are captured, unless explicitly specified not to `preserve` them
        """
        if isinstance(color, DisplayColor): color = color.value
        palette = self.ownerBase.palette()
        palette.setColor(role, QColor(color))
        self.ownerBase.setPalette(palette)
        if preserve is True and role == self.bgColorRole:
            self.savedBgColor = palette.color(role)

    def blink(self, color: DisplayColor):
        """ Blink with background with smooth fade-out. Does not change `.color()` output.
            `FADE_TIME` and `FADE_STAGES` global settings adjust quality and timing respectively
        """
        self.blinkTimer.stage = self.FADE_STAGES
        self.blinkTimer.widgetBlinkColor = QColor(color.value)
        self.setColor(self.bgColorRole, color, preserve=False)
        self.blinkTimer.start()
        self.blinking = True

    def unblink(self):
        """ Decrease blinking color intensity one step (out of `FADE_STAGES`) and set timer for the next stage
            If stages are over (`timer.stage == 0`), set owner widget background color
                to its current idle state color (`.savedBgColor` / same as what `.color()` returns)
        """
        timer = self.blinkTimer
        timer.stage -= 1
        if timer.stage <= 0:
            timer.stop()
            self.setColor(self.bgColorRole, self.savedBgColor, preserve=False)
            self.blinking = False
        else:
            self.setColor(self.bgColorRole, self._blendColor_(
                    self.savedBgColor, timer.widgetBlinkColor, timer.stage), preserve=False)

    def setHalo(self, color: Union[DisplayColor, QColor, str]):
        if isinstance(color, DisplayColor): color = color.value
        # TODO: ▼ convert this to Chain() statement
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0)
        effect.setBlurRadius(BLUR_RADIUS)
        effect.setColor(QColor(color))
        self.owner.setGraphicsEffect(effect)

    def blinkHalo(self, color: DisplayColor):
        """ Blink with glowing borders with smooth fade-out.
            `FADE_TIME_HALO` and `BLUR_RADIUS` global settings adjust timing and halo size respectively
            NOTE: Early dev-state function, use .blink() for better look&feel
        """
        self.setHalo(color)
        self.blinkHaloTimer.start()
        self.blinkingHalo = True

    def unblinkHalo(self):
        """ Set shadow graphics effect blur radius one step smaller and set timer for the next dimming step
            If `.blurRadius ≤ 1`, remove effect from owner widget.
        """
        effect = self.owner.graphicsEffect()
        if effect.blurRadius() <= 1:
            self.owner.setGraphicsEffect(None)
            self.blinkHaloTimer.stop()
            self.blinkingHalo = False
        else:
            effect.setBlurRadius(effect.blurRadius() - 1)

    def patchValidator(self):
        """ Modify validator to blink on certain validation state changes (defined by `BlinkingValidator` logic)
            Return boolean value denoting whether validator has been patched successfully
        """
        try: validator = self.owner.validator()
        except AttributeError: return False
        if validator is not None:
            self.owner.setValidator(BlinkingValidator(self))
            return True
        else: return False

    def setBaseColor(self, color: Union[DisplayColor, QColor, str, None]):
        """ If `color` is `None`, color is reset to stored background color (equivalent to `.resetBaseColor()`)"""
        if color is None: color = self.bgColor
        return self.setColor(self.bgColorRole, color)

    def resetBaseColor(self):
        return self.setColor(self.bgColorRole, self.bgColor)

    def color(self, role: QPalette.ColorRole = None):
        if role == self.bgColorRole: return self.savedBgColor
        if role is None: role = self.bgColorRole
        return self.owner.palette().color(role)

    blinked = partial(colored, setHalo)  # decorator  # TESTME
    colorized = partial(colored, setBaseColor)  # decorator  # TESTME
