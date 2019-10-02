from __future__ import annotations as annotations_feature

import traceback
import sys
from typing import NamedTuple, Union
from types import FrameType


class Traceback(NamedTuple):
    tb_frame: FrameType
    tb_lasti: int
    tb_lineno: int
    tb_next: Union[FrameType, Traceback]


def _excepthook_(exc_type, exc_value, exc_tb):
    enriched_tb = _add_missing_frames_(exc_tb) if exc_tb else exc_tb

    print(dir(exc_tb.tb_frame))
    traceback.print_exception(exc_type, exc_value, enriched_tb)


def _add_missing_frames_(tb):
    result = Traceback(tb.tb_frame, tb.tb_lasti, tb.tb_lineno, tb.tb_next)
    frame = tb.tb_frame.f_back
    while frame:
        result = Traceback(frame, frame.f_lasti, frame.f_lineno, result)
        frame = frame.f_back
    return result


def install_exhook():
    sys.excepthook = _excepthook_