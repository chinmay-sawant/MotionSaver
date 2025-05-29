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
import logging
import traceback

# Setup logging
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_debug.log")
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class ScreenSaverService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ScreenSaverService"
    _svc_display_name_ = "Custom Screen Saver Service"
    _svc_description_ = "Runs PhotoEngine in system tray mode for Win+S screensaver activation"
    
    # REMOVED _exe_name_ and _exe_args_ to use win32serviceutil defaults
    # This means this script (screensaver_service.py) will be run by the service,
    # and its SvcDoRun method will be called.

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.tray_process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        servicemanager.LogInfoMsg("Service stop requested")

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        logging.info("Service SvcDoRun called.")
        try:
            self.main()
            logging.info("Service main function completed.")
        except Exception as e:
            logging.error(f"Exception in SvcDoRun trying to call self.main(): {e}")
            logging.error(traceback.format_exc())
            self.SvcStop()

    def main(self):
        """Main service - runs PhotoEngine in tray mode directly"""
        logging.info("Service main function started.")
        try:
            # Import and run PhotoEngine's tray mode directly
            import sys
            import os
            
            logging.info("Service main: Imported sys and os.")
            # Add the current directory to Python path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logging.info(f"Service main: script_dir is {script_dir}")
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
                logging.info(f"Service main: Added {script_dir} to sys.path.")
            
            servicemanager.LogInfoMsg("Starting PhotoEngine tray mode directly")
            logging.info("Service main: Logged 'Starting PhotoEngine tray mode directly' to servicemanager.")
            
            # Import PhotoEngine and run tray mode
            logging.info("Service main: Attempting to import PhotoEngine.")
            import PhotoEngine
            logging.info("Service main: Successfully imported PhotoEngine.")
            
            # Set up command line arguments for tray mode
            sys.argv = ['PhotoEngine.py', '-min']
            logging.info(f"Service main: Set sys.argv to {sys.argv}")
            
            # Run PhotoEngine's main function
            logging.info("Service main: Attempting to run PhotoEngine.main().")
            PhotoEngine.main()
            logging.info("Service main: PhotoEngine.main() completed without raising an immediate exception.")
            
        except Exception as e:
            servicemanager.LogErrorMsg(f"Service main error: {e}")
            logging.error(f"Exception in service main: {e}")
            logging.error(traceback.format_exc())
            # Optionally, re-raise or handle to ensure service stops if PhotoEngine crashes
            raise

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ScreenSaverService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ScreenSaverService)
