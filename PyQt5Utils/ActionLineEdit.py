
from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QLineEdit
from enum import Enum

from PyQt5Utils.Colorer import Colorer
from logger import Logger
from utils import Dummy


log = Logger("ActionLineEdit")


class ActionLineEdit(QLineEdit):

    # TODO: docs and API method arguments/return_values type annotations

    updateRequired = pyqtSignal()

    def __init__(self, *args, default='', syncActionText=False):
        super().__init__(*args)
        self.syncText = syncActionText
        self.activeValue = default
        self.targetAction = None

        self.setText(default)

    def setAction(self, action):
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.editingFinished.connect(self.triggerActionWithData)
        self.updateFromAction()

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerActionWithData(self):
        log.debug(f"Action triggered! Text= {self.text()}")

    # TO BE CONTINUED ...
