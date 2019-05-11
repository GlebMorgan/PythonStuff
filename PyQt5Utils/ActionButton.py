from PyQt5.QtWidgets import QPushButton


class ActionButton(QPushButton):
    def __init__(self, *args, action):
        super().__init__(*args)
        self.actions = action
        action.changed.connect(self.updateFromAction)
        self.clicked.connect(action.trigger)

    def updateFromAction(self):
        self.setText(self.action.text())
        self.setStatusTip(self.action.statusTip())
        self.setToolTip(self.action.toolTip())
        self.setIcon(self.action.icon())
        self.setEnabled(self.action.isEnabled())
        self.setCheckable(self.action.isCheckable())
        self.setChecked(self.action.isChecked())
