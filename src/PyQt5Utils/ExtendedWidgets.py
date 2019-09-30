from __future__ import annotations

from PyQt5.QtCore import QStringListModel, QTimer, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QComboBox, QPushButton, QLineEdit, QVBoxLayout, QMessageBox
from Utils import Logger

from .WidgetColorer import Colorer
from .ExtendedWidgetsBase import ActionWidget, ColoredWidget

log = Logger("ActionWidget")


class ActionButton(QPushButton, ActionWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actionSignal = self.clicked
        self.actionSlot = lambda: self.targetAction.trigger()


class QComboBoxCooperative(QComboBox):
    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(parent=parent)


class ActionComboBox(QComboBoxCooperative, ActionWidget):

    # TODO: docs and API method arguments/return_values type annotations

    # CONSIDER: ▼ signal is failing to connect with slots when inherited from ActionWidget - reimplementing it here
    updateRequired = pyqtSignal()

    def __init__(self, *args, default='', **kwargs):

        super().__init__(*args, **kwargs)
        # QComboBox.__init__(self)
        # ActionWidget.__init__(self, *args, parent=parent, **kwargs)

        self.actionSignal = self.currentIndexChanged
        self.actionSlot = self.triggerActionWithData

        self.setModel(QStringListModel())
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.view().setSizeAdjustPolicy(self.view().AdjustToContents)

        self.setCurrentText(default)

    def triggerActionWithData(self):
        if self.view().hasFocus(): return self.restoreCurrentIndex()
        log.debug(f"Action '{self.targetAction.text()}' triggered!")
        if self.currentIndex() == -1:
            QMessageBox().warning(self, "ASSERT", "In triggerActionWithData(): self.currentIndex() == -1")
            return  # CONSIDER: what are the cases when this fires?
        if self.currentText() != self.activeValue:
            self.targetAction.setData(self.currentText())
            self.targetAction.trigger()
        else:
            QMessageBox().warning(self, "ASSERT", "In triggerActionWithData(): self.currentText() == self.activeValue")
        log.debug(f"New state: {self.currentText()}, sender: {self.sender().__class__.__name__}")

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        self.updateRequired.emit()
        QTimer().singleShot(0, self.lineEdit().selectAll)

    def restoreCurrentIndex(self):
        self.blockSignals(True)
        self.setCurrentIndex(self.findText(self.activeValue))
        self.blockSignals(False)


class ColoredComboBox(ActionComboBox, ColoredWidget):

    def __init__(self, *args, parent=None, **kwargs):
        # CONSIDER: and again - super() works incorrectly here + in 3 other methods
        super().__init__(*args, parent=parent, **kwargs)
        # ActionComboBox.__init__(self, *args, **kwargs)
        # ColoredWidget.__init__(self, *args, parent=parent, **kwargs)

    def setValidator(self, validator):
        ActionComboBox.setValidator(self, validator)
        ColoredWidget.setValidator(self, validator)

    def focusInEvent(self, QFocusEvent):
        super().focusInEvent(QFocusEvent)
        # ActionComboBox.focusInEvent(self, QFocusEvent)
        # ColoredWidget.focusInEvent(self, QFocusEvent)

    def focusOutEvent(self, QFocusEvent):
        # formatList(self.__class__.mro())
        # super().focusOutEvent(QFocusEvent)
        ColoredWidget.focusOutEvent(self, QFocusEvent)
        ActionComboBox.focusOutEvent(self, QFocusEvent)
        if self.view().hasFocus():
            self.colorer.setColor(QPalette.Text, self.colorer.DisplayColor.Black)

    # TODO: remove this test function when finished class
    def testColorizeRandomly(self):
        from random import choice
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))
        self.setPalette(palette)
        log.debug(self.lineEdit().palette().color(QPalette.WindowText).name())


class ActionLineEdit(QLineEdit, ActionWidget):

    # TODO: docs and API method arguments/return_values type annotations

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.actionSignal = self.editingFinished
        self.actionSlot = self.triggerActionWithData

        self.setText(self.activeValue)

    def setAction(self, action):
        super().setAction(action)
        self.editingFinished.connect(self.triggerActionWithData)

    def updateFromAction(self):
        self.setText(self.targetAction.text())
        self.setStatusTip(self.targetAction.statusTip())
        self.setToolTip(self.targetAction.toolTip())
        self.setEnabled(self.targetAction.isEnabled())

    def triggerActionWithData(self):
        log.debug(f"Action triggered! Text= {self.text()}")
        if self.text() != self.activeValue:
            self.targetAction.setData(self.text())
            self.targetAction.trigger()
        log.debug(f"New state: {self.text()}, sender: {self.sender().__class__.__name__}")
    # TO BE CONTINUED ...


