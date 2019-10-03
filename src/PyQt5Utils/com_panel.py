from __future__ import annotations as annotations_feature

import sys
from contextlib import contextmanager
from enum import Enum
from functools import partial
from os.path import expandvars as envar, dirname
from typing import Union, Callable, List, Optional
from serial.tools.list_ports_common import ListPortInfo as ComPortInfo
from serial.tools.list_ports_windows import comports
from pkg_resources import resource_filename, cleanup_resources, set_extraction_path

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QObject, QThread, QTimer, QRegularExpression as QRegex
from PyQt5.QtGui import QFontMetrics, QKeySequence, QRegularExpressionValidator as QRegexValidator
from PyQt5.QtGui import QIcon, QMovie, QColor
from PyQt5.QtWidgets import QAction, QSizePolicy, QActionGroup
from PyQt5.QtWidgets import QWidget, QApplication, QHBoxLayout, QComboBox, QPushButton, QLineEdit, QMenu, QLabel

from .colorer import Colorer, DisplayColor

from Transceiver import SerialTransceiver, SerialError
from Utils import Logger, formatList, ignoreErrors

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #
# TEMP TESTME TODO FIXME NOTE CONSIDER

# ✓ Tooltips

# ? TODO: Check for actions() to be updated when I .addAction() to widget

# TODO: Keyboard-layout independence option

# ✓ Do not accept and apply value in combobox's lineEdit when drop-down is triggered

# CONSIDER: combine CommButton and CommModeDropDown in one button
#     (use .setMouseTracking() to control what subwidget to activate)

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #

# Default layout spacing = 5
# Default ContentsMargins = 12

log = Logger("CommPanel")

REFRESH_GIF = resource_filename(__name__, 'res/refresh.gif')


class QDataAction(QAction):
    def __init__(self, *args, widget: QWidget):
        super().__init__(*args)
        self.widget = widget

    def triggerString(self, data:str):
        self.setData(data)
        self.trigger()
        self.widget.setText(data)


class WidgetActions(dict):
    def __init__(self, owner: QWidget):
        super().__init__()
        self.owner: QWidget = owner

    def addAction(self, action: QAction):
        self.owner.addAction(action)
        self[action.text().lower()] = action
        log.debug(f"Action '{action.text()}' created, id={action.text().lower()}")
        return action

    def add(self, id: str, *args, **kwargs):
        action = self.new(*args, **kwargs)
        self[id] = action
        return action

    def new(self, name: str, widget: QWidget = None, slot: Callable = None,
            shortcut: str = None, context: Qt.ShortcutContext = Qt.WindowShortcut):
        this = QDataAction(name, self.owner, widget=widget)
        if slot:
            this.slot = slot
            this.triggered.connect(slot)
        if shortcut:
            this.setShortcut(QKeySequence(shortcut))
            this.setShortcutContext(context)
        self.owner.addAction(this)
        return this

    def __getattr__(self, item):
        """ Mock for pyCharm syntax highlighter """
        raise AttributeError(f"Action '{item}' does not exist")


class QRightclickButton(QPushButton):
    rclicked = pyqtSignal()
    lclicked = pyqtSignal()
    mclicked = pyqtSignal()

    def mouseReleaseEvent(self, qMouseEvent):
        if qMouseEvent.button() == Qt.RightButton:
            self.rclicked.emit()
        elif qMouseEvent.button() == Qt.LeftButton:
            self.lclicked.emit()
        elif qMouseEvent.button() == Qt.MiddleButton:
            self.mclicked.emit()
        return super().mouseReleaseEvent(qMouseEvent)


