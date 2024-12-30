import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class RestartHandler(FileSystemEventHandler):
    def __init__(self, script):
        self.script = script
        self.process = None
        self.restart_script()

    def restart_script(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
        print(f"Starting {self.script}...")
        self.process = subprocess.Popen([sys.executable, self.script])

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"Detected change in {event.src_path}. Restarting...")
            self.restart_script()

    def on_created(self, event):
        if event.src_path.endswith('.py'):
            print(f"New file detected: {event.src_path}. Restarting...")
            self.restart_script()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autostart.py <script-to-run>")
        sys.exit(1)

    script_to_run = sys.argv[1]

    event_handler = RestartHandler(script_to_run)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