if __name__ == '__main__':
    log = Logger("ExtendedWidgets test")

    from PyQt5.QtWidgets import QWidget, QHBoxLayout, QApplication, QLabel, QAction
    from random import choice

    def addItem(labelText, widget):
        this = QWidget()
        this.label = QLabel(labelText, this)
        this.label.resize(this.label.sizeHint())
        this.widget = widget
        this.widget.resize(this.widget.sizeHint())
        this.layout = QHBoxLayout()
        this.layout.addWidget(this.label)
        this.layout.addWidget(this.widget)
        this.setLayout(this.layout)
        layout.addWidget(this)
        this.show()
        items.append(this)
        return this.widget

    def newAction(name, parent, slot, shortcut=None):
        this = QAction(name, parent)
        if shortcut: this.setShortcut(shortcut)
        this.triggered.connect(slot)
        log.debug(f"Action {name} created: {this}")
        return this

    app = QApplication([])
    window = QWidget()
    layout = QVBoxLayout()
    items = []

    # ActionComboBox; empty constructor; updateRequired
    ur = addItem("ur: ACB no params", ActionComboBox())
    ur.updateRequired.connect(lambda: print(f'{ur.parent().label.text()}: updateRequired triggered'))
    ur.addItems(("test1", "test2", "test3", "test4", "test5"))
    ur.setAction(newAction('ur_Action', ur, lambda: print("ur_Action triggered")))

    # ActionComboBox; default=34; no items
    dni = addItem("dni: ACB, default = 34, no items set", ActionComboBox(default='34'))
    dni.setAction(newAction('dni_Action', dni, lambda: print("dni_Action triggered")))

    # ActionComboBox; default=azaza, one of the items matches default (valid default)
    dvi = addItem("dvi: ACB, default = azaza (valid), 5 items set", ActionComboBox(default='azaza'))
    dvi.addItems(('lol', 'kek', 'azaza', 'blablabla', 'rofl'))
    dvi.setAction(newAction('dvi_Action', dvi, lambda: print("dvi_Action triggered")))

    # ActionComboBox; default = bug, no item matches default (invalid default)
    dii = addItem("dii: ACB, default = bug (invalid), 5 items set", ActionComboBox(default='bug'))
    dii.addItems(str(i) for i in (1,2,3,4,5))
    dii.setAction(newAction('dii_Action', dii, lambda: print("dii_Action triggered")))

    # ColoredComboBox; empty constructor; updateRequired
    cur = addItem("cur: CCB no params", ColoredComboBox())
    cur.updateRequired.connect(lambda: print(f'{cur.parent().label.text()}: updateRequired triggered'))
    cur.addItems(("test1", "test2", "test3", "test4", "test5"))
    cur.setColorer(Colorer(target=cur, colorize=lambda colorer:
            (QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))))
    cur.setAction(newAction('cur_Action', cur, lambda: print("cur_Action triggered")))

    # ColoredComboBox; default=34; no items
    cdni = addItem("cdni: CCB, default = 34, no items set", ColoredComboBox(default='34'))
    cdni.setColorer(Colorer(target=cdni, colorize=lambda colorer:
            (QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))))
    cdni.setAction(newAction('cdni_Action', cdni, lambda: print("cdni_Action triggered")))

    # ColoredComboBox; default=azaza, one of the items matches default (valid default)
    cdvi = addItem("cdvi: CCB, default = azaza (valid), 5 items set", ColoredComboBox(default='azaza'))
    cdvi.addItems(('lol', 'kek', 'azaza', 'blablabla', 'rofl'))
    cdvi.setColorer(Colorer(target=cdvi, colorize=lambda colorer:
            (QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))))
    cdvi.setAction(newAction('cdvi_Action', cdvi, lambda: print("cdvi_Action triggered")))

    # ColoredComboBox; default = bug, no item matches default (invalid default)
    cdii = addItem("cdii: CCB, default = bug (invalid), 5 items set", ColoredComboBox(default='bug'))
    cdii.addItems(str(i) for i in (1,2,3,4,5))
    cdii.setColorer(Colorer(target=cdii, colorize=lambda colorer:
            (QPalette.Base, QColor(choice(('orange', 'aqua', 'khaki', 'magenta', 'aquamarine', 'lime'))))))
    cdii.setAction(newAction('cdii_Action', cdii, lambda: print("cdii_Action triggered")))

    window.setLayout(layout)
    window.show()

    app.exec()
