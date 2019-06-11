from __future__ import annotations
from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QValidator, QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QAction, QComboBox, QWidget
from enum import Enum
from typing import Union, Sequence, NamedTuple

from context_proxy import Context
from utils import Dummy


class NotifyingValidator(QRegExpValidator):

    def __init__(self, *args):
        self.state = None
        super().__init__(*args)

    triggered = pyqtSignal(QRegExpValidator.State)
    validationStateChanged = pyqtSignal(QRegExpValidator.State)


class Colorer():

    """ Supposed to be subclassed and override colorize() method
        Default behaviour - colorize based on target.validator().state and target.activeValue attrs """

    # changeTextColor() on:
    #   validator.triggered
    #   focusInEvent()
    #   focusOutEvent() when coloring is removed
    #   ack()

    # Needs to change on:
    #   setCurrentText()                 -> needs testing
    #   validator().triggered            -> ???
    #   focusInEvent(), focusOutEvent()  -> call manually
    #   ack()                            -> call manually

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

    def __init__(self, target:QWidget):
        self.target = target
        if not isinstance(self.target, QWidget):
            raise TypeError(f"'target' parameter type is incorrect: expected 'QWidget', got {type(self.target)}")
        if hasattr(self.target, 'currentTextChanged'):
            self.target.currentTextChanged.connect(self.updateColor)
        elif hasattr(self.target, 'textChanged'):
            self.target.textChanged.connect(self.updateColor)
        self.blinkingTimer = None

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
        # TESTME - crashes on continuous blinkings
        if not self.blinkingTimer:
            print(f'▲ ({color})')
            self.blinkingTimer = QTimer(self.target)
            self.blinkingTimer.color = color
            self.blinkingTimer.setInterval(80)
            self.blinkingTimer.setSingleShot(True)
            self.blinkingTimer.timeout.connect(lambda: self.unblink(currColor))
            self.blinkingTimer.start()
        elif self.blinkingTimer.color != color:
            print(f'↺ ({color})')
            self.blinkingTimer.color = color
            self.blinkingTimer.timeout.disconnect()
            self.blinkingTimer.timeout.connect(lambda: self.unblink(currColor))
            self.blinkingTimer.start()
        else: return
        print('☼')
        currColor = self.target.palette().color(QPalette.Text)
        self.setColor(QPalette.Text, self.DisplayColor.Normal)
        self.setColor(QPalette.Base, color)

    def unblink(self, oldColor):
        print('○')
        # print("TIMER: unblink called")
        # if self.blinkingTimer is None: return
        self.setColor(QPalette.Text, oldColor)
        self.setColor(QPalette.Base, self.DisplayColor.BackgroundNormal)
        QTimer().singleShot(20, self.test_clearBlinkingTimer)

    def test_clearBlinkingTimer(self):
        print("▼")
        if self.blinkingTimer is None: print("AAAAAAAAAAAAAAAAAAAAAAAAAAA, error!")
        setattr(self, 'blinkingTimer', None) if self.blinkingTimer and not self.blinkingTimer.isActive() else None


class ActionComboBox(QComboBox):

    updateRequired = pyqtSignal()

    def __init__(self, *args, default='', syncActionText=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.syncText = syncActionText
        self.activeValue = default
        self.targetAction = None

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        self.setCurrentText(default)

    def setAction(self, action):
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.currentIndexChanged.connect(self.triggerActionWithData)
        self.updateFromAction()
        # QTimer().singleShot(0, self.triggerActionWithData)

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerActionWithData(self):
        print(f"Action '{self.targetAction.text()}' triggered!")
        if self.view().hasFocus():
            return self.restoreCurrentIndex()
        # CONSIDER: ▼ will this still be needed in the end? :)
        if self.currentIndex() == -1: return
        if self.currentText() != self.activeValue:
            self.targetAction.setData(self.currentText())
            self.targetAction.trigger()
        print(f"New state: {self.currentText()}, sender: {self.sender().__class__.__name__}")

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        print('Focus!')
        self.updateRequired.emit()
        QTimer().singleShot(0, self.lineEdit().selectAll)

    def focusOutEvent(self, QFocusEvent):
        if not self.view().hasFocus():
            super().focusOutEvent(QFocusEvent)

    def restoreCurrentIndex(self):
        self.blockSignals(True)
        self.setCurrentIndex(self.findText(self.activeValue))
        self.blockSignals(False)

class ValidatingComboBox(ActionComboBox):

    class PersistInputMode(Enum):
        Persist = 1
        Clear = 2
        Retain = 3

    def __init__(self, persistInput=PersistInputMode.Retain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistInvalidInput = persistInput
        self.lastInput = None
        self.colorer = Dummy()

    def setColorer(self, colorer:Colorer=True):
        if colorer is True: self.colorer = Colorer(self)
        elif colorer: self.colorer = colorer
        else: self.colorer = Dummy()

    def setValidator(self, validator):
        super().setValidator(validator)
        validator.triggered.connect(lambda state:
                self.colorer.blink(self.colorer.DisplayColor.Red) if state == self.validator().Invalid else None
        )

    def triggerActionWithData(self):
        super().triggerActionWithData()
        if self.currentIndex() == -1:  # CONSIDER: if this needed?
            self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        if self.persistInvalidInput is self.PersistInputMode.Retain:
            if self.lastInput:
                self.setCurrentText(self.lastInput)
            if self.lastInput != self.activeValue:
                QTimer().singleShot(0, self.lineEdit().deselect)
            print(f"LastInput: {self.lastInput}, activeValue: {self.activeValue}, currentText: {self.currentText()}")
        self.colorer.updateColor()

    def focusOutEvent(self, QFocusEvent):
        super().focusOutEvent(QFocusEvent)
        self.lastInput = self.currentText()
        if self.persistInvalidInput is self.PersistInputMode.Persist:
            if self.palette().color(QPalette.Text) == QColor(self.colorer.DisplayColor.Green.value): # FIXME: rewrite using self.activeValue
                self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)
        else:
            self.setCurrentText(self.activeValue)
            self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)

    # TODO: remove this test function when finished class
    def testColorizeRandomly(self):
        from random import choice
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))
        self.setPalette(palette)
        print(self.lineEdit().palette().color(QPalette.WindowText).name())

    def ack(self, ack=True):
        self.activeValue = self.currentText()
        self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)
        if ack is True:
            self.colorer.blink(self.colorer.DisplayColor.Green)
            self.lastInput = self.currentText()
        elif ack is False:
            self.colorer.blink(self.colorer.DisplayColor.Red)
