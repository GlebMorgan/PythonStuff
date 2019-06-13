from typing import Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QValidator


class Validator:
    """ ...  # TODO
        For defining validator function
    """

    def __new__(cls, *args, base: type = QValidator, validate: Callable = None):
        return type(cls.__name__, (base, NotifyingValidator), {})(*args, validate=validate)


class NotifyingValidator:
    """ ...  # TODO
            .validate() could be provided as an alternative way to define 'validate' override, besides inheritance

            API:

            NotifyingValidator(baseClass, *args, [validate:Callable])
                If .validate() is provided, its signature should conform to one of the following:
                    validate_function(text:str, pos:int) -> tuple(newState:QValidator.State, newText:str, newPos:int)
                    validate_method(self, text:str, pos:int) ->  ——— || ———
        """

    def __init__(self, *args, validate: Callable = None):
        super().__init__(*args)
        self.state = None
        if validate: self.validate = lambda text, pos: validate(self, text, pos)

    triggered = pyqtSignal(QValidator.State)
    validationStateChanged = pyqtSignal(QValidator.State)
