from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QRegularExpressionValidator as QRegexValidator, QFontMetrics
from PyQt5.QtWidgets import QApplication, QPushButton, QComboBox, QLineEdit, QSizePolicy


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
        if self.validator().validate(self.text(), -1)[0] != QRegexValidator.Acceptable:
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
        QTimer.singleShot(0, lambda: self.lineEdit().editingFinished.connect(
                lambda: self.triggered.emit() if not self.view().hasFocus() else None))

    def text(self):
        return self.lineEdit().text()

    def setText(self, text):
        return self.lineEdit().setText(text)
