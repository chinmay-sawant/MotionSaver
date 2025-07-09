"""
Enhanced Key Blocker (Python-only): Robust key blocking and Ctrl+Alt+Del detection.
Uses only Python keyboard hooks and monitoring.
"""

import time
import threading
import subprocess
import sys
import os
import psutil
import winreg
from datetime import datetime, timedelta
from utils.key_blocker import KeyBlocker
import inspect

# Initialize central logging
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('EnhancedKeyBlocker')

class EnhancedKeyBlocker:
    """
    Enhanced key blocker (Python-only): uses Python hooks for key blocking and Ctrl+Alt+Del detection.
    """
    def __init__(self, debug_print=True):
        logger.info("__init__")
        self.debug_print = debug_print
        self.python_blocker = None
        self.monitoring_thread = None
        self.stop_monitoring = False
        self.ctrl_alt_del_monitor_thread = None
        self.last_active_time = datetime.now()
        self.restart_pending = False    
        self._print_debug("EnhancedKeyBlocker initialized")

    def _print_debug(self, message):
        logger.info("_print_debug")
        if self.debug_print:
            try:
                # Get the name of the calling function for detailed logging
                caller_frame = inspect.currentframe().f_back
                caller_name = caller_frame.f_code.co_name
                logger.debug(f"{caller_name} - {message}")
            except Exception:
                logger.debug(message) # Fallback

    def start_blocking(self):
        """Start Python key blocking."""
        logger.info("start_blocking")
        success_python = False
        try:
            self.python_blocker = KeyBlocker(debug_print=self.debug_print)
            success_python = self.python_blocker.enable_all_blocking()
            if success_python:
                self._print_debug("Python key blocking enabled")
            else:
                self._print_debug("Python key blocking failed")
        except Exception as e:
            self._print_debug(f"Failed to start Python blocking: {e}")
            log_exception(e)

        self.start_monitoring()
        self.start_ctrl_alt_del_monitoring()
        return success_python

    def stop_blocking(self):
        """Stop all key blocking."""
        logger.info("stop_blocking")
        self._print_debug("Stopping all key blocking...")
        self.stop_monitoring = True

        # Stop monitoring threads
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self._print_debug("Joining monitoring_thread...")
            self.monitoring_thread.join(timeout=2)

        if self.ctrl_alt_del_monitor_thread and self.ctrl_alt_del_monitor_thread.is_alive():
            self._print_debug("Joining ctrl_alt_del_monitor_thread...")
            self.ctrl_alt_del_monitor_thread.join(timeout=2)

        # Stop Python blocking
        if self.python_blocker:
            try:
                self.python_blocker.disable_all_blocking()
                self._print_debug("Python key blocking disabled")
            except Exception as e:
                self._print_debug(f"Error stopping Python blocking: {e}")
                log_exception(e)
    
    def start_monitoring(self):
        """Start a monitoring thread to check and restart Python hooks if needed."""
        logger.info("start_monitoring")
        self.stop_monitoring = False
        self.monitoring_thread = threading.Thread(target=self._monitor_hooks, daemon=True)
        self.monitoring_thread.start()
        self._print_debug("Hook monitoring started")

    def _monitor_hooks(self):
        """Monitor Python hook status and restart if necessary."""
        logger.info("_monitor_hooks")
        check_count = 0
        while not self.stop_monitoring:
            try:
                check_count += 1
                if check_count % 60 == 0: # Log every 30 seconds
                    self._print_debug(f"Hook monitoring active - check #{check_count}")

                # Check Python hook status (if it has a way to check)
                disable_auto_hook_restart = False
                try:
                    from utils.key_blocker import KeyBlocker
                    disable_auto_hook_restart = getattr(KeyBlocker, '_block_action_flags', {}).get('disable_auto_hook_restart', False)
                except Exception as e:
                    self._print_debug(f"Failed to get the disable_auto_hook_restart attribute : {e}")
                if self.python_blocker and hasattr(self.python_blocker, 'hooks_active') and not self.python_blocker.hooks_active:
                    if not disable_auto_hook_restart:
                        self._print_debug("Python hooks lost, attempting to restart...")
                        try:
                            if hasattr(self.python_blocker, 'start_hook_blocking'):
                                self.python_blocker.start_hook_blocking()
                            else:
                                self.python_blocker.enable_all_blocking()
                            self._print_debug("Python hooks restarted successfully")
                        except Exception as e:
                            self._print_debug(f"Failed to restart Python hooks: {e}")
                            log_exception(e)
                    else:
                        self._print_debug("Python hooks lost, but auto-restart is disabled due to Ctrl+Alt+Del event.")

                time.sleep(0.5)
            except Exception as e:
                self._print_debug(f"Error in monitoring thread: {e}")
                log_exception(e)
                time.sleep(2)
    
    def is_blocking_active(self):
        """Check if Python blocking is active."""
        logger.info("is_blocking_active")
        python_active = self.python_blocker and self.python_blocker.hooks_active
        full_blocking_active = self.python_blocker and getattr(self.python_blocker, 'full_blocking_active', False)
        self._print_debug(f"Blocking active status: hooks={python_active}, full_blocking={full_blocking_active}")
        return python_active and full_blocking_active

    def get_status(self):
        """Get detailed status of Python blocking."""
        logger.info("get_status")
        status = {
            'python_hooks_active': False,
            'python_registry_active': False,
            'python_full_blocking_active': False,
            'monitoring_active': False
        }

        if self.python_blocker:
            status['python_hooks_active'] = self.python_blocker.hooks_active
            status['python_registry_active'] = self.python_blocker.registry_disabled
            status['python_full_blocking_active'] = getattr(self.python_blocker, 'full_blocking_active', False)

        if self.monitoring_thread:
            status['monitoring_active'] = self.monitoring_thread.is_alive()
        
        self._print_debug(f"Current status: {status}")
        return status
    
    def start_ctrl_alt_del_monitoring(self):
        """Start monitoring for Ctrl+Alt+Del events and system state changes."""
        logger.info("start_ctrl_alt_del_monitoring")
        self.ctrl_alt_del_monitor_thread = threading.Thread(target=self._monitor_ctrl_alt_del, daemon=True)
        self.ctrl_alt_del_monitor_thread.start()
        self._print_debug("Ctrl+Alt+Del monitoring started")

    def _monitor_ctrl_alt_del(self):
        """Monitor for Ctrl+Alt+Del interruptions and system state changes (Python-only)."""
        logger.info("_monitor_ctrl_alt_del")
        self._print_debug("Starting Ctrl+Alt+Del detection monitoring...")

        check_count = 0
        last_winlogon_check = datetime.now()
        last_process_check = datetime.now()

        while not self.stop_monitoring:
            try:
                check_count += 1
                current_time = datetime.now()

                if check_count % 60 == 0: # Log every 30 seconds
                    self._print_debug(f"Ctrl+Alt+Del monitoring active - check #{check_count}")

                # Method 1: Check for winlogon.exe activity (every 5 seconds)
                if (current_time - last_winlogon_check).total_seconds() >= 5:
                    self._check_winlogon_activity()
                    last_winlogon_check = current_time

                # Method 2: Check for secure desktop processes (every 10 seconds)
                if (current_time - last_process_check).total_seconds() >= 10:
                    if self._check_secure_desktop_processes():
                        self._print_debug("Secure desktop activity detected - scheduling restart")
                        self._schedule_restart_after_delay()
                    last_process_check = current_time

                time.sleep(0.5)
            except Exception as e:
                self._print_debug(f"Error in Ctrl+Alt+Del monitoring: {e}")
                log_exception(e)
                time.sleep(2)
    
    def _check_winlogon_activity(self):
        """Check for winlogon.exe activity which might indicate Ctrl+Alt+Del."""
        logger.info("_check_winlogon_activity")
        try:
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                if proc.info['name'] and 'winlogon' in proc.info['name'].lower():
                    cpu_usage = proc.cpu_percent(interval=0.1)
                    if cpu_usage > 5:  # Winlogon using significant CPU
                        self._print_debug(f"Winlogon activity detected: {cpu_usage}% CPU")
                        return True
        except Exception as e:
            self._print_debug(f"Error checking winlogon activity: {e}")
            log_exception(e)
        return False
    
    def _check_secure_desktop_processes(self):
        """Check for processes that indicate secure desktop mode."""
        logger.info("_check_secure_desktop_processes")
        secure_desktop_indicators = [
            'logonui.exe',      # Windows login UI
            'lsass.exe',        # Local Security Authority (high activity)
            'dwm.exe',          # Desktop Window Manager (high activity)
            'csrss.exe'         # Client Server Runtime (high activity)
        ]
        
        try:
            high_activity_count = 0
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() in secure_desktop_indicators:
                    cpu_usage = proc.cpu_percent(interval=0.1)
                    if cpu_usage > 10:  # High CPU usage
                        high_activity_count += 1
                        self._print_debug(f"Secure desktop process active: {proc_name} ({cpu_usage}% CPU)")
            
            # If multiple secure desktop processes are highly active
            if high_activity_count >= 2:
                self._print_debug(f"Multiple secure desktop processes active ({high_activity_count})")
                return True
                
        except Exception as e:
            self._print_debug(f"Error checking secure desktop processes: {e}")
            log_exception(e)
        
        return False
    
    def _schedule_restart_after_delay(self):
        """Schedule application restart after a delay to allow user to finish."""
        logger.info("_schedule_restart_after_delay")
        if self.restart_pending:
            return  # Restart already scheduled

        self.restart_pending = True
        self._print_debug("Scheduling application restart in 5 seconds...")

        # Start restart timer in a separate thread
        restart_thread = threading.Thread(target=self._restart_application_after_delay, daemon=True)
        restart_thread.start()

    def _restart_application_after_delay(self):
        """Wait for delay then restart the application."""
        logger.info("_restart_application_after_delay")
        try:
            # Wait 5 seconds for user to finish with secure desktop
            self._print_debug("Waiting 5 seconds before application restart...")
            time.sleep(5)
            self._print_debug("Restarting application after delay...")
            self._restart_application()
        except Exception as e:
            self._print_debug(f"Error in restart delay thread: {e}")
            log_exception(e)
            self.restart_pending = False

    def _restart_application(self):
        """Restart the current application with the same arguments."""
        logger.info("_restart_application")
        try:
            self._print_debug("Restarting application to restore hooks after Ctrl+Alt+Del...")

            # Get current script path and arguments
            script_path = sys.argv[0]
            script_args = sys.argv[1:]

            # Build the restart command
            if script_path.endswith('.py'):
                restart_cmd = [sys.executable, script_path] + script_args
            else:
                restart_cmd = [script_path] + script_args

            self._print_debug(f"Restart command: {' '.join(restart_cmd)}")

            subprocess.Popen(restart_cmd, 
                           cwd=os.getcwd(),
                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)

            self._print_debug("New application instance started, exiting current process in 2 seconds.")

            threading.Timer(2.0, lambda: os._exit(0)).start()

        except Exception as e:
            self._print_debug(f"Error restarting application: {e}")
            log_exception(e)
            self.restart_pending = False
    
    def __enter__(self):
        """Context manager entry."""
        logger.info("__enter__")
        self.start_blocking()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        logger.info("__exit__")
        self._print_debug(f"Exiting context manager. Type: {exc_type}, Val: {exc_val}")
        self.stop_blocking()


