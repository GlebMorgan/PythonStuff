from subprocess import run, CREATE_NO_WINDOW, CompletedProcess
from os.path import expandvars as envar, join as joinpath
from itertools import groupby
import re
from typing import Optional, Tuple, List

SILENT_MODE = True
FETCH_COMMAND = 'list'


def get_port_pairs() -> List[Tuple[str, str]]:
    silent = '--silent' if SILENT_MODE else ''
    exe = joinpath(envar('%ProgramFiles(x86)%'), 'com0com', 'setupc.exe').join('""')

    # CONSIDER: Does not work if not running under admin - 'The requested operation requires elevation'
    result = run(args=' '.join((exe, silent, FETCH_COMMAND)), capture_output=True,
                 encoding='oem', creationflags=CREATE_NO_WINDOW)

    if result.returncode != 0:
        e = OSError("Failed to fetch com port pairs from com0com utility")
        e.stdout = result.stdout
        e.stderr = result.stderr
        raise e

    ports = re.findall(r"CNC[A|B](\d*) PortName=.*,RealPortName=(.*)", result.stdout)

    port_pairs = []
    for n, pair in groupby(ports, lambda x: x[0]):
        port_pairs.append(tuple(elem[1] for elem in pair))
    return port_pairs


def find_complement(portname: str) -> Optional[str]:
    portname = portname.upper()
    pairs = get_port_pairs()
    for pair in pairs:
        if portname == pair[1]: return pair[0]
        if portname == pair[0]: return pair[1]


if __name__ == '__main__':
    try: print(get_port_pairs())
    except OSError as e:
        print(f"Error: {e}")
        print(f"Stdout:\n{e.stdout}")
        print(f"Stderr:\n{e.stderr}")
