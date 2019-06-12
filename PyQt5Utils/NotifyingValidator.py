from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QRegExpValidator


class NotifyingValidator(QRegExpValidator):

    # TODO: add validator assignment functionality by providing .validate() function
    #       in constructor, not only by subclassing (just like it is made in Colorer class)

    def __init__(self, *args):
        self.state = None
        super().__init__(*args)

    triggered = pyqtSignal(QRegExpValidator.State)
    validationStateChanged = pyqtSignal(QRegExpValidator.State)