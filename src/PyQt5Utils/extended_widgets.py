from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QRegularExpressionValidator as QRegexValidator, QFontMetrics
from PyQt5.QtWidgets import QApplication, QPushButton, QComboBox, QLineEdit, QSizePolicy, QRadioButton, QLabel
from .colorer import Colorer


class QRightclickButton(QPushButton):
    rclicked = pyqtSignal()
    lclicked = pyqtSignal()
    mclicked = pyqtSignal()

    def mouseReleaseEvent(self, qMouseEvent):
        super().mouseReleaseEvent(qMouseEvent)
        if qMouseEvent.button() == Qt.RightButton:
            self.rclicked.emit()
        elif qMouseEvent.button() == Qt.LeftButton:
            self.lclicked.emit()
        elif qMouseEvent.button() == Qt.MiddleButton:
            self.mclicked.emit()


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
        super().mouseReleaseEvent(qMouseEvent)
        if qMouseEvent.button() == Qt.LeftButton and QApplication.keyboardModifiers() & Qt.ControlModifier:
            QTimer.singleShot(0, self.selectAll)
        elif qMouseEvent.button() == Qt.MiddleButton:
            QTimer.singleShot(0, self.selectAll)

    def focusInEvent(self, qFocusEvent):
        super().focusInEvent(qFocusEvent)
        self.savedState = self.text()

    def focusOutEvent(self, qFocusEvent):
        super().focusOutEvent(qFocusEvent)
        try:
            result = self.validator().validate(self.text(), -1)[0] != QRegexValidator.Acceptable
        except AttributeError:
            result = self.text().strip() == ''
        if result:
            self.setText(self.savedState)


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
        # QTimer.singleShot(0, lambda: self.lineEdit().editingFinished.connect(
        #         lambda: self.triggered.emit() if not self.view().hasFocus() else None))
        # ▼ Ducktape for mouse click item activation
        QTimer.singleShot(0, lambda: self.currentIndexChanged.connect(
                lambda: self.triggered.emit() if not self.view().hasFocus() else None))

    def keyPressEvent(self, qKeyEvent):
        if qKeyEvent.key() == Qt.Key_Down and QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.showPopup()
        else:
            super().keyPressEvent(qKeyEvent)

    def text(self):
        return self.lineEdit().text()

    def setText(self, text):
        return self.lineEdit().setText(text)


class QIndicator(QRadioButton):
    def __init__(self, parent, duration=120, *args):
        super().__init__(parent, *args)
        self.colorer = Colorer(self, duration=duration)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip('Transactions indicator<br>'
                        '<font color="green">ok</font> - '
                        '<font color="orange">timeout</font> - '
                        '<font color="red">error</font>')
        self.blink = self.colorer.blink
        self.blinkHalo = self.colorer.blinkHalo

    def sizeHint(self):
        height = super().sizeHint().height()
        return QSize(height, height)

    def mousePressEvent(self, *args, **kwargs):
        # CONSIDER: block built-in click event handlers rather than shut down the event entirely
        return


class QFixedLabel(QLabel):
    def __init__(self, *args):
        super().__init__(*args)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
