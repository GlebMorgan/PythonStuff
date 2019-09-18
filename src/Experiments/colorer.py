from __future__ import annotations as annotations_feature
from enum import Enum
from typing import Union

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette, QValidator
from PyQt5.QtWidgets import QWidget, QGraphicsDropShadowEffect
from Utils import Logger

log = Logger("Colorer")

BACKGROUND_COLOR = 'white'
BLINKING_DURATION = 100  # ms


class DisplayColor(Enum):
    Normal = 'black'
    Red = 'red'
    Green = 'forestgreen'
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
        if state == QValidator.Invalid: self.colorer.glow(DisplayColor.Red)

    def fixup(self, text):
        return self.targetValidator.fixup()


class Colorer():
    def __init__(self, owner: QWidget):
        self.owner: QWidget = owner
        self.blinkingTimer: QTimer = None

    def setColor(self, role: QPalette.ColorRole, color: Union[QColor, str]):
        """ Update 'owner' widget color component 'role' (text, selection, background, etc.)
                with color 'color' """
        palette = self.owner.palette()
        palette.setColor(role, QColor(color))
        self.owner.setPalette(palette)

    def glow(self, color):
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0)
        effect.setBlurRadius(20)
        effect.setColor(color)
        self.owner.setGraphicsEffect(effect)

    def removeGlow(self):
        log.debug(f"○")
        self.owner.setGraphicsEffect(None)
        QTimer().singleShot(BLINKING_DURATION // 4,
                            lambda: setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None)

    def blink(self, color: DisplayColor):
        """ Blink background with specified color for BLINKING_DURATION ms """

        if not self.blinkingTimer:
            log.debug(f'▲ ({color.name})')
            self.blinkingTimer = QTimer(self.owner)
            self.blinkingTimer.setInterval(BLINKING_DURATION // 4 * 3)
            self.blinkingTimer.setSingleShot(True)
            self.blinkingTimer.timeout.connect(lambda: self.removeGlow)
            self.blinkingTimer.start()
        elif self.blinkingTimer.color != color:
            log.debug(f'↺ ({color.name})')
            self.blinkingTimer.start()
        else: return
        log.debug('☼')
        self.blinkingTimer.color = color
        self.glow(color.name)

    def _unblink_(self, oldColor: Union[DisplayColor, QColor]):
        # log.debug(f"○ ({oldColor.name() if hasattr(oldColor.name, '__call__') else oldColor.name})")
        self.setColor(QPalette.Text, oldColor)
        self.setColor(QPalette.Base, DisplayColor.BackgroundNormal)
        QTimer().singleShot(BLINKING_DURATION // 4,
                            lambda: setattr(self, 'blinkingTimer', None) if not self.blinkingTimer.isActive() else None)

    def patchValidator(self):
        validator = self.owner.validator()
        log.debug(f"Owner validator is {validator}")
        if validator is not None:
            self.owner.setValidator(BlinkingValidator(validator))
