from PyQt5.QtCore import QStringListModel, QTimer
from PyQt5.QtGui import QValidator
from PyQt5.QtWidgets import QAction, QComboBox


class ActionComboBox(QComboBox):
    def __init__(self, *args, action: QAction = None, validator: QValidator = None,
                 syncText=False, resize=True, show=True):
        super().__init__(*args)
        self.syncText = syncText

        if action:
            action.changed.connect(self.updateFromAction)
            self.currentIndexChanged.connect(self.triggerActionWithData)
            self.targetAction = action
            self.updateFromAction()

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        if validator: self.setValidator(validator)

        if resize: self.resize(self.sizeHint())
        if show: self.show()

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerActionWithData(self):
        if self.validator(): self.validator().finish()
        self.targetAction.setData(self.currentIndex())
        self.targetAction.trigger()

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        if self.validator():
            self.validator().validate(self.currentText(), self.lineEdit().cursorPosition())
        QTimer().singleShot(0, self.lineEdit().selectAll)

    def focusOutEvent(self, QFocusEvent):
        super().focusOutEvent(QFocusEvent)
        if self.validator(): self.validator().finish()
