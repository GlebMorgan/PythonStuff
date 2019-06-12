from __future__ import annotations

from enum import Enum
from typing import NamedTuple, Union, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QWidget


class Colorer():

    """ Colorizes text on edits in ComboBoxes and EditBoxes@needsTesting based on .colorize() method
        By default, color is based on validator state
            (target_class.validator().state:QValidator.State attr should exist)
        Alternative .colorize() behaviour could be provided by subclassing
            or by providing colorizing function in Colorer() constructor.

        API:

        Colorer(target:QWidget)
        Colorer(target:QWidget, colorize:Callable)
            Initialize Colorer with target widget [ + colorize override function, optionally]
            QComboBox and QLineEdit (not tested!) is supported currently
            If colorize() function is not provided (whether by subclassing or as constructor parameter)
                target widget should have custom .validator() assigned with .state:QValidator.State attr
                representing current validation state
            Else, colorize() signature should conform to one of the following:
                colorize_function(colorer_object) -> ColorSetting()
                colorize_method(self, colorer_object) -> .ColorSetting()

        .updateColor()
            Update text color as defined by .colorize()
            Triggered automatically on text edits, could be called manually when necessary

        .setColor(role: QPalette.ColorRole, color: .DisplayColor)
        .setColor(role: QPalette.ColorRole, color: QColor)
        .setColor(ColorSetting)
            Update target widget component 'role' (text, selection, background, etc.) with specified color 'color'

        .blink(color: .DisplayColor):
            Blink background with specified color for 100ms
            Do not triggered automatically, intended to be called manually when necessary
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
        QRegExpValidator.Invalid: DisplayColor.Red,
        QRegExpValidator.Intermediate: DisplayColor.Blue,
        QRegExpValidator.Acceptable: DisplayColor.Green,
        None: DisplayColor.Black
    }

    class ColorSetting(NamedTuple):
        colorRole: QPalette.ColorRole
        color: Colorer.DisplayColor

    def __init__(self, target:QWidget, colorize:Callable = None):
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
        self.setColor(*self.colorize())

    def colorize(self) -> ColorSetting:
        if self.target.currentText() == self.target.activeValue:
            return self.ColorSetting(QPalette.Text, Colorer.DisplayColor.Black)
        return self.ColorSetting(QPalette.Text, self.ValidatorColorsMapping[self.target.validator().state])

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor]):
        palette = self.target.palette()
        if isinstance(color, self.DisplayColor): color = color.value
        palette.setColor(role, QColor(color))
        self.target.setPalette(palette)

    def blink(self, color: DisplayColor):
        self.savedColor = self.target.palette().color(QPalette.Text)
        if not self.blinkingTimer:
            print(f'▲ ({color.name})')
            self.blinkingTimer = QTimer(self.target)
            self.blinkingTimer.color = color
            self.blinkingTimer.setInterval(80)
            self.blinkingTimer.setSingleShot(True)
            self.blinkingTimer.timeout.connect(lambda: self.unblink(self.savedColor))
            self.blinkingTimer.start()
        elif self.blinkingTimer.color != color:
            print(f'↺ ({color.name})')
            self.blinkingTimer.color = color
            self.blinkingTimer.start()
        else: return
        print('☼')
        self.blinkingTimer.color = color
        self.setColor(QPalette.Text, self.DisplayColor.Normal)
        self.setColor(QPalette.Base, color)

    def unblink(self, oldColor):
        print(f'○ ({oldColor.name()})')
        self.setColor(QPalette.Text, oldColor)
        self.setColor(QPalette.Base, self.DisplayColor.BackgroundNormal)
        QTimer().singleShot(20, self.test_clearBlinkingTimer)

    def test_clearBlinkingTimer(self):
        print("▼")
        if self.blinkingTimer is None:
            raise AssertionError("Colorer.blinkingTimer is set to None when it is already None")
        setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None
