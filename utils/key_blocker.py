"""
Key blocking utility for the ScreenSaver application.
Provides both registry-based and hook-based key blocking methods.
"""
import platform
import json
import os

# Initialize central logging
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('KeyBlocker')

# Registry-based blocking (Windows only)
if platform.system() == "Windows":
    try:
        import winreg
        import subprocess
        WINDOWS_REGISTRY_SUPPORT = True
    except ImportError:
        WINDOWS_REGISTRY_SUPPORT = False
else:
    WINDOWS_REGISTRY_SUPPORT = False

# Hook-based blocking using keyboard library
try:
    import keyboard
    KEYBOARD_HOOK_SUPPORT = True
except ImportError:    
    KEYBOARD_HOOK_SUPPORT = False
    logger.warning("'keyboard' library not installed. Install with: pip install keyboard")

class KeyBlocker:
    # Class-level dictionary to track special block states
    _block_action_flags = {}
    """
    Manages key blocking using multiple methods for maximum effectiveness.
    """
    
    def __init__(self, debug_print=True):
        self.debug_print = debug_print
        self.registry_disabled = False
        self.hooks_active = False
        self.blocked_combinations = {
            'alt+tab': "Alt+Tab",
            'shift+alt+tab': "Shift+Alt+Tab",
            'win+tab': "Win+Tab",
            'win': "Windows Key (Standalone)",
            'win+r': "Win+R (Run)",
            'win+x': "Win+X (Quick Menu)",
            'win+s': "Win+S (Search)",
            'alt+f4': "Alt+F4",
            'ctrl+shift+esc': "Ctrl+Shift+Esc (Task Manager)",
            'ctrl+alt+del': "Ctrl+Alt+Del (Security Screen)",
            'altgr+tab': "AltGr+Tab",
            'ctrl+esc': "Ctrl+Esc (Start Menu)",
            'ctrl+alt+esc': "Ctrl+Alt+Esc (Task Manager)",
            'altgr': "AltGr (Right Alt Standalone)"
        }
    def _print_debug(self, message):
        """Print debug message if debug mode is enabled."""
        if self.debug_print:
            logger.debug(f"{message}")
    def _on_block_action(self, combo_name):
        """Action to perform when a key combination is blocked."""
        self._print_debug(f"Blocked: {combo_name}")
        # Block Alt keys using pynput if Alt_L or Alt_R is detected
        try:
            from pynput.keyboard import Controller, Key
            keyboard_controller = Controller()
            if combo_name.lower() in ["alt", "alt_l", "alt key (left)"]:
                self._print_debug("Blocking Alt_L (left alt) using pynput.")
                keyboard_controller.release(Key.alt_l)
            elif combo_name.lower() in ["alt_r", "alt key (right)"]:
                self._print_debug("Blocking Alt_R (right alt) using pynput.")
                keyboard_controller.release(Key.alt_r)
        except Exception as e:
            self._print_debug(f"pynput Alt block failed: {e}")

        # Detect Ctrl+Alt+Del and call LockWorkStation
        if combo_name.lower() in ["ctrl+alt+del", "ctrl+alt+del (security screen)"]:
            self._print_debug("Ctrl+Alt+Del detected! Locking workstation...")
            logger.info("Ctrl+Alt+Del detected! Locking workstation...")
            # Set a flag to indicate hooks should NOT be auto-reenabled
            KeyBlocker._block_action_flags['disable_auto_hook_restart'] = True
            try:
                import ctypes
                # Removes any blocking hooks before locking
                self.stop_hook_blocking()
                ctypes.windll.user32.LockWorkStation()
                self._print_debug("LockWorkStation() executed from Python.")
            except Exception as e:
                self._print_debug(f"LockWorkStation() failed: {e}")
        return True
    
    def disable_task_manager_registry(self):
        """Disable Task Manager via registry (requires admin privileges)."""
        if not WINDOWS_REGISTRY_SUPPORT:
            return False
            
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            self._print_debug("Task Manager disabled via registry")
            return True
        except Exception as e:
            self._print_debug(f"Failed to disable Task Manager: {e}")
            return False
    
    def enable_task_manager_registry(self):
        """Re-enable Task Manager via registry."""
        if not WINDOWS_REGISTRY_SUPPORT:
            return False
            
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\System")
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            self._print_debug("Task Manager re-enabled via registry")
            return True
        except Exception as e:
            self._print_debug(f"Failed to re-enable Task Manager: {e}")
            return False
    
    def disable_windows_hotkeys_registry(self):
        """Disable various Windows hotkeys via registry (requires admin privileges)."""
        if not WINDOWS_REGISTRY_SUPPORT:
            return False
            
        disabled_count = 0
        try:
            # Local Machine policies
            key_explorer_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            winreg.SetValueEx(key_explorer_lm, "NoRun", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_lm, "NoWinKeys", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_lm, "AltTabSettings", 0, winreg.REG_DWORD, 1)
            disabled_count += 3
            winreg.CloseKey(key_explorer_lm)
            
            # Current User policies
            key_explorer_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            winreg.SetValueEx(key_explorer_cu, "NoRun", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_cu, "NoWinKeys", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key_explorer_cu, "AltTabSettings", 0, winreg.REG_DWORD, 1)
            disabled_count += 3
            winreg.CloseKey(key_explorer_cu)
            
            # Disable Windows Search
            try:
                search_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Policies\Microsoft\Windows\Windows Search")
                winreg.SetValueEx(search_key_lm, "DisableWebSearch", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(search_key_lm, "AllowSearchToUseLocation", 0, winreg.REG_DWORD, 0)
                winreg.CloseKey(search_key_lm)
                disabled_count += 2
            except Exception as e:
                self._print_debug(f"Warning: Could not disable web search: {e}")
            
            # Hide search box
            search_key_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                         r"Software\Microsoft\Windows\CurrentVersion\Search")
            winreg.SetValueEx(search_key_cu, "SearchboxTaskbarMode", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(search_key_cu, "BingSearchEnabled", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(search_key_cu)
            disabled_count += 2
            
            self._print_debug(f"Windows hotkeys disabled via registry ({disabled_count} entries)")
            
            # Non-blocking group policy update
            try:
                subprocess.Popen(['gpupdate', '/force'], 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                self._print_debug("Group policy update initiated")
            except Exception as e:
                self._print_debug(f"Could not initiate group policy update: {e}")
            
            return True
            
        except Exception as e:
            self._print_debug(f"Failed to disable Windows hotkeys: {e}")
            return False
    
    def enable_windows_hotkeys_registry(self):
        """Re-enable Windows hotkeys via registry."""
        if not WINDOWS_REGISTRY_SUPPORT:
            return False
            
        enabled_count = 0
        try:
            # Local Machine policies
            key_explorer_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            for value in ["NoRun", "NoWinKeys", "AltTabSettings"]:
                try:
                    winreg.DeleteValue(key_explorer_lm, value)
                    enabled_count += 1
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key_explorer_lm)
            
            # Current User policies
            key_explorer_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer")
            
            for value in ["NoRun", "NoWinKeys", "AltTabSettings"]:
                try:
                    winreg.DeleteValue(key_explorer_cu, value)
                    enabled_count += 1
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key_explorer_cu)
            
            # Re-enable Windows Search
            try:
                search_key_lm = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                             r"SOFTWARE\Policies\Microsoft\Windows\Windows Search")
                for value in ["DisableWebSearch", "AllowSearchToUseLocation"]:
                    try:
                        winreg.DeleteValue(search_key_lm, value)
                        enabled_count += 1
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(search_key_lm)
            except Exception as e:
                self._print_debug(f"Warning: Could not re-enable web search: {e}")
            
            # Restore search box visibility
            search_key_cu = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                         r"Software\Microsoft\Windows\CurrentVersion\Search")
            winreg.SetValueEx(search_key_cu, "SearchboxTaskbarMode", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(search_key_cu, "BingSearchEnabled", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(search_key_cu)
            enabled_count += 2
            
            self._print_debug(f"Windows hotkeys re-enabled via registry ({enabled_count} entries)")
            
            # Non-blocking group policy update
            try:
                subprocess.Popen(['gpupdate', '/force'],
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                self._print_debug("Group policy restore initiated")
            except Exception as e:
                self._print_debug(f"Could not initiate group policy update: {e}")
            
            return True
            
        except Exception as e:
            self._print_debug(f"Failed to re-enable Windows hotkeys: {e}")
            return False
    
    def start_hook_blocking(self):
        """Start hook-based key blocking using keyboard library."""
        if not KEYBOARD_HOOK_SUPPORT:
            self._print_debug("Keyboard library not available for hook blocking")
            return False
        
        try:
            self._print_debug("Starting hook-based key blocking...")
            
            # Register hotkeys with suppression
            for combo, name in self.blocked_combinations.items():
                try:
                    keyboard.add_hotkey(combo, lambda n=name: self._on_block_action(n), suppress=True)
                    self._print_debug(f"Registered hook for: {name} ({combo})")
                except Exception as e:
                    self._print_debug(f"Failed to register hook for {name}: {e}")
            
            self.hooks_active = True
            self._print_debug("Hook-based key blocking activated")
            return True
            
        except Exception as e:
            self._print_debug(f"Failed to start hook blocking: {e}")
            return False
    
    def stop_hook_blocking(self):
        """Stop hook-based key blocking."""
        if not KEYBOARD_HOOK_SUPPORT or not self.hooks_active:
            return
        
        try:
            keyboard.unhook_all_hotkeys()
            self.hooks_active = False
            self._print_debug("Hook-based key blocking stopped")
        except Exception as e:
            self._print_debug(f"Error stopping hook blocking: {e}")
    
    def enable_all_blocking(self, use_registry=True, use_hooks=True):
        """Enable all available blocking methods."""
        success_registry = True
        success_hooks = True
        
        if use_registry and WINDOWS_REGISTRY_SUPPORT:
            task_mgr_disabled = self.disable_task_manager_registry()
            hotkeys_disabled = self.disable_windows_hotkeys_registry()
            success_registry = task_mgr_disabled and hotkeys_disabled
            self.registry_disabled = success_registry
        
        if use_hooks and KEYBOARD_HOOK_SUPPORT:
            success_hooks = self.start_hook_blocking()
        
        return success_registry and success_hooks
    
    def disable_all_blocking(self):
        """Disable all blocking methods and restore normal behavior."""
        if self.registry_disabled and WINDOWS_REGISTRY_SUPPORT:
            self.enable_task_manager_registry()
            self.enable_windows_hotkeys_registry()
            self.registry_disabled = False
        
        if self.hooks_active:
            self.stop_hook_blocking()
        
        self._print_debug("All key blocking disabled")

# Standalone script functionality
def main():
    """Run as standalone key blocker script."""
    logger.info("ScreenSaver Key Blocker Utility")
    logger.info("================================")
    logger.info("This utility blocks system hotkeys for kiosk/screensaver applications.")
    logger.info("IMPORTANT: Run with administrator privileges for full functionality.")
    logger.info("Press Ctrl+C to stop blocking and exit.")
    logger.info("")
    
    blocker = KeyBlocker(debug_print=True)
    
    try:
        # Try to enable all blocking methods
        if blocker.enable_all_blocking():
            logger.info("Key blocking is now active.")
        else:
            logger.warning("Some blocking methods failed to activate. Check permissions.")
        
        if KEYBOARD_HOOK_SUPPORT:
            # Keep running to maintain hooks
            keyboard.wait()
        else:
            input("Press Enter to disable blocking and exit...")
    except KeyboardInterrupt:
        logger.info("\nCtrl+C detected. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        blocker.disable_all_blocking()
        logger.info("Key blocking disabled. Exiting.")

if __name__ == "__main__":
    main()