class QSqButton(QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        height = super().sizeHint().height()
        return QSize(height, height)


class QAutoSelectLineEdit(QLineEdit):

    def __init__(self, *args):
        super().__init__(*args)
        self.savedState = self.text()

    def mouseReleaseEvent(self, qMouseEvent):
        if qMouseEvent.button() == Qt.LeftButton and QApplication.keyboardModifiers() & Qt.ControlModifier:
            QTimer.singleShot(0, self.selectAll)
        elif qMouseEvent.button() == Qt.MiddleButton:
            QTimer.singleShot(0, self.selectAll)
        return super().mouseReleaseEvent(qMouseEvent)

    def focusInEvent(self, qFocusEvent):
        self.savedState = self.text()
        return super().focusInEvent(qFocusEvent)

    def focusOutEvent(self, qFocusEvent):
        if self.text().strip() == '':
            self.setText(self.savedState)
        return super().focusOutEvent(qFocusEvent)


class QSymbolLineEdit(QAutoSelectLineEdit):
    def __init__(self, *args, symbols, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = tuple(str(item) for item in symbols)

    def sizeHint(self):
        if isinstance(self.symbols, str):
            width = QFontMetrics(self.font()).horizontalAdvance(self.symbols)
        else:
            width = max(QFontMetrics(self.font()).horizontalAdvance(ch) for ch in self.symbols)
        height = super().sizeHint().height()
        self.setMaximumWidth(width+height/2)
        return QSize(width+height/2, super().sizeHint().height())


class QHoldFocusComboBox(QComboBox):
    triggered = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QTimer.singleShot(0, lambda:
            self.lineEdit().editingFinished.connect(
                lambda: self.triggered.emit() if not self.view().hasFocus() else None))

    def text(self):
        return self.lineEdit().text()

    def setText(self, text):
        return self.lineEdit().setText(text)


class QWorkerThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, *args, name=None, target):
        super().__init__(*args)
        self.function = target
        if name is not None: self.setObjectName(name)

    def run(self):
        log.debug(f"Test thread ID: {int(QThread.currentThreadId())}")
        self.done.emit(self.function())


class CommMode(Enum):
    Continuous = 0
    Manual = 1
    Smart = 2


class SerialCommPanel(QWidget):

    def __init__(self, parent, devInt=None, *args):
        super().__init__(parent, *args)

        # Core
        self.serialInt: SerialTransceiver = None
        self.actionList = super().actions
        self.comUpdaterThread: QThread = None
        self.commMode: CommMode = CommMode.Continuous
        self.actions = WidgetActions(self)

        # Bindings
        self.activeCommBinding = None  # active communication binding
        self.commBindings = dict.fromkeys(CommMode.__members__.keys())

        # Widgets
        # self.testButton = self.newTestButton()  # TEMP
        self.commButton = self.newCommButton()
        self.commModeButton = self.newCommModeButton()
        self.commModeMenu = self.newCommModeMenu()
        self.comCombobox = self.newComCombobox()
        self.refreshPortsButton = self.newRefreshPortsButton()
        self.baudCombobox = self.newBaudCombobox()
        self.bytesizeEdit = self.newDataFrameEdit(name='bytesize', chars=SerialTransceiver.BYTESIZES)
        self.parityEdit = self.newDataFrameEdit(name='parity', chars=SerialTransceiver.PARITIES)
        self.stopbitsEdit = self.newDataFrameEdit(name='stopbits', chars=(1, 2))

        self.setup(devInt)

    def setup(self, interface):
        self.initLayout()
        self.commButton.setFocus()
        self.updateComPortsAsync()
        self.setInterface(interface)
        self.commButton.setFocus()
        self.setFixedSize(self.sizeHint())  # CONSIDER: SizePolicy is not working
        # self.setStyleSheet('background-color: rgb(200, 255, 200)')

    def initLayout(self):
        spacing = self.font().pointSize()
        smallSpacing = spacing/4
        layout = QHBoxLayout()
        layout.setContentsMargins(*(smallSpacing,)*4)
        layout.setSpacing(0)
        layout.addWidget(self.commButton)
        layout.addWidget(self.commModeButton)
        layout.addSpacing(spacing)
        layout.addWidget(self.newLabel("COM"))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.comCombobox)
        layout.addWidget(self.refreshPortsButton)
        layout.addSpacing(spacing)
        layout.addWidget(self.newLabel("BAUD"))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.baudCombobox)
        layout.addSpacing(spacing)
        layout.addWidget(self.newLabel("FRAME"))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.bytesizeEdit)
        layout.addWidget(self.newLabel("–"))
        layout.addWidget(self.parityEdit)
        layout.addWidget(self.newLabel("–"))
        layout.addWidget(self.stopbitsEdit)
        # layout.addSpacing(spacing)  # TEMP
        # layout.addWidget(self.testButton)  # TEMP
        self.setLayout(layout)

    def newCommButton(self):
        def updateState(this: QRightclickButton):
            if self.serialInt is None: return
            mode = self.commMode
            if mode == CommMode.Continuous:
                if self.serialInt.is_open:
                    this.setText('Stop')
                    this.colorer.setBaseColor(DisplayColor.LightGreen)
                else:
                    this.setText('Start')
                    this.colorer.resetBaseColor()
                this.setToolTip("Start/Stop communication loop")
            elif mode == CommMode.Smart:
                this.setText('Send/Auto')
                this.setToolTip("Packets are sent automatically + on button click")
            elif mode == CommMode.Manual:
                this.setText('Send')
                this.setToolTip("Send single packet")
            else: raise AttributeError(f"Unsupported mode '{mode.name}'")

        this = QRightclickButton('Connect', self)
        this.colorer = Colorer(this)
        this.updateState = updateState.__get__(this, this.__class__)  # bind method to commButton
        this.rclicked.connect(partial(self.dropStartButtonMenuBelow, this))
        this.clicked.connect(self.startCommunication)
        this.clicked.connect(this.updateState)
        return this

    def newCommModeMenu(self):
        # CONSIDER: Radio button options are displayed as ✓ instead of • when using .setStyleSheet() on parent
        this = QMenu("Communication mode", self)
        actionGroup = QActionGroup(self)
        for mode in CommMode.__members__.keys():
            action = actionGroup.addAction(QAction(f'{mode} mode', self))
            action.setCheckable(True)
            action.mode = CommMode[mode]
            this.addAction(action)
            if mode == self.commMode.name: action.setChecked(True)
        actionGroup.triggered.connect(self.changeCommMode)
        this.group = actionGroup
        return this

    def newCommModeButton(self):
        this = QSqButton('▼', self)  # CONSIDER: increases height with '🞃'
        this.clicked.connect(partial(self.dropStartButtonMenuBelow, self.commButton))
        this.colorer = Colorer(this)
        this.setToolTip("Communication mode")
        return this

    def newComCombobox(self):
        this = QHoldFocusComboBox(parent=self)
        this.contents = ()
        this.setLineEdit(QAutoSelectLineEdit())
        this.setEditable(True)
        this.setInsertPolicy(QComboBox.NoInsert)
        # this.lineEdit().setStyleSheet('background-color: rgb(200, 255, 200)')
        this.setFixedWidth(QFontMetrics(self.font()).horizontalAdvance('000') + self.height())
        this.colorer = Colorer(widget=this, base=this.lineEdit())
        action = self.actions.add(id='setPort', name='Change COM port', widget=this,
                                  slot=partial(self.changeSerialConfig, 'port'))
        this.triggered.connect(action.trigger)
        this.setToolTip("COM port")
        # NOTE: .validator and .colorer are set in updateComCombobox()
        return this

    def newRefreshPortsButton(self):
        this = QSqButton(self)
        action = self.actions.add(id='refreshPorts', name='Refresh COM ports',
                                  slot=self.updateComPortsAsync, shortcut=QKeySequence("Ctrl+R"))
        this.clicked.connect(action.trigger)
        this.setIcon(QIcon(REFRESH_GIF))
        this.setIconSize(this.sizeHint() - QSize(10, 10))
        this.anim = QMovie(REFRESH_GIF, parent=this)
        this.anim.frameChanged.connect(lambda: this.setIcon(QIcon(this.anim.currentPixmap())))
        if cleanup_resources() is not None:
            log.warning(f"Failed to cleanup temporary resources (refresh icon): {cleanup_resources()}")
        this.setToolTip("Refresh COM ports list")
        return this

    def newBaudCombobox(self):
        MAX_DIGITS = 7
        this = QHoldFocusComboBox(parent=self)
        this.setLineEdit(QAutoSelectLineEdit())
        this.setEditable(True)
        this.setInsertPolicy(QComboBox.NoInsert)
        this.setSizeAdjustPolicy(this.AdjustToContents)
        this.maxChars = MAX_DIGITS
        # this.lineEdit().setStyleSheet('background-color: rgb(200, 200, 255)')
        bauds = SerialTransceiver.BAUDRATES
        items = bauds[bauds.index(9600): bauds.index(921600)+1]
        this.addItems((str(num) for num in items))
        this.setMaxVisibleItems(len(items))
        with ignoreErrors(): this.setCurrentIndex(items.index(SerialTransceiver.DEFAULT_CONFIG['baudrate']))
        this.setFixedWidth(QFontMetrics(self.font()).horizontalAdvance('0'*MAX_DIGITS) + self.height())
        log.debug(f"BaudCombobox: max items = {this.maxVisibleItems()}")
        action = self.actions.add(id='changeBaudrate', name='Change COM baudrate', widget=this,
                                  slot=partial(self.changeSerialConfig, 'baudrate'))
        this.triggered.connect(action.trigger)
        this.setValidator(QRegexValidator(QRegex(rf"[1-9]{{1}}[0-9]{{0,{MAX_DIGITS-1}}}"), this))
        this.colorer = Colorer(widget=this, base=this.lineEdit())
        this.setToolTip("Baudrate (speed)")
        return this

    def newDataFrameEdit(self, name, chars):
        chars = tuple(str(ch) for ch in chars)
        this = QSymbolLineEdit("X", self, symbols=chars)
        this.setAlignment(Qt.AlignCenter)
        this.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        this.setText(str(SerialTransceiver.DEFAULT_CONFIG[name]))
        this.textEdited.connect(lambda text: this.setText(text.upper()))
        action = self.actions.add(id=f'change{name.capitalize()}', name=f'Change COM {name}', widget=this,
                                  slot=partial(self.changeSerialConfig, name))
        this.editingFinished.connect(action.trigger)
        this.setValidator(QRegexValidator(QRegex('|'.join(chars), options=QRegex.CaseInsensitiveOption)))
        this.colorer = Colorer(this)
        # this.setStyleSheet('background-color: rgb(255, 200, 200)')
        this.setToolTip(name.capitalize())
        return this

    def newLabel(self, text):
        this = QLabel(text, self)
        this.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return this

    def newTestButton(self):
        this = QRightclickButton('Test', self)
        this.clicked.connect(lambda: print("click on button!"))
        this.rclicked.connect(self.testSlot2)
        # this.setProperty('testField', True)
        this.colorer = Colorer(this)
        this.setToolTip("Test")
        return this

    def dropStartButtonMenuBelow(self, qWidget):
        self.commModeMenu.exec(self.mapToGlobal(qWidget.geometry().bottomLeft()))

    def setInterface(self, interface):
        self.serialInt = interface
        self.commButton.updateState()

    def changeCommMode(self, action: Union[QAction, CommMode]):
        if isinstance(action, CommMode): mode = action
        else: mode = action.mode

        if mode == self.commMode:
            log.debug(f"Mode={mode.name} is already set — cancelling")
            return None

        log.debug(f"Changing communication mode to {mode}...")
        commBinding = self.commBindings[mode.name]
        try:
            if commBinding is not None:
                self.commMode = mode
                self.commButton.updateState()
                self.activeCommBinding = commBinding
                self.commModeButton.colorer.blink(DisplayColor.Green)
                log.info(f"Communication mode ——► {mode.name}")
                return True
            else:
                self.commModeButton.colorer.blink(DisplayColor.Red)
                log.error(f"Mode '{mode}' is not implemented (no method binding)")
                return False
        finally:
            for action in self.commModeMenu.group.actions():
                if action.mode == self.commMode:
                    action.setChecked(True)
                    break

    @staticmethod
    def getComPortsList():
        log.debug("Fetching com ports...")
        newComPorts: List[ComPortInfo] = comports()
        log.debug(f"New com ports list: {', '.join(port.device for port in newComPorts)} ({len(newComPorts)} items)")
        return newComPorts

    def updateComPortsAsync(self):
        if self.comUpdaterThread is not None:
            log.debug("Update is already running - cancelled")
            return
        log.debug(f"Updating COM ports...")
        thread = QWorkerThread(self, name="COM ports refresh", target=self.getComPortsList)
        thread.done.connect(self.updateComCombobox)
        thread.started.connect(self.refreshPortsButton.anim.start)
        thread.finished.connect(self.finishUpdateComPorts)
        self.comUpdaterThread = thread
        log.debug(f"Main thread ID: {int(QThread.currentThreadId())}")
        thread.start()

    def finishUpdateComPorts(self):
        self.refreshPortsButton.anim.stop()
        self.refreshPortsButton.anim.jumpToFrame(0)
        self.comUpdaterThread = None
        log.debug(f"Updating com ports ——► DONE")

    def updateComCombobox(self, ports: List[ComPortInfo]):
        log.debug("Refreshing com ports combobox...")
        combobox = self.comCombobox
        currentPort = combobox.text()
        newPortNumbers = tuple((port.device.strip('COM') for port in ports))
        if combobox.contents != newPortNumbers:
            with self.preservedSelection(combobox):
                with self.blockedSignals(combobox):
                    combobox.clear()
                    combobox.addItems(newPortNumbers)
                for i, port in enumerate(ports):
                    combobox.setItemData(i, port.description, Qt.ToolTipRole)
                combobox.setCurrentIndex(combobox.findText(currentPort))
                combobox.contents = newPortNumbers
            currentComPortsRegex = QRegex('|'.join(combobox.contents), options=QRegex.CaseInsensitiveOption)
            combobox.setValidator(QRegexValidator(currentComPortsRegex))
            combobox.colorer.patchValidator()
            combobox.validator().changed.connect(lambda: log.warning("Validator().changed() triggered"))  # TEMP
            if combobox.view().isVisible():
                combobox.hidePopup()
                combobox.showPopup()
            combobox.colorer.blink(DisplayColor.Blue)
            log.info(f"COM ports refreshed: {', '.join(f'COM{port}' for port in newPortNumbers)}")
        else:
            log.debug("COM ports refresh - no changes")

    def changeSerialConfig(self, setting: str) -> Optional[bool]:
        value = self.sender().data()
        colorer = self.sender().widget.colorer
        interface = self.serialInt
        if value is None: value = self.sender().widget.text()

        if value == '':
            log.debug(f"Serial setting '{setting}' is not chosen — cancelling")
            return None
        if setting == 'port':
            value = f'COM{value}'

        currValue = getattr(interface, setting, None)
        if value.isdecimal():
            value = int(value)
        if value == currValue:
            log.debug(f"{setting.capitalize()}={value} is already set — cancelling")
            return None

        try:
            setattr(interface, setting, value)
        except SerialError as e:
            log.error(e)
            setattr(interface, setting, None)
            self.commButton.updateState()
            colorer.setBaseColor(DisplayColor.LightRed)
            return False
        else:
            log.info(f"Serial {setting} ——► {value}")
            colorer.resetBaseColor()
            colorer.blink(DisplayColor.Green)
            return True

    def bind(self, mode: CommMode, function: Callable):
        self.commBindings[mode.name] = function
        if mode == self.commMode: self.activeCommBinding = function

    def startCommunication(self):
        if self.activeCommBinding is None:
            log.error(f"No communication bindings set")
            self.commButton.colorer.blink(DisplayColor.Red)
            return False
        connStatus = self.activeCommBinding()
        if connStatus is False:
            self.commButton.colorer.blink(DisplayColor.Red)
        elif connStatus is not True:
            raise TypeError(f"Communication binding .{self.activeCommBinding.__name__}() "
                            f"for '{self.commMode.name}' mode returned invalid status: {connStatus}")
        self.commButton.updateState()

    def applySerialConfig(self):
        for name, action in self.actions.items():
            if not name.startswith('change'): continue
            else: name = name.lstrip('change').lower()
            value = str(getattr(self.serialInt, name))
            if action.widget.text() != value:
                action.widget.setText(value)
                action.widget.colorer.blink(DisplayColor.Blue)

    @contextmanager
    def preservedSelection(self, widget: QWidget):
        try: textEdit = widget.lineEdit()
        except AttributeError: textEdit = widget
        try:
            if not textEdit.hasSelectedText():
                yield
                return
            else:
                currentSelection = (textEdit.selectionStart(), len(textEdit.selectedText()))
        except AttributeError:
            raise ValueError(f"Widget {widget.__class__} seems to not support text selection")

        yield currentSelection

        textEdit.setSelection(*currentSelection)

    @contextmanager
    def blockedSignals(self, qObject: QObject):
        qObject.blockSignals(True)
        yield
        qObject.blockSignals(False)

    def testCommBinding(self):
        try:
            if self.serialInt.is_open:
                self.serialInt.close()
                log.debug(f"TEST: {self.serialInt.port} ▼")
            else:
                self.serialInt.open()
                log.debug(f"TEST: {self.serialInt.port} ▲")
        except SerialError as e:
            log.error(e)
            return False
        return True

    def testSlot(self, par=...):
        if par is not ...: print(f"Par: {par}")
        print(f"Serial int: {self.serialInt}")
        print(f"Communication mode: {self.commMode.name}")
        self.bytesizeEdit.colorer.setBaseColor(QColor(255,127,127))
        self.parityEdit.colorer.setBaseColor(QColor(127,255,127))
        self.stopbitsEdit.colorer.setBaseColor(QColor(127,127,255))
        QTimer.singleShot(20, partial(self.testButton.colorer.blink, DisplayColor.Green))

    def testSlot2(self):
        if self.testButton.colorer.color() == DisplayColor.LightRed.value:
            self.testButton.colorer.resetBaseColor()
        else:
            self.testButton.colorer.setBaseColor(DisplayColor.LightRed)


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


if __name__ == '__main__':

    if len(log.handlers) == 2 and type(log.handlers[0] is type(log.handlers[1])):
        del log.handlers[1]

    def trap_exc_during_debug(*args):
        raise RuntimeError(f'PyQt5 says "{args[1]}"')
    sys.excepthook = trap_exc_during_debug

    app = QApplication(sys.argv)
    app.setStyle('fusion')

    # print(app.font().pointSize)
    # app.setFont(Chain(app.font()).setPointSize(10).ok)

    p = QWidget()
    p.setWindowTitle('Simple COM Panel - dev')
    tr = SerialTransceiver()

    cp = SerialCommPanel(p, tr)
    cp.resize(100, 20)
    cp.move(300, 300)
    cp.bind(CommMode.Continuous, cp.testCommBinding)

    l = QHBoxLayout()
    # l.addWidget(QPushButton("Test", p))
    l.addWidget(cp)
    p.setLayout(l)
    p.show()

    sys.exit(app.exec())
