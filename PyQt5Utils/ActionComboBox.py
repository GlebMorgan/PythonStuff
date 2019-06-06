from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QValidator, QRegExpValidator, QPalette, QColor
from PyQt5.QtWidgets import QAction, QComboBox
from enum import Enum
from typing import Union, Sequence

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


class ActionComboBox(QComboBox):

    updateRequired = pyqtSignal()

    def __init__(self, *args, syncActionText=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.activeValue = ''
        self.syncText = syncActionText
        self.targetAction = None

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

    def setAction(self, action):
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.currentIndexChanged.connect(self.triggerAction)
        self.updateFromAction()
        QTimer().singleShot(0, self.triggerAction)

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

    class DisplayColor(Enum):
        Normal = 'black'
        Red = 'red'
        Green = 'forestgreen'
        Blue = 'mediumblue'
        Black = 'black'
        BackgroundNormal = 'white'
        BackgroundRed = 'red'

    class PersistInputMode(Enum):
        Persist = 1
        Clear = 2
        Retain = 3

    ValidatorColorsMapping = {
        QRegExpValidator.Invalid: DisplayColor.Red,
        QRegExpValidator.Intermediate: DisplayColor.Blue,
        QRegExpValidator.Acceptable: DisplayColor.Green,
        None: DisplayColor.Black
    }

    def __init__(self, persistInput=PersistInputMode.Retain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistInvalidInput = persistInput
        self.lastInput = None

    def setValidator(self, validator):
        super().setValidator(validator)
        validator.triggered.connect(
                lambda state: self.changeTextColor(state)
        )
        validator.triggered.connect(
                lambda state: self.blink(self.DisplayColor.Red) if state == self.validator().Invalid else None
        )
        # validator.triggered.connect(
        #         lambda state: self.testAfterValidate(state)
        # )

    def triggerAction(self):
        # self.changeTextColor(None)
        # self.blink(self.DisplayColor.Green)
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
        self.changeTextColor(self.validator().state)

    def focusOutEvent(self, QFocusEvent):
        super().focusOutEvent(QFocusEvent)
        self.lastInput = self.currentText()
        if self.persistInvalidInput is self.PersistInputMode.Persist:
            if self.palette().color(QPalette.Text) == QColor(self.DisplayColor.Green.value):
                self.setColor(QPalette.Text, self.DisplayColor.Black)
        else:
            self.setCurrentText(self.activeValue)
            self.setColor(QPalette.Text, self.DisplayColor.Black)

    def setColor(self, role: QPalette.ColorRole, color: Union[DisplayColor, QColor]):
        palette = self.palette()
        if isinstance(color, self.DisplayColor): color = color.value
        palette.setColor(role, QColor(color))
        self.setPalette(palette)

    def changeTextColor(self, state):
        # FIXME: color should reflect state of actual text in textInput, not validation state of last keypress
        if state == self.validator().Acceptable:
            text = self.lineEdit().text()
            items = self.model().stringList()
            if text not in items:
                if any(item.startswith(text) for item in items):
                    state = self.validator().Intermediate
                else:
                    state = self.validator().Invalid
        self.setColor(QPalette.Text, self.ValidatorColorsMapping[state])

    def blink(self, color: DisplayColor):
        if self.palette().color(QPalette.Base) == QColor(color.value): return
        currColor = self.palette().color(QPalette.Text)
        self.setColor(QPalette.Text, self.DisplayColor.Normal)
        self.setColor(QPalette.Base, color)
        QTimer().singleShot(100, lambda: self.setColor(QPalette.Text, currColor))
        QTimer().singleShot(100, lambda: self.setColor(QPalette.Base, self.DisplayColor.BackgroundNormal))

    def testAfterValidate(self, state):
        from random import choice
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))
        self.setPalette(palette)
        print(self.lineEdit().palette().color(QPalette.WindowText).name())

    def ack(self, ack=True):
        self.changeTextColor(None)
        if ack is True:
            self.blink(self.DisplayColor.Green)
            self.lastInput = self.currentText()
        elif ack is False:
            self.blink(self.DisplayColor.Red)