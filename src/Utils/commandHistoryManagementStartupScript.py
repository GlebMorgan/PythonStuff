import atexit
import os
import readline
import rlcompleter

"""
Script saves and loads interactive sessions input history

History file is stored at %USERPROFILE%\.pyhistory
File is loaded on startup and automatically saved before interpreter exits
"""

historyPath = os.path.expanduser("~/.pyhistory")

if os.path.exists(historyPath):
    readline.read_history_file(historyPath)

def save_history(path=historyPath):
    import readline
    readline.write_history_file(path)

atexit.register(save_history)

del os, atexit, readline, rlcompleter, save_history, historyPath