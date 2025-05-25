import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import time
import threading
import subprocess
from screensaver_app.PasswordConfig import load_config

class ScreenSaverService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ScreenSaverService"
    _svc_display_name_ = "Custom Screen Saver Service"
    _svc_description_ = "Automatically starts screensaver after configured idle time"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.screensaver_process = None
        self.last_activity_time = time.time()
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        if self.screensaver_process:
            self.screensaver_process.terminate()

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        """Main service loop"""
        import win32gui
        import win32api
        
        while self.running:
            try:
                config = load_config()
                timer_minutes = config.get("screensaver_timer_minutes", 10)
                timer_seconds = timer_minutes * 60
                
                # Check for user activity
                current_time = time.time()
                
                # Get cursor position and check if it changed
                cursor_pos = win32gui.GetCursorPos()
                if hasattr(self, 'last_cursor_pos') and cursor_pos != self.last_cursor_pos:
                    self.last_activity_time = current_time
                self.last_cursor_pos = cursor_pos
                
                # Check if screensaver should start
                if (current_time - self.last_activity_time) >= timer_seconds:
                    if not self.screensaver_process or self.screensaver_process.poll() is not None:
                        self.start_screensaver()
                        self.last_activity_time = current_time  # Reset timer
                
                # Check every 5 seconds
                if win32event.WaitForSingleObject(self.hWaitStop, 5000) == win32event.WAIT_OBJECT_0:
                    break
                    
            except Exception as e:
                servicemanager.LogErrorMsg(f"Service error: {e}")
                time.sleep(10)

    def start_screensaver(self):
        """Start the screensaver process"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            photo_engine_path = os.path.join(script_dir, "PhotoEngine.py")
            
            self.screensaver_process = subprocess.Popen([
                sys.executable, photo_engine_path
            ], cwd=script_dir)
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Failed to start screensaver: {e}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ScreenSaverService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ScreenSaverService)
