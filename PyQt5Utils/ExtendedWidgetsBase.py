from __future__ import annotations

from enum import Enum
from typing import Union, Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QComboBox, QLineEdit, QAction
from PyQt5.QtWidgets import QWidget
from Utils import Logger, Dummy

from . import Colorer

log = Logger("ExtendedWidgetsBase")


class ActionWidget(QWidget):

    # TODO: Add check in __init__():
    #       if not isinstance(self, QWidget): raise NIE("needs to be used in conjunction with some QWidget)

    updateRequired = pyqtSignal()

    def __init__(self: QWidget, *args,
                 parent=None, default='', resize=False, show=False):
        super().__init__(parent=parent)
        self.activeValue = default
        self.targetAction: QAction
        self.actionSignal: Callable     # NOTE: needs to be overridden in successors
        self.actionSlot: Callable       # NOTE: needs to be overridden in successors

        if resize: self.resize(self.sizeHint())
        if show: self.show()

    def updateFromAction(self):
        # TODO: not to trigger this on targetAction.setData()

        expressionIterator = ((fun, arg) for fun, arg in (
            ('setText', self.targetAction.text()),
            ('setStatusTip', self.targetAction.statusTip()),
            ('setToolTip', self.targetAction.toolTip()),
            ('setIcon', self.targetAction.icon()),
            ('setEnabled', self.targetAction.isEnabled()),
            ('setCheckable', self.targetAction.isCheckable()),
            ('setChecked', self.targetAction.isChecked()),
        ))

        for fun, arg in expressionIterator:
            try: getattr(self, fun)(arg)
            except AttributeError: pass

    def setAction(self, action):
        # TODO: accept kwargs describing action and create it here, set as self.targetAction and return it
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.actionSignal.connect(self.actionSlot)
        self.updateFromAction()


class ColoredWidget(ActionWidget):

    # TODO: Add check in __init__():
    #       if not isinstance(self, (QWidget, ActionWidget, ColoredWidget):
    #           raise NotImplementedError("needs to be used in conjunction with some QWidget")

    # Should have .validator().state attr

    class InputMode(Enum):
        Persist = 1  # Always shows last input
        Reset = 2    # Resets input to current active value if invalid
        Retain = 3   # Restores last input when returned to editing

    def __init__(self: Union[QWidget, ActionWidget, ColoredWidget], *args,
                 parent=None, persistInput=InputMode.Retain, **kwargs):
        super().__init__(parent=parent)
        self.persistInvalidInput = persistInput
        self.lastInput = None
        self.colorer = Dummy()

        if isinstance(self, QComboBox):
            self.lineEditSubwidget = self.lineEdit
            self.setTextContents = self.setCurrentText
            self.textContents = self.currentText
        elif isinstance(self, QLineEdit):
            self.lineEditSubwidget = lambda: self
            self.setTextContents = self.setText
            self.textContents = self.text
        else:
            raise NotImplementedError(f"{self.__class__} is not supported for inheritance")

    def setAction(self, *args, **kwargs):
        # FIXME: trigger action sees activeValue updated too early
        super().setAction(*args, **kwargs)
        self.actionSignal.connect(self.setActiveValue)

    def setColorer(self, colorer: Union[Colorer, bool] = True):
        if colorer is True: self.colorer = Colorer(self)
        elif colorer: self.colorer = colorer

    def setValidator(self, validator):
        validator.triggered.connect(lambda state:
                self.colorer.blink(
                        self.colorer.DisplayColor.Red) if self.validator().state == self.validator().Invalid else None)

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        if self.persistInvalidInput is self.InputMode.Retain:
            if self.lastInput:
                self.setTextContents(self.lastInput)
            if self.lastInput != self.activeValue:
                QTimer().singleShot(0, self.lineEditSubwidget().deselect)
        self.colorer.updateColor()

    def focusOutEvent(self, QFocusEvent):
        super().focusOutEvent(QFocusEvent)
        self.lastInput = self.textContents()
        if self.persistInvalidInput is self.InputMode.Persist:
            if self.textContents() == self.activeValue:
                self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)
        else:
            self.setTextContents(self.activeValue)
            self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)

    def ack(self, ack=True):
        # TESTME: moved these 2 lines to triggerAction(). Is anything broken?
        self.setActiveValue()
        if ack is True:
            QTimer().singleShot(0, lambda: self.colorer.blink(self.colorer.DisplayColor.Green))
            self.lastInput = self.textContents()
        elif ack is False:
            self.colorer.blink(self.colorer.DisplayColor.Red)

    def setActiveValue(self):
        self.activeValue = self.textContents()
        self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)



