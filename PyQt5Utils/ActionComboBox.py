from __future__ import annotations
from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QComboBox
from enum import Enum

from PyQt5Utils.Colorer import Colorer
from utils import Dummy


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
        self.view().setSizeAdjustPolicy(self.view().AdjustToContents)

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

    def setColorer(self, colorer: Colorer =True):
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
        # if self.currentIndex() == -1:  # CONSIDER: if this needed?
        #     self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)

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
        if self.view().hasFocus():
            self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)
        self.lastInput = self.currentText()
        if self.persistInvalidInput is self.PersistInputMode.Persist:
            if self.currentText() == self.activeValue:
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
