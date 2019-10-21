from __future__ import annotations as annotations_feature

import sys
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

from .exhook import install_exhook
from .colorer import Colorer, DisplayColor
from .helpers import QWorkerThread, pushed, blockedSignals, preservedSelection
from .extended_widgets import QRightclickButton, QSqButton, QSymbolLineEdit, QAutoSelectLineEdit, QHoldFocusComboBox
from .extended_widgets import QIndicator, QFixedLabel

from Transceiver import SerialTransceiver, SerialError
from Utils import Logger, formatList, ignoreErrors, AttrEnum, legacy

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #

# ✓ Tooltips

# ✗ Check for actions() to be updated when I .addAction() to widget

# TODO: Keyboard-layout independence option

# ✓ Transaction status indicator: blinks red (comm error), yellow (timeout), green (successful transaction), etc.

# ✓ Do not accept and apply value in combobox's lineEdit when drop-down is triggered

# CONSIDER: combine CommButton and CommModeDropDown in one button
#     (use .setMouseTracking() to control what subwidget to activate)

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #

# Default layout spacing = 5
# Default ContentsMargins = 12

log = Logger("CommPanel")

# True ––► test button and test methods are added
DEBUG_MODE = False

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

    def new(self, name: str, widget: QWidget = None, shortcut: str = None,
            slot: Callable = None, context: Qt.ShortcutContext = Qt.WindowShortcut):
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


class CommMode(AttrEnum):
    __names__ = 'label', 'description', 'handler'

    Continuous = 'Start', "Start/Stop communication loop", "triggerCommunication"
    Manual = 'Send/Auto', "Packets are sent automatically + on button click", "triggerTransaction"
    Smart = 'Send', "Send single packet", "triggerTransaction"


