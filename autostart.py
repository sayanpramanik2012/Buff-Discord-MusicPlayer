import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time
from threading import Timer

class RestartHandler(FileSystemEventHandler):
    def __init__(self, script):
        self.script = script
        self.process = None
        self.restart_timer = None
        # FIXED: Directories to ignore to prevent unnecessary restarts
        self.ignored_dirs = {
            '__pycache__', 
            '.git', 
            'venv', 
            'env', 
            'node_modules', 
            'downloads',
            '.venv',
            'logs'
        }
        self.restart_script()
    
    # FIXED: Improved shutdown with timeout
    def restart_script(self):
        if self.process:
            print(f"Stopping {self.script}...")
            self.process.terminate()
            
            # Wait up to 5 seconds for graceful shutdown
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Process didn't terminate gracefully, forcing shutdown...")
                self.process.kill()
                self.process.wait()
        
        print(f"Starting {self.script}...")
        self.process = subprocess.Popen([sys.executable, self.script])
    
    # FIXED: Added debouncing to prevent multiple rapid restarts
    def debounced_restart(self):
        if self.restart_timer:
            self.restart_timer.cancel()
        
        # Wait 1 second before restarting to catch multiple file changes
        self.restart_timer = Timer(1.0, self.restart_script)
        self.restart_timer.start()
    
    def should_ignore(self, path):
        """Check if the file/directory should be ignored"""
        path_parts = path.split(os.sep)
        return any(ignored in path_parts for ignored in self.ignored_dirs)
    
    def on_modified(self, event):
        # FIXED: Ignore specific directories and add debouncing
        if event.src_path.endswith('.py') and not self.should_ignore(event.src_path):
            print(f"Detected change in {event.src_path}. Restarting...")
            self.debounced_restart()
    
    def on_created(self, event):
        # FIXED: Ignore specific directories and add debouncing
        if event.src_path.endswith('.py') and not self.should_ignore(event.src_path):
            print(f"New file detected: {event.src_path}. Restarting...")
            self.debounced_restart()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python autostart.py <script_to_run.py>")
        sys.exit(1)
    
    script_to_run = sys.argv[1]
    
    if not os.path.exists(script_to_run):
        print(f"Error: Script '{script_to_run}' not found!")
        sys.exit(1)
    
    event_handler = RestartHandler(script_to_run)
    observer = Observer()
    
    # FIXED: Only watch current directory, not recursive to avoid watching everything
    observer.schedule(event_handler, path=".", recursive=False)
    
    # Watch specific subdirectories that contain code
    for subdir in ['commands', 'search', 'player']:
        if os.path.exists(subdir):
            observer.schedule(event_handler, path=subdir, recursive=True)
    
    observer.start()
    
    print(f"Watching for changes... (Press Ctrl+C to stop)")
    
    try:
        observer.join()
    except KeyboardInterrupt:
        print("\nStopping observer...")
        observer.stop()
        if event_handler.process:
            event_handler.process.terminate()
            try:
                event_handler.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                event_handler.process.kill()
    
    observer.join()
    print("Autostart stopped.")
