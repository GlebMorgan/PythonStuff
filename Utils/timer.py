import time

class Timer:
    def __init__(self, name=None):
        self.name = name
        self.tstart = None
        self.running = False

    def __enter__(self):
        self.start()

    def __exit__(self, errtype, value, traceback):
        self.stop()

    def start(self):
        if not self.running:
            self.running = True
            self.tstart = time.time()

    def stop(self):
        if self.running:
            self.running = False
            print(f"[{self.name or 'Timer'}] duration: {time.time() - self.tstart}")