class SerialCommPanel(QWidget):
    """ For CommMode.Continuous return status denotes whether communication is started (True) or stopped (False) """

    comPortsRefreshed = pyqtSignal(tuple)  # (new com ports list)
    commModeChanged = pyqtSignal(CommMode)  # (new mode)
    serialConfigChanged = pyqtSignal(str, str)  # (setting name, new value)
    bindingAdded = pyqtSignal(CommMode)  # (added binding mode)

    Mode = CommMode  # to access CommMode available outside (for ex., in .bind())

    def __init__(self, parent, devInt=None, *args):
        super().__init__(parent, *args)

        # Core
        self.serialInt: SerialTransceiver = None
        self.actionList = super().actions
        self.comUpdaterThread: QThread = None
        self.commMode: CommMode = None
        self.actions = WidgetActions(self)

        # Bindings
        self.activeCommBinding = None  # active communication binding
        self.commBindings = dict.fromkeys(CommMode.__members__.keys())

        # Widgets
        self.indicator = QIndicator(self, duration=150)
        self.commButton = self.newCommButton()
        self.commModeButton = self.newCommModeButton()
        self.commModeMenu = self.newCommModeMenu()
        self.comCombobox = self.newComCombobox()
        self.refreshPortsButton = self.newRefreshPortsButton()
        self.baudCombobox = self.newBaudCombobox()
        self.bytesizeEdit = self.newDataFrameEdit(name='bytesize', chars=SerialTransceiver.BYTESIZES)
        self.parityEdit = self.newDataFrameEdit(name='parity', chars=SerialTransceiver.PARITIES)
        self.stopbitsEdit = self.newDataFrameEdit(name='stopbits', chars=(1, 2))
        if DEBUG_MODE: self.testButton = self.newTestButton()

        self.setup(devInt)

    def setup(self, interface):
        self.initLayout()
        self.setInterface(interface)
        self.updateComPortsAsync()
        self.setFixedSize(self.sizeHint())  # CONSIDER: SizePolicy is not working
        self.setFocusPolicy(Qt.TabFocus)
        self.setFocusProxy(self.commButton)
        # self.commButton.setFocus()
        # self.setStyleSheet('background-color: rgb(200, 255, 200)')

    def initLayout(self):
        spacing = self.font().pointSize()
        smallSpacing = spacing/4
        layout = QHBoxLayout()
        layout.setContentsMargins(*(smallSpacing,)*4)
        layout.setSpacing(0)

        layout.addWidget(self.indicator)
        layout.addWidget(self.commButton)
        layout.addWidget(self.commModeButton)
        layout.addSpacing(spacing)
        layout.addWidget(QFixedLabel("COM", self))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.comCombobox)
        layout.addWidget(self.refreshPortsButton)
        layout.addSpacing(spacing)
        layout.addWidget(QFixedLabel("BAUD", self))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.baudCombobox)
        layout.addSpacing(spacing)
        layout.addWidget(QFixedLabel("FRAME", self))
        layout.addSpacing(smallSpacing)
        layout.addWidget(self.bytesizeEdit)
        layout.addWidget(QFixedLabel("–", self))
        layout.addWidget(self.parityEdit)
        layout.addWidget(QFixedLabel("–", self))
        layout.addWidget(self.stopbitsEdit)
        if DEBUG_MODE:
            layout.addSpacing(spacing)
            layout.addWidget(self.testButton)

        self.setLayout(layout)

    def newCommButton(self):
        def setMode(this: QRightclickButton, mode:CommMode):
            this.setText(mode.label)
            this.setToolTip(mode.description)

        def setState(this: QRightclickButton, running:bool):
            assert self.commMode == CommMode.Continuous
            if running is None: return
            this.setText('Stop' if running else 'Start')
            self.commModeMenu.setDisabled(running)
            self.comCombobox.setDisabled(running)
            this.state = running

        this = QRightclickButton('Connect', self)
        this.colorer = Colorer(this)
        this.state = False

        action = self.actions.add(id='communicate', name='Trigger communication/transaction',
                                  widget=this, shortcut=QKeySequence("Ctrl+T"),
                                  slot=lambda: getattr(self, self.commMode.handler)())
        this.clicked.connect(action.trigger)

        # ▼ Bind methods to commButton
        this.setMode = setMode.__get__(this, this.__class__)
        this.setState = setState.__get__(this, this.__class__)

        this.rclicked.connect(partial(self.dropStartButtonMenuBelow, this))
        self.commModeChanged.connect(this.setMode)

        this.setDisabled(True)
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
        this.setLineEdit(QAutoSelectLineEdit())
        this.setEditable(True)
        this.setInsertPolicy(QComboBox.NoInsert)
        this.setFixedWidth(QFontMetrics(self.font()).horizontalAdvance('000') + self.height())
        this.contents = ()
        this.colorer = Colorer(widget=this, base=this.lineEdit())
        action = self.actions.add(id='setPort', name='Change COM port', widget=this,
                                  slot=partial(self.changeSerialConfig, 'port'))
        # this.lineEdit().setStyleSheet('background-color: rgb(200, 255, 200)')
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
        this.setToolTip("Baudrate (data speed)")
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

    def newTestButton(self):
        this = QRightclickButton('Test', self)
        this.clicked.connect(lambda: print("click on button!"))
        this.lclicked.connect(self.testSlotL)
        this.rclicked.connect(self.testSlotR)
        this.mclicked.connect(self.testSlotM)
        this.colorer = Colorer(this)
        this.setToolTip("Test")
        return this

    def dropStartButtonMenuBelow(self, qWidget):
        self.commModeMenu.exec(self.mapToGlobal(qWidget.geometry().bottomLeft()))

    def setInterface(self, interface):
        self.serialInt = interface
        if interface is not None:
            self.updateSerialConfig()
            if interface.port is not None:
                self.comCombobox.setText(interface.port.lstrip('COM'))

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
                self.commModeButton.colorer.blink(DisplayColor.Green)
                self.commModeChanged.emit(mode)
                log.info(f"Communication mode ——► {mode.name}")
                return True
            else:
                self.commModeButton.colorer.blink(DisplayColor.Red)
                log.error(f"No method binding is set for mode '{mode}'")
                return False
        finally:
            for action in self.commModeMenu.group.actions():
                if action.mode == self.commMode:
                    action.setChecked(True)
                    break

    @staticmethod
    def getComPortsList():
        log.debug(f"Update thread ID: {int(QThread.currentThreadId())}")
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
        thread.finished.connect(self.notifyComPortsUpdated)
        self.comUpdaterThread = thread
        log.debug(f"Main thread ID: {int(QThread.currentThreadId())}")
        thread.start()

    def notifyComPortsUpdated(self):
        self.refreshPortsButton.anim.stop()
        self.refreshPortsButton.anim.jumpToFrame(0)
        self.comUpdaterThread = None
        self.comPortsRefreshed.emit(self.comCombobox.contents)
        log.debug(f"Updating com ports ——► DONE")

    def updateComCombobox(self, ports: List[ComPortInfo]):
        log.debug("Refreshing com ports combobox...")
        combobox = self.comCombobox
        # currentPort = combobox.text()
        newPortNumbers = tuple((port.device.strip('COM') for port in ports))

        if combobox.contents != newPortNumbers:
            with preservedSelection(combobox):
                with blockedSignals(combobox):
                    combobox.clear()
                    combobox.addItems(newPortNumbers)
                for i, port in enumerate(ports):
                    combobox.setItemData(i, port.description, Qt.ToolTipRole)
                # combobox.setCurrentIndex(combobox.findText(currentPort))
                try: port = self.serialInt.port.strip('COM')
                except AttributeError: port = ''
                combobox.setCurrentText(port)
                combobox.contents = newPortNumbers
            currentComPortsRegex = QRegex('|'.join(combobox.contents), options=QRegex.CaseInsensitiveOption)
            combobox.setValidator(QRegexValidator(currentComPortsRegex))
            combobox.colorer.patchValidator()
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
            assert self.sender().widget.text() == str(value).lstrip('COM')
            # setattr(interface, setting, None)  # BUG: does not work for baudrate, for ex.
            colorer.setBaseColor(DisplayColor.LightRed)
            return False
        else:
            log.info(f"Serial {setting} ——► {value}")
            colorer.resetBaseColor()
            colorer.blink(DisplayColor.Green)
            self.serialConfigChanged.emit(setting, str(value))
            return True

    def updateSerialConfig(self):
        for name, action in self.actions.items():
            if not name.startswith('change'): continue
            name = name.lstrip('change').lower()
            value = str(getattr(self.serialInt, name))
            if action.widget.text() != value:
                action.widget.setText(value)
                action.widget.colorer.blink(DisplayColor.Blue)

    def bind(self, mode: CommMode, function: Callable):
        """ First binding added is considered default one """
        self.commBindings[mode.name] = function
        if self.commMode is None:
            self.changeCommMode(mode)
            self.commButton.setDisabled(False)
            log.debug(f"Default communication mode changed to {mode.name}")
        self.commModeButton.colorer.blink(DisplayColor.Blue)
        self.bindingAdded.emit(mode)
        log.info(f"Communication binding added: {function.__name__}() <{mode.name}>")

    def triggerCommunication(self):
        # ▼ No idea why this works only if these 2 lines are combined into single callback... :|
        def cleanupBufferedClicks(status):
            QApplication.processEvents()
            self.commButton.setState(status)

        button = self.commButton
        with pushed(button):
            status = self.commBindings[self.commMode.name](button.state)
            if status is None:
                return
            if status is not button.state:
                button.colorer.setBaseColor(DisplayColor.LightGreen if status else None)
            else:
                button.colorer.blink(DisplayColor.Red)
            QTimer.singleShot(0, partial(cleanupBufferedClicks, status))

    def triggerTransaction(self):
        button = self.commButton
        with pushed(button):
            status = self.commBindings[self.commMode.name]()
            if status is True: button.colorer.blink(DisplayColor.Green)
            elif status is False: button.colorer.blink(DisplayColor.Red)
            else: return

    if DEBUG_MODE:

        def testCommBinding(self, state):
            from random import randint
            if state is False and randint(0,2) == 0:
                log.debug("<Imitating com port opening failure>")
                return False
            try:
                if state is True:
                    self.serialInt.close()
                    log.debug(f"TEST: {self.serialInt.port} ▼")
                    return False
                else:
                    self.serialInt.open()
                    log.debug(f"TEST: {self.serialInt.port} ▲")
                    return True
            except SerialError as e:
                log.error(e)
                return state

        def testSlotL(self, par=..., *args):
            if par is not ...: print(f"Par: {par}")
            print(f"Serial int: {self.serialInt}")
            print(f"Communication mode: {self.commMode.name}")
            self.bytesizeEdit.colorer.setBaseColor(QColor(255,127,127))
            self.parityEdit.colorer.setBaseColor(QColor(127,255,127))
            self.stopbitsEdit.colorer.setBaseColor(QColor(127,127,255))
            QTimer.singleShot(20, partial(self.testButton.colorer.blink, DisplayColor.Green))

        def testSlotR(self):
            if self.testButton.colorer.color() == DisplayColor.LightRed.value:
                self.testButton.colorer.resetBaseColor()
            else:
                self.testButton.colorer.setBaseColor(DisplayColor.LightRed)

        def testSlotM(self):
            print(self.commButton.isChecked())


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


if __name__ == '__main__':

    if len(log.handlers) == 2 and type(log.handlers[0] is type(log.handlers[1])):
        del log.handlers[1]

    install_exhook()

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
