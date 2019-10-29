from contextlib import contextmanager
from typing import Union

from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QLayout, QWidget, QVBoxLayout, QHBoxLayout


class QWorkerThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, *args, name=None, target):
        super().__init__(*args)
        self.function = target
        if name is not None: self.setObjectName(name)

    def run(self):
        self.done.emit(self.function())


class Block:
    """ BoxLayout helper contextmanager TODO: docstring """
    def __init__(self, owner: Union[QLayout, QWidget], *, layout: Union[QLayout, str],
                 stretch=0, spacing: int = None, margins: int = 0, attr: str = None):

        if isinstance(layout, str):
            if layout == 'v': layout = QVBoxLayout()
            if layout == 'h': layout = QHBoxLayout()
        self.owner = owner
        self.parent = owner if isinstance(owner, QWidget) else owner.parentWidget()
        self.stretch = stretch
        self.layout = layout

        if attr and attr.isidentifier():
            setattr(self.parent, attr, self.layout)
        elif attr is not None:
            raise ValueError(f"Invalid attr name '{attr}'")

        self.layout.setContentsMargins(*(margins,)*4)
        if spacing: self.layout.setSpacing(spacing)

    def __enter__(self):
        if isinstance(self.owner, QWidget):
            self.owner.setLayout(self.layout)
        elif isinstance(self.owner, QLayout):
            self.owner.addLayout(self.layout, stretch=self.stretch)
        else:
            raise TypeError(f"Invalid owner type '{self.owner.__class__.__name__}', "
                            f"expected 'QWidget' or 'QLayout'")
        return self.layout

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@contextmanager
def preservedSelection(widget: QWidget):
    try: textEdit = widget.lineEdit()
    except AttributeError: textEdit = widget

    try:
        selection = textEdit.selectedText()
    except AttributeError:
        raise ValueError(f"Widget {widget.__class__} seems to not support text selection")

    if selection == '':
        yield
        return
    else:
        currentSelection = (textEdit.selectionStart(), len(selection))
        yield selection
        textEdit.setSelection(*currentSelection)


@contextmanager
def blockedSignals(qObject: QObject):
    oldState = qObject.blockSignals(True)
    try: yield
    finally: qObject.blockSignals(oldState)


@contextmanager
def disabled(widget: QWidget):
    widget.setDisabled(True)
    widget.repaint()
    try: yield
    finally: widget.setDisabled(False)


@contextmanager
def pushed(widget: QWidget):
    widget.setDown(True)
    widget.repaint()
    try: yield
    finally: widget.setDown(False)


def setFocusChain(*args: QWidget, owner: QWidget, loop=True):
    for i in range(len(args) - 1):
        owner.setTabOrder(args[i], args[i+1])
    if loop: owner.setTabOrder(args[-1], args[0])
