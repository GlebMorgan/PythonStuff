from PyQt5.QtWidgets import QPushButton, QAction


class ActionButton(QPushButton):
    def __init__(self, *args, action: QAction = None, syncText=False, resize=True, show=True):
        super().__init__(*args)
        self.syncText = syncText

        if action:
            action.changed.connect(self.updateFromAction)
            self.clicked.connect(action.trigger)
            self.targetAction = action
            self.updateFromAction()

        if resize: self.resize(self.sizeHint())
        if show: self.show()

    def updateFromAction(self):
        if self.syncText: self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setIcon(self.targetAction.icon())
        self.setEnabled(self.targetAction.isEnabled())
        self.setCheckable(self.targetAction.isChself.targetActioneckable())
        self.setChecked(self.targetAction.isChecked())
