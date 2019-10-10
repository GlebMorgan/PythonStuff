from typing import Union

from PyQt5.QtCore import QThread, pyqtSignal
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
    def __init__(self, owner: Union[QLayout, QWidget], *, layout: Union[QLayout, str], spacing=None, margins=0):
        if isinstance(layout, str):
            if layout == 'v': layout = QVBoxLayout()
            if layout == 'h': layout = QHBoxLayout()
        self.layout = layout
        self.layout.setContentsMargins(*(margins,)*4)
        if spacing: self.layout.setSpacing(spacing)
        self.owner = owner

    def __enter__(self):
        return self.layout

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.owner, QWidget):
            self.owner.setLayout(self.layout)
        elif isinstance(self.owner, QLayout):
            self.owner.addLayout(self.layout)

