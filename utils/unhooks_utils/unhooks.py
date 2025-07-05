"""
MotionSaver Unhooks Utility
Removes all hooks, blockers, and registry modifications made by MotionSaver.
This script should be run as Administrator to fully clean up registry entries.
"""

import os
import sys
import platform
import subprocess
import time
import threading

# Initialize central logging
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('Unhooks')

# Windows-specific imports
WINDOWS_SUPPORT = False
if platform.system() == "Windows":
    try:
        import winreg
        import win32serviceutil
        import win32service
        import ctypes
        WINDOWS_SUPPORT = True
    except ImportError:
        logger.warning("Windows-specific libraries not available. Some features will be limited.")

# Keyboard hook support
KEYBOARD_SUPPORT = False
try:
    import keyboard
    KEYBOARD_SUPPORT = True
except ImportError:
    logger.warning("'keyboard' library not available. Hook removal will be limited.")

# Process monitoring support
PSUTIL_SUPPORT = False
try:
    import psutil
    PSUTIL_SUPPORT = True
except ImportError:
    logger.warning("'psutil' library not available. Process monitoring features disabled.")

class MotionSaverUnhooks:
    """
    Comprehensive cleanup utility for MotionSaver hooks and modifications.
    """
    
    def __init__(self, debug_print=True):
        self.debug_print = debug_print
        self.cleanup_count = 0
        self.errors = []
    
    def _print_debug(self, message):
        """Print debug message if debug mode is enabled."""
        if self.debug_print:
            print(f"[Unhooks] {message}")
            logger.info(message)
    
    def _print_error(self, message):
        """Print and log error message."""
        print(f"[ERROR] {message}")
        logger.error(message)
        self.errors.append(message)
    
    def is_admin(self):
        """Check if running with administrator privileges."""
        if not WINDOWS_SUPPORT:
            return False
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def unhook_keyboard_hooks(self):
        """Remove all keyboard hooks from the 'keyboard' library."""
        self._print_debug("Removing keyboard library hooks...")
        
        if not KEYBOARD_SUPPORT:
            self._print_error("Keyboard library not available")
            return False
        
        try:
            # Unhook all hotkeys registered by keyboard library
            keyboard.unhook_all()
            self._print_debug("All keyboard hooks removed successfully")
            self.cleanup_count += 1
            return True
        except Exception as e:
            self._print_error(f"Failed to remove keyboard hooks: {e}")
            return False
    
    def restore_task_manager_registry(self):
        """Re-enable Task Manager via registry."""
        if not WINDOWS_SUPPORT:
            self._print_error("Windows registry support not available")
            return False
        
        self._print_debug("Restoring Task Manager registry settings...")
        success = False
        
        try:
            # Remove DisableTaskMgr from Current User
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(key, "DisableTaskMgr")
                    self._print_debug("Removed DisableTaskMgr from HKEY_CURRENT_USER")
                    success = True
                except FileNotFoundError:
                    self._print_debug("DisableTaskMgr not found in HKEY_CURRENT_USER (already clean)")
                winreg.CloseKey(key)
            except FileNotFoundError:
                self._print_debug("Task Manager policies key not found in HKEY_CURRENT_USER")
            
            # Alternative: Set to 0 instead of deleting
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
                winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(key)
                self._print_debug("Set DisableTaskMgr to 0 (enabled)")
                success = True
            except Exception as e:
                self._print_debug(f"Could not set DisableTaskMgr to 0: {e}")
            
            if success:
                self.cleanup_count += 1
            
        except Exception as e:
            self._print_error(f"Failed to restore Task Manager: {e}")
        
        return success
    
    def restore_windows_hotkeys_registry(self):
        """Re-enable Windows hotkeys via registry."""
        if not WINDOWS_SUPPORT:
            self._print_error("Windows registry support not available")
            return False
        
        self._print_debug("Restoring Windows hotkeys registry settings...")
        success_count = 0
        
        # Registry keys and values to clean up
        registry_locations = [
            {
                'hive': winreg.HKEY_LOCAL_MACHINE,
                'path': r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer",
                'values': ["NoRun", "NoWinKeys", "AltTabSettings"]
            },
            {
                'hive': winreg.HKEY_CURRENT_USER,
                'path': r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", 
                'values': ["NoRun", "NoWinKeys", "AltTabSettings"]
            },
            {
                'hive': winreg.HKEY_LOCAL_MACHINE,
                'path': r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
                'values': ["DisableWebSearch", "AllowSearchToUseLocation"]
            },
            {
                'hive': winreg.HKEY_CURRENT_USER,
                'path': r"Software\Microsoft\Windows\CurrentVersion\Search",
                'values': [("SearchboxTaskbarMode", 1), ("BingSearchEnabled", 1)]  # Restore to enabled
            }
        ]
        
        for location in registry_locations:
            try:
                # Try to open the key
                try:
                    key = winreg.OpenKey(location['hive'], location['path'], 0, winreg.KEY_SET_VALUE)
                except FileNotFoundError:
                    self._print_debug(f"Registry key not found: {location['path']} (already clean)")
                    continue
                
                for value_info in location['values']:
                    try:
                        if isinstance(value_info, tuple):
                            # Restore specific value
                            value_name, restore_value = value_info
                            winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, restore_value)
                            self._print_debug(f"Restored {value_name} to {restore_value}")
                        else:
                            # Delete the value
                            value_name = value_info
                            winreg.DeleteValue(key, value_name)
                            self._print_debug(f"Deleted registry value: {value_name}")
                        success_count += 1
                    except FileNotFoundError:
                        self._print_debug(f"Registry value {value_info} not found (already clean)")
                    except Exception as e:
                        self._print_debug(f"Could not process registry value {value_info}: {e}")
                
                winreg.CloseKey(key)
                
            except Exception as e:
                self._print_error(f"Error processing registry location {location['path']}: {e}")
        
        if success_count > 0:
            self.cleanup_count += 1
            self._print_debug(f"Restored {success_count} registry values")
            
            # Trigger group policy update
            try:
                subprocess.Popen(['gpupdate', '/force'], 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                self._print_debug("Group policy update initiated")
            except Exception as e:
                self._print_debug(f"Could not update group policy: {e}")
        
        return success_count > 0
    
    def stop_motionsaver_processes(self):
        """Stop all running MotionSaver processes."""
        if not PSUTIL_SUPPORT:
            self._print_debug("Process monitoring not available, skipping process cleanup")
            return False
        
        self._print_debug("Stopping MotionSaver processes...")
        stopped_count = 0
        
        # Process names to look for
        process_names = [
            'PhotoEngine.py',
            'PhotoEngine.exe', 
            'gui.py',
            'enhanced_key_blocker.py',
            'blockit.py',
            'python.exe'  # Check if running MotionSaver scripts
        ]
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    if not proc_info['name']:
                        continue
                    
                    # Check if process name matches
                    if proc_info['name'].lower() in [name.lower() for name in process_names]:
                        # For python.exe, check if it's running MotionSaver scripts
                        if proc_info['name'].lower() == 'python.exe':
                            cmdline = proc_info.get('cmdline', [])
                            if not any('PhotoEngine' in str(arg) or 'MotionSaver' in str(arg) 
                                     or 'screensaver' in str(arg).lower() for arg in cmdline):
                                continue
                        
                        self._print_debug(f"Terminating process: {proc_info['name']} (PID: {proc_info['pid']})")
                        
                        # Try graceful termination first
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            # Force kill if still running
                            proc.kill()
                            proc.wait(timeout=1)
                        
                        stopped_count += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    self._print_debug(f"Error stopping process {proc_info.get('name', 'unknown')}: {e}")
        
        except Exception as e:
            self._print_error(f"Error during process cleanup: {e}")
            return False
        
        if stopped_count > 0:
            self._print_debug(f"Stopped {stopped_count} MotionSaver processes")
            self.cleanup_count += 1
        else:
            self._print_debug("No MotionSaver processes found running")
        
        return True
    
    def stop_motionsaver_service(self):
        """Stop and remove MotionSaver Windows service if it exists."""
        if not WINDOWS_SUPPORT:
            self._print_debug("Windows service support not available")
            return False
        
        self._print_debug("Checking for MotionSaver Windows services...")
        
        service_names = [
            "PhotoEngineService",
            "ScreenSaverService", 
            "MotionSaverService"
        ]
        
        stopped_services = 0
        
        for service_name in service_names:
            try:
                # Check if service exists
                status = win32serviceutil.QueryServiceStatus(service_name)[1]
                self._print_debug(f"Found service: {service_name}")
                
                # Stop service if running
                if status == win32service.SERVICE_RUNNING:
                    self._print_debug(f"Stopping service: {service_name}")
                    win32serviceutil.StopService(service_name)
                    time.sleep(2)  # Wait for service to stop
                
                # Remove service
                self._print_debug(f"Removing service: {service_name}")
                win32serviceutil.RemoveService(service_name)
                stopped_services += 1
                
            except Exception as e:
                # Service probably doesn't exist
                self._print_debug(f"Service {service_name} not found or already removed: {e}")
        
        if stopped_services > 0:
            self._print_debug(f"Removed {stopped_services} MotionSaver services")
            self.cleanup_count += 1
        
        return True
    
    def remove_startup_entries(self):
        """Remove any MotionSaver startup entries from registry."""
        if not WINDOWS_SUPPORT:
            self._print_debug("Windows registry support not available")
            return False
        
        self._print_debug("Removing startup entries...")
        removed_count = 0
        
        startup_locations = [
            winreg.HKEY_CURRENT_USER,
            winreg.HKEY_LOCAL_MACHINE
        ]
        
        startup_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        startup_names = ["MotionSaver", "PhotoEngine", "ScreenSaver"]
        
        for hive in startup_locations:
            try:
                key = winreg.OpenKey(hive, startup_path, 0, winreg.KEY_SET_VALUE)
                
                for startup_name in startup_names:
                    try:
                        winreg.DeleteValue(key, startup_name)
                        self._print_debug(f"Removed startup entry: {startup_name}")
                        removed_count += 1
                    except FileNotFoundError:
                        pass  # Entry doesn't exist
                
                winreg.CloseKey(key)
                
            except Exception as e:
                self._print_debug(f"Could not access startup registry: {e}")
        
        if removed_count > 0:
            self.cleanup_count += 1
        
        return True

    def run_complete_cleanup(self):
        """Run all cleanup operations."""
        self._print_debug("Starting complete MotionSaver cleanup...")
        
        if not self.is_admin():
            print("WARNING: Not running as Administrator!")
            print("Some cleanup operations may fail without admin privileges.")
            print("For complete cleanup, please run this script as Administrator.")
            print()
        
        # Stop processes first
        self.stop_motionsaver_processes()
        
        # Stop services
        self.stop_motionsaver_service()
        
        # Remove keyboard hooks
        self.unhook_keyboard_hooks()
        
        # Restore registry settings
        self.restore_task_manager_registry()
        self.restore_windows_hotkeys_registry()
        
        # Remove startup entries
        self.remove_startup_entries()
        
        # Summary
        print()
        print("=" * 50)
        print("CLEANUP SUMMARY")
        print("=" * 50)
        print(f"Total cleanup operations completed: {self.cleanup_count}")
        
        if self.errors:
            print(f"Errors encountered: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("No errors encountered.")
        
        print()
        print("MotionSaver cleanup completed!")
        print("You may need to restart your computer for all changes to take effect.")
        
        return self.cleanup_count > 0

def main():
    """Main function for the unhooks utility."""
    print("MotionSaver Unhooks Utility")
    print("=" * 40)
    print("This utility will remove all hooks, blockers, and modifications")
    print("made by MotionSaver, restoring your system to its original state.")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        # Automatic mode
        unhooks = MotionSaverUnhooks(debug_print=True)
        unhooks.run_complete_cleanup()
    else:
        # Interactive mode
        response = input("Do you want to proceed with the cleanup? (y/N): ")
        if response.lower() in ['y', 'yes']:
            unhooks = MotionSaverUnhooks(debug_print=True)
            unhooks.run_complete_cleanup()
        else:
            print("Cleanup cancelled.")

if __name__ == "__main__":
    main()
