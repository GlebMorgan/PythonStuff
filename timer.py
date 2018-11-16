import time

class Timer:
    def __init__(self, name=None):
        self.name = name

    def __enter__(self):
        self.tstart = time.time()

    def __exit__(self, type, value, traceback):
        name = self.name or ""
        print('[{}] Duration: {}'.format(name, time.time() - self.tstart))