def test_enhanced_blocker():    
    """Test the enhanced key blocker (Python-only)."""
    logger.info("test_enhanced_blocker")
    logger.info("Enhanced Key Blocker Test (Python-only)")
    logger.info("=" * 30)
    logger.info("This will block key combinations using Python hooks only.")
    logger.info("FIRST: Press Win+S to activate full blocking mode.")
    logger.info("Then: Press Ctrl+C to stop.")
    logger.info("")

    blocker_instance = None
    try:
        blocker_instance = EnhancedKeyBlocker(debug_print=True)
        with blocker_instance as blocker:
            if not blocker.python_blocker or not blocker.python_blocker.hooks_active:
                logger.warning("Warning: Hook system not active!")
                logger.warning("Make sure you're running as administrator.")
                return

            logger.info("Enhanced blocker is ready in trigger mode!")

            # Show status
            status = blocker.get_status()
            logger.info(f"Status: {status}")
            logger.info("")
            logger.info("Press Win+S to activate full blocking mode.")
            logger.info("Once activated, these keys will be blocked:")
            logger.info("- Win+Tab")
            logger.info("- Alt+Tab")
            logger.info("- Shift+Alt+Tab")
            logger.info("- Ctrl+Alt+Del (Python hooks may not survive this)")
            logger.info("")

            # Keep running
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nStopping enhanced blocker...")
    except Exception as e:
        logger.error(f"Error: {e}")
        log_exception(e)
    finally:
        if blocker_instance:
            logger.info("Ensuring blocker is stopped in finally block.")
            blocker_instance.stop_blocking()


if __name__ == "__main__":
    log_startup()
    test_enhanced_blocker()
    log_shutdown()
