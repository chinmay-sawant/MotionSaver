import tkinter as tk
from tkinter import ttk, filedialog
import pygame
import os
import threading
import time
import subprocess
import json
import re
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
import platform

class MediaWidget:
    def __init__(self, parent_root, transparent_key='#123456', screen_width=0, screen_height=0):
        self.parent_root = parent_root # This is the main root window
        self.transparent_key = transparent_key
        # ... (rest of the existing __init__ attributes like current_file etc. can be kept if local playback is ever re-added) ...
        
        # Optimized YouTube integration for better performance
        self.youtube_track_info = None
        self.youtube_check_interval = 15  # Increased to 15 seconds to reduce overhead
        
        # Initialize pygame mixer (still needed for potential future use or if other parts rely on it)
        pygame.mixer.init()

        # Create a Toplevel window for the widget
        self.window = tk.Toplevel(self.parent_root)
        self.window.overrideredirect(True)
        self.window.attributes('-transparentcolor', self.transparent_key)
        self.window.configure(bg=self.transparent_key)
        self.window.attributes('-topmost', True) # Keep it on top

        # Position the Toplevel window (example: bottom-left)
        widget_width = 300
        widget_height = 80 # Adjusted height for Toplevel (minimalist)
        
        if screen_width == 0: screen_width = self.parent_root.winfo_screenwidth()
        if screen_height == 0: screen_height = self.parent_root.winfo_screenheight()

        x_pos = 20 # For bottom-left
        y_pos = screen_height - widget_height - 20
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        
        self.create_widget_content() # Renamed from create_widget
        self.start_youtube_detection()
    
    def create_widget_content(self):
        """Create the media widget UI content within its Toplevel window"""
        # All widgets are now parented to self.window
        
        # YouTube section - simplified with better transparency and text alignment
        self.youtube_info_label = tk.Label(
            self.window, # Parent is self.window
            text="🎵 No YouTube video detected",
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 11, 'bold'),
            wraplength=280, # Adjust if needed for text fitting
            anchor='w',     # Align text to the West (left)
            justify=tk.LEFT # Justify multi-line text to the left
        )
        self.youtube_info_label.pack(fill=tk.X, pady=5, padx=5) # Added padx for some spacing
        
        # Control buttons - simplified layout with transparent background for the container
        self.control_frame = tk.Frame(self.window, bg=self.transparent_key) # Parent is self.window
        self.control_frame.pack(pady=5)
        
        # Button config - buttons themselves will have their own distinct background
        btn_config = {
            'bg': self.transparent_key, # Make button background transparent
            'fg': 'white',
            'font': ('Arial', 16), # Icons are usually larger
            'width': 2,
            'height': 1,
            'activebackground': '#333333', # Keep active background distinct
            'activeforeground': 'white',
            'relief': 'flat',
            'bd': 0,
            'highlightthickness': 0 # Ensure no extra border from button itself
        }
        
        self.prev_btn = tk.Button(
            self.control_frame,
            text="⏮",
            command=self.previous_track,
            **btn_config
        )
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.play_pause_btn = tk.Button(
            self.control_frame,
            text="⏸", 
            command=self.toggle_play_pause,
            **btn_config
        )
        self.play_pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = tk.Button(
            self.control_frame,
            text="⏭",
            command=self.next_track,
            **btn_config
        )
        self.next_btn.pack(side=tk.LEFT, padx=5)

    def send_media_key(self, key):
        """Send media key commands to control browser playback"""
        try:
            system = platform.system()
            
            if system == "Windows":
                # Use Windows API to send media keys
                import win32api
                import win32con
                
                # Media key codes for Windows
                media_keys = {
                    'play_pause': 0xB3,  # VK_MEDIA_PLAY_PAUSE
                    'next': 0xB0,        # VK_MEDIA_NEXT_TRACK  
                    'previous': 0xB1     # VK_MEDIA_PREV_TRACK
                }
                
                if key in media_keys:
                    # Send key down and key up events
                    win32api.keybd_event(media_keys[key], 0, 0, 0)  # Key down
                    win32api.keybd_event(media_keys[key], 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up
                    print(f"Sent media key: {key}")
                    return True
                    
            elif system == "Darwin":  # macOS
                # Use AppleScript to send media keys
                scripts = {
                    'play_pause': 'tell application "System Events" to key code 16',  # Play/Pause
                    'next': 'tell application "System Events" to key code 17',       # Next
                    'previous': 'tell application "System Events" to key code 18'   # Previous
                }
                
                if key in scripts:
                    subprocess.run(['osascript', '-e', scripts[key]], capture_output=True)
                    print(f"Sent media key: {key}")
                    return True
                    
            elif system == "Linux":
                # Use playerctl for Linux
                commands = {
                    'play_pause': 'playerctl play-pause',
                    'next': 'playerctl next',
                    'previous': 'playerctl previous'
                }
                
                if key in commands:
                    subprocess.run(commands[key].split(), capture_output=True)
                    print(f"Sent media key: {key}")
                    return True
                    
        except Exception as e:
            print(f"Error sending media key {key}: {e}")
            return False
        
        return False

    def detect_youtube_playback(self):
        """Lightweight YouTube detection - optimized for performance"""
        try:
            system = platform.system()
            
            if system == "Windows":
                try:
                    # Use only the fastest method to reduce overhead
                    youtube_info = self._check_windows_media_session()
                    if youtube_info:
                        return youtube_info
                    
                    # Fallback to process check (lighter than PowerShell)
                    youtube_info = self._check_browser_processes_for_youtube_lightweight()
                    if youtube_info:
                        return youtube_info
                    
                except Exception as e:
                    print(f"Error in Windows YouTube detection: {e}")
            
            elif system == "Darwin":  # macOS
                try:
                    # Simplified macOS approach for better performance
                    script = '''
                    tell application "System Events"
                        if application "Google Chrome" is running then
                            tell application "Google Chrome"
                                repeat with w in windows
                                    set activeTab to active tab of w
                                    set tabURL to URL of activeTab
                                    set tabTitle to title of activeTab
                                    if tabURL contains "youtube.com/watch" and tabTitle contains " - YouTube" then
                                        return tabTitle
                                    end if
                                end repeat
                            end tell
                        end if
                    end tell
                    '''
                    
                    result = subprocess.run(['osascript', '-e', script], 
                                          capture_output=True, text=True, timeout=2)  # Reduced timeout
                    if result.stdout and " - YouTube" in result.stdout:
                        title = result.stdout.strip()
                        video_title = title.split(" - YouTube")[0].strip()
                        
                        if video_title and video_title != "YouTube":
                            return {"title": video_title, "source": "YouTube"}
                except subprocess.TimeoutExpired:
                    pass
                except Exception as e:
                    print(f"Error in macOS YouTube detection: {e}")
            
        except Exception as e:
            print(f"Error detecting YouTube playback: {e}")
        
        return None
    
    def _check_browser_processes_for_youtube_lightweight(self):
        """Lightweight browser process check - only check Chrome for performance"""
        try:
            import psutil
            # Only check Chrome for better performance
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
                        # Try to get window title via Windows API (faster than cmdline)
                        try:
                            import win32gui
                            import win32process
                            
                            def enum_windows_callback(hwnd, results):
                                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                                if pid == proc.info['pid']:
                                    window_title = win32gui.GetWindowText(hwnd)
                                    if window_title and "youtube" in window_title.lower() and " - " in window_title:
                                        video_title = window_title.split(" - ")[0].strip()
                                        if video_title and video_title != "YouTube":
                                            results.append({"title": video_title, "source": "YouTube"})
                                return True
                            
                            results = []
                            win32gui.EnumWindows(enum_windows_callback, results)
                            if results:
                                return results[0]
                        except ImportError:
                            pass  # win32gui not available
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error in lightweight browser check: {e}")
        return None
    
    def _check_windows_media_session(self):
        """Check Windows Media Session for currently playing media"""
        try:
            # Use Windows Runtime API to check media session
            powershell_cmd = '''
            Add-Type -AssemblyName System.Runtime.WindowsRuntime
            $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
            Function Await($WinRtTask, $ResultType) {
                $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
                $netTask = $asTask.Invoke($null, @($WinRtTask))
                $netTask.Wait(-1) | Out-Null
                $netTask.Result
            }
            
            [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime] | Out-Null
            $sessionManager = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
            $sessionManager = Await $sessionManager ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
            
            $sessions = $sessionManager.GetSessions()
            foreach ($session in $sessions) {
                $mediaProperties = $session.TryGetMediaPropertiesAsync()
                $mediaProperties = Await $mediaProperties ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
                
                if ($mediaProperties.Title -and $mediaProperties.Title -ne "") {
                    $appInfo = $session.SourceAppUserModelId
                    if ($appInfo -like "*chrome*" -or $appInfo -like "*firefox*" -or $appInfo -like "*edge*") {
                        Write-Output "$($mediaProperties.Title)|$($mediaProperties.Artist)|$appInfo"
                    }
                }
            }
            '''
            
            result = subprocess.run(['powershell', '-Command', powershell_cmd], 
                                  capture_output=True, text=True, timeout=3)
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            title = parts[0].strip()
                            artist = parts[1].strip()
                            app = parts[2].strip() if len(parts) > 2 else ""
                            
                            # Check if it's likely from YouTube
                            if title and (not artist or artist == title):
                                return {"title": title, "source": "YouTube"}
                                
        except Exception as e:
            print(f"Error checking Windows media session: {e}")
        return None
    
    def _extract_video_id_from_cmdline(self, cmdline_str):
        """Extract YouTube video ID from command line string"""
        try:
            import re
            # Look for YouTube video ID pattern
            match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})', cmdline_str)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"Error extracting video ID: {e}")
        return None
    
    def _get_youtube_title_by_id(self, video_id):
        """Get YouTube video title by video ID (basic method)"""
        try:
            # Simple method to get title without API key
            import urllib.request
            url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=3) as response:
                html = response.read().decode('utf-8')
                
            # Extract title from HTML
            import re
            title_match = re.search(r'"title":"([^"]+)"', html)
            if title_match:
                title = title_match.group(1)
                # Decode unicode escape sequences
                title = title.encode().decode('unicode_escape')
                return title
                
        except Exception as e:
            print(f"Error getting YouTube title: {e}")
        return None

    def start_youtube_detection(self):
        """Start periodic YouTube detection - optimized"""
        def youtube_detection_loop():
            # Check if window exists before proceeding
            while hasattr(self, 'window') and self.window.winfo_exists(): 
                try:
                    youtube_info = self.detect_youtube_playback()
                    if self.window.winfo_exists(): # Check again before UI update
                        if youtube_info:
                            self.parent_root.after(0, lambda info=youtube_info: self.update_youtube_track_info(info))
                        else:
                            self.parent_root.after(0, lambda: self.clear_youtube_track_info())
                except Exception as e:
                    # Ensure window exists before printing error related to it
                    if hasattr(self, 'window') and self.window.winfo_exists():
                        print(f"Error in YouTube detection loop: {e}")
                    else: # Window was destroyed, stop loop
                        break 
                
                time.sleep(self.youtube_check_interval)
            # If loop exits because window is gone, print a note
            if not (hasattr(self, 'window') and self.window.winfo_exists()):
                print("MediaWidget: YouTube detection loop stopped, window destroyed.")

        thread = threading.Thread(target=youtube_detection_loop, daemon=True)
        thread.start()
    
    def update_youtube_track_info(self, youtube_info):
        """Update UI with YouTube track info - simplified"""
        if hasattr(self, 'youtube_info_label') and self.youtube_info_label.winfo_exists():
            # Extract just the title, remove everything after " - "
            title = youtube_info["title"].split(" - ")[0].strip()
            
            # Truncate long titles for performance
            if len(title) > 40:
                title = title[:37] + "..."
            
            self.youtube_info_label.config(text=f"🎵 {title}", fg='white')
    
    def clear_youtube_track_info(self):
        """Clear YouTube track info"""
        if hasattr(self, 'youtube_info_label') and self.youtube_info_label.winfo_exists():
            self.youtube_info_label.config(text="🎵 No YouTube video detected", fg='#888888')

    # Media control functions that actually work with browser playback
    def toggle_play_pause(self):
        """Toggle play/pause for browser media"""
        success = self.send_media_key('play_pause')
        if success:
            # Update button state based on current state
            if self.play_pause_btn.cget('text') == "▶":
                self.play_pause_btn.config(text="⏸")
                self.is_playing = True
            else:
                self.play_pause_btn.config(text="▶")
                self.is_playing = False
        else:
            print("Failed to send play/pause command")
            
    def previous_track(self):
        """Previous track for browser media"""
        success = self.send_media_key('previous')
        if success:
            print("Previous track command sent")
        else:
            print("Failed to send previous track command")
        
    def next_track(self):
        """Next track for browser media"""
        success = self.send_media_key('next')
        if success:
            print("Next track command sent")
        else:
            print("Failed to send next track command")
        
    def destroy(self):
        """Clean up widget - simplified"""
        # pygame.mixer.quit() # Might be problematic if other widgets use it, or re-init.
                              # Consider if this is truly necessary or if it should be handled globally.
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
