from __future__ import annotations
from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QValidator, QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QAction, QComboBox, QWidget
from enum import Enum
from typing import Union, Sequence, NamedTuple

from utils import Dummy


class NotifyingValidator(QRegExpValidator):

    def __init__(self, *args):
        self.state = None
        super().__init__(*args)

    # class DisplayColor(Enum):
    #     Red = 'red'
    #     Green = 'forestgreen'
    #     Blue = 'mediumblue'
    #     Black = 'black'

    # class ExState(Enum):
        # Invalid = 0       # Unacceptable by nature
        # Intermediate = 1  # Could become accepted value by further editing
        # Valid = 2         # Acceptable value
        # Acceptable = 2    # ['Valid' alias]
        # Unacceptable = 3  # Unacceptable in current circumstances
        # Inactive = 4      # Validation is not conducted currently
        # Undefined = 5     # Cannot determine state

    triggered = pyqtSignal(QRegExpValidator.State)
    validationStateChanged = pyqtSignal(QRegExpValidator.State)


class Colorer():

    """ Supposed to be subclassed and override colorize() method
        Default behaviour - colorize based on target.validator().state property """

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
        # if not isinstance(self.target.validator(), QValidator):
        #     raise TypeError(f"Target widget should have validator assigned")
        # if not hasattr(self.target.validator(), 'state') or not hasattr(self.target.validator(), 'triggered'):
        #     raise TypeError("Target widget validator should have 'state' parameter containing current validation state "
        #                     "and emit 'triggered' signal when validation is performed")
        # self.target.validator().triggered.connect(self.setColor(self.colorize()))
        if hasattr(self.target, 'currentTextChanged'):
            self.target.currentTextChanged.connect(self.updateColor)
        elif hasattr(self.target, 'textChanged'):
            self.target.textChanged.connect(self.updateColor)
        self.blinking = False

    def updateColor(self):
        self.setColor(*self.colorize())

    def colorize(self) -> ColorSetting:
        return self.ColorSetting(QPalette.Text, self.ValidatorColorsMapping[self.target.validator().state])

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor]):
        palette = self.target.palette()
        if isinstance(color, self.DisplayColor): color = color.value
        palette.setColor(role, QColor(color))
        self.target.setPalette(palette)

    def blink(self, color: DisplayColor):
        if self.blinking: return
        else: self.blinking = True
        currColor = self.target.palette().color(QPalette.Text)
        self.setColor(QPalette.Text, self.DisplayColor.Normal)
        self.setColor(QPalette.Base, color)
        QTimer().singleShot(100, lambda: self.unblink(currColor))

    def unblink(self, oldColor):
        self.setColor(QPalette.Text, oldColor)
        self.setColor(QPalette.Base, self.DisplayColor.BackgroundNormal)
        QTimer().singleShot(50, lambda: setattr(self, 'blinking', False))


# FIXME: on startup, color is not set to black

class ActionComboBox(QComboBox):

    updateRequired = pyqtSignal()

    def __init__(self, *args, syncActionText=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.activeValue = ''
        self.syncText = syncActionText
        self.targetAction = None
        self.colorer = Dummy()

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

    def setAction(self, action):
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.currentIndexChanged.connect(self.triggerAction)
        self.updateFromAction()
        QTimer().singleShot(0, self.triggerAction)

    def setColorer(self, colorer:Colorer):
        self.colorer = colorer

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerAction(self):
        if self.view().hasFocus():
            return self.restoreCurrentIndex()
        # CONSIDER: ▼ will this still be needed in the end? :)
        # if self.currentIndex() == -1: return
        self.updateRequired.emit()
        if self.currentText() != self.activeValue:
            self.activeValue = self.currentText()
            self.targetAction.trigger()
        print(f"New state: {self.currentText()}, sender: {self.sender().__class__.__name__}")

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
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

    # TODO: dont mess things up on drop-down

    # TODO: Move coloring routine to dedicated class

    class PersistInputMode(Enum):
        Persist = 1
        Clear = 2
        Retain = 3

    def __init__(self, persistInput=PersistInputMode.Retain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistInvalidInput = persistInput
        self.lastInput = None

    def setValidator(self, validator):
        super().setValidator(validator)
        validator.triggered.connect(
                lambda state: self.colorer.blink(self.colorer.DisplayColor.Red) if state == self.validator().Invalid else None
        )
        # validator.triggered.connect(
        #         lambda state: self.testColorizeRandomly(state)
        # )

    # TODO: get back triggerActionWithData!
    def triggerAction(self):
        # self.changeTextColor(None)
        # self.blink(self.colorer.DisplayColor.Green)
        # self.lastInput = self.currentText()
        super().triggerAction()

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
            if self.palette().color(QPalette.Text) == QColor(self.colorer.DisplayColor.Green.value):
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
        self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)
        if ack is True:
            self.colorer.blink(self.colorer.DisplayColor.Green)
            self.lastInput = self.currentText()
        elif ack is False:
            self.colorer.blink(self.colorer.DisplayColor.Red)
