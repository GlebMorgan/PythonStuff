from __future__ import annotations

from enum import Enum
from typing import NamedTuple, Union, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QWidget
from ..Utils import Logger

log = Logger("Colorer")


class Colorer():
    # TESTME: Use case with LineEdit

    """ Colorizes text on edits in ComboBoxes and LineEdits@needsTesting based on .colorize() method
        By default, color is based on validator state
            (target_class.validator().state: QValidator.State attr should exist)
            and is updated on text edits, though could be called whenever necessary
        Customized .colorize() behaviour could be provided by subclassing
            or by providing colorizing function in Colorer() constructor.
    """

    class DisplayColor(Enum):
        Normal = 'black'
        Red = 'red'
        Green = 'forestgreen'
        Blue = 'mediumblue'
        Black = 'black'
        BackgroundNormal = 'white'
        BackgroundRed = 'red'

    ValidatorColorsMapping = {
        QRegExpValidator.Invalid:      DisplayColor.Red,
        QRegExpValidator.Intermediate: DisplayColor.Blue,
        QRegExpValidator.Acceptable:   DisplayColor.Green,
        None:                          DisplayColor.Black
    }

    class ColorSetting(NamedTuple):
        colorRole: QPalette.ColorRole
        color: Colorer.DisplayColor

    def __init__(self, target: QWidget, colorize: Callable[[Colorer], ColorSetting] = None):
        """ Initialize Colorer with target widget [ + 'colorize' override function, optionally]
            QComboBox and QLineEdit widgets are supported currently
            If colorize() function is not provided (whether by subclassing or as constructor parameter)
                target widget should have custom .validator() with .state: QValidator.State attr
                representing current validation state
        """
        self.target = target
        if hasattr(self.target, 'currentTextChanged'):
            self.target.currentTextChanged.connect(self.updateColor)
        elif hasattr(self.target, 'textChanged'):
            self.target.textChanged.connect(self.updateColor)

        if colorize: self.colorize = lambda: colorize(self)
        elif not (hasattr(target, 'validator') and
                  hasattr(target.validator, '__call__') and
                  target.validator() is not None):
            raise ValueError(f"Target widget should have a validator assigned in order to let default colorizer work")

        self.blinkingTimer = None
        self.savedColor = None

    def updateColor(self):
        """ Update text color as defined by .colorize()
            Triggered automatically on text edits, could be called manually when necessary
        """
        self.setColor(*self.colorize())

    def colorize(self) -> ColorSetting:
        """ Default implementation, is based on .target.validator().state :QValidator.State attr.
            Intended to be overridden for providing alternative behaviour
        """
        if self.target.currentText() == self.target.activeValue:
            return self.ColorSetting(QPalette.Text, Colorer.DisplayColor.Black)
        return self.ColorSetting(QPalette.Text, self.ValidatorColorsMapping[self.target.validator().state])

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor]):
        """ Update target widget component 'role' (text, selection, background, etc.)
                with specified color 'color'. Use as .setColor(*.ColorSetting(role, color))
        """
        palette = self.target.palette()
        if isinstance(color, self.DisplayColor): color = color.value
        palette.setColor(role, QColor(color))
        self.target.setPalette(palette)

    def blink(self, color: DisplayColor):
        """ Blink background with specified color for 100ms
            Is not triggered automatically, intended to be called manually when necessary
        """
        # FIXME: trouble with changing color while blinking!
        self.savedColor = self.target.palette().color(QPalette.Text)
        if not self.blinkingTimer:
            # log.debug(f'▲ ({color.name})')
            self.blinkingTimer = QTimer(self.target)
            self.blinkingTimer.color = color
            self.blinkingTimer.setInterval(80)
            self.blinkingTimer.setSingleShot(True)
            self.blinkingTimer.timeout.connect(lambda: self._unblink_(self.savedColor))
            self.blinkingTimer.start()
        elif self.blinkingTimer.color != color:
            # log.debug(f'↺ ({color.name})')
            self.blinkingTimer.color = color
            self.blinkingTimer.start()
        else: return
        # log.debug('☼')
        self.blinkingTimer.color = color
        self.setColor(QPalette.Text, self.DisplayColor.Normal)
        self.setColor(QPalette.Base, color)

    def _unblink_(self, oldColor: Union[DisplayColor, QColor]):
        # log.debug(f"○ ({oldColor.name() if hasattr(oldColor.name, '__call__') else oldColor.name})")
        self.setColor(QPalette.Text, oldColor)
        self.setColor(QPalette.Base, self.DisplayColor.BackgroundNormal)
        QTimer().singleShot(20, lambda:
                setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None)

    def _test_clearBlinkingTimer_(self):
        # log.debug('▼')
        setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None
