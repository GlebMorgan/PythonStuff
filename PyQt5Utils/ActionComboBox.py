from PyQt5.QtCore import QStringListModel, QTimer
from PyQt5.QtGui import QValidator
from PyQt5.QtWidgets import QAction, QComboBox


class ActionComboBox(QComboBox):
    def __init__(self, *args, action: QAction = None, syncText=False, resize=True, show=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.syncText = syncText
        self.targetAction = action

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        if action: self.setAction(action)

        if resize: self.resize(self.sizeHint())
        if show: self.show()

    def setAction(self, action):
        self.targetAction = action
        self.targetAction.changed.connect(self.updateFromAction)
        self.currentIndexChanged.connect(self.triggerActionWithData)
        self.updateFromAction()

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerActionWithData(self):
        self.targetAction.setData(self.currentIndex())
        self.targetAction.trigger()
        print(f"New state: {self.currentText()}")

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        QTimer().singleShot(0, self.lineEdit().selectAll)


class ValidatingComboBox(ActionComboBox):
    def __init__(self, *args, validator: QValidator = None, **kwargs):
        super().__init__(*args, **kwargs)
        if validator: self.setValidator(validator)

    def setValidator(self, validator):
        super().setValidator(validator)
        validator.validationStateChanged.connect(lambda state: self.changeTextColor(state))

    def triggerActionWithData(self):
        if self.validator().state == QValidator.Acceptable: self.changeTextColor()
        super().triggerActionWithData()

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        self.validator().validate(self.currentText(), self.lineEdit().cursorPosition())

    def focusOutEvent(self, QFocusEvent):
        super().focusOutEvent(QFocusEvent)
        if self.validator().state == QValidator.Acceptable: self.changeTextColor()

    def changeTextColor(self, state=None):
        if state == QValidator.Acceptable:
            self.lineEdit().setStyleSheet('color: forestgreen')
        elif state == QValidator.Intermediate:
            self.lineEdit().setStyleSheet('color: mediumblue')
        elif state == QValidator.Invalid:
            self.lineEdit().setStyleSheet('color: red')
        else:
            self.lineEdit().setStyleSheet('color: black')
