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
        self.parent_root = parent_root
        self.transparent_key = transparent_key
        
        self.media_track_info = None # Renamed from youtube_track_info
        self.media_check_interval = 20 # Renamed from youtube_check_interval
        self.detection_running = False
        self.initialized = False
        self.last_detection_time = 0
        self.detection_cache = None
        self.cache_timeout = 5
        
        pygame.mixer.init()

        self.window = tk.Toplevel(self.parent_root)
        self.window.overrideredirect(True)
        self.window.attributes('-transparentcolor', self.transparent_key)
        self.window.configure(bg=self.transparent_key)
        self.window.attributes('-topmost', True)

        widget_width = 300
        widget_height = 80
        
        if screen_width == 0: screen_width = self.parent_root.winfo_screenwidth()
        if screen_height == 0: screen_height = self.parent_root.winfo_screenheight()

        x_pos = 20
        y_pos = screen_height - widget_height - 20
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        
        # Initialize in separate thread with longer delay
        self.init_thread = threading.Thread(target=self._initialize_widget_async, daemon=True)
        self.init_thread.start()
    
    def _initialize_widget_async(self):
        """Initialize widget content in separate thread"""
        try:
            # Longer delay to ensure video is fully stable
            time.sleep(1.0)
            
            # Schedule UI creation on main thread
            self.parent_root.after(0, self._create_widget_ui)
            
        except Exception as e:
            print(f"Error in media widget async initialization: {e}")
    
    def _create_widget_ui(self):
        """Create widget UI on main thread"""
        try:
            if not self.window.winfo_exists():
                return
                
            self.create_widget_content()
            self.initialized = True
            
            # Start detection in separate thread after UI is ready
            self.detection_thread = threading.Thread(target=self._start_detection_async, daemon=True)
            self.detection_thread.start()
            
        except Exception as e:
            print(f"Error creating media widget UI: {e}")
    
    def _start_detection_async(self):
        """Start media detection in completely separate thread""" # Renamed
        try:
            time.sleep(3.0)
            self.start_media_detection() # Renamed
        except Exception as e:
            print(f"Error starting media detection: {e}")

    def create_widget_content(self):
        """Create the media widget UI content within its Toplevel window"""
        
        self.media_info_label = tk.Label( # Renamed from youtube_info_label
            self.window,
            text="🎵 No media detected", # Generic text
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 11, 'bold'),
            wraplength=280,
            anchor='w',
            justify=tk.LEFT
        )
        self.media_info_label.pack(fill=tk.X, pady=5, padx=5) # Renamed
        
        # Control buttons - simplified layout with transparent background
        self.control_frame = tk.Frame(self.window, bg=self.transparent_key)
        self.control_frame.pack(pady=5)
        
        btn_config = {
            'bg': self.transparent_key,
            'fg': 'white',
            'font': ('Arial', 16),
            'width': 2,
            'height': 1,
            'activebackground': '#333333',
            'activeforeground': 'white',
            'relief': 'flat',
            'bd': 0,
            'highlightthickness': 0
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

    def detect_media_playback(self):
        """Ultra-lightweight media detection with caching"""
        current_time = time.time()
        
        # Use cached result if still valid
        if (self.detection_cache and 
            current_time - self.last_detection_time < self.cache_timeout):
            return self.detection_cache
        
        try:
            system = platform.system()
            result = None
            
            if system == "Windows":
                # Try Windows Media Session first
                result = self._check_windows_media_session_fast()
                
                # If no result, try direct window title check as fallback
                if not result:
                    result = self._check_browser_window_titles()
                
            elif system == "Darwin":
                result = self._check_macos_chrome_fast()
            
            # Debug output for troubleshooting
            if result:
                print(f"Detected media: {result}")
                
            # Cache the result
            self.detection_cache = result
            self.last_detection_time = current_time
            return result
            
        except Exception as e:
            print(f"Error in media detection: {e}")
            return None
    
    def _check_windows_media_session_fast(self):
        """Ultra-fast Windows Media Session check for browsers"""
        try:
            # Version with more extensive debugging
            powershell_cmd = '''
            try {
                Add-Type -AssemblyName System.Runtime.WindowsRuntime
                $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

                Function Await($WinRtTask, $ResultType) {
                    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
                    $netTask = $asTask.Invoke($null, @($WinRtTask))
                    $netTask.Wait(-1) | Out-Null
                    $netTask.Result
                }

                $sessionManager = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
                $sessionManager = Await $sessionManager ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
                
                $sessions = $sessionManager.GetSessions()
                ForEach ($session in $sessions) {
                    $info = $session.SourceAppUserModelId
                    $props = $session.TryGetMediaPropertiesAsync()
                    $props = Await $props ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
                    
                    if ($props.Title) {
                        $cleanTitle = $props.Title -replace "[\r\n]", " "
                        $appIdLower = $info.ToLower()
                        
                        # Include all browsers, not just YouTube-specific
                        if ($appIdLower -like "*chrome*" -or $appIdLower -like "*firefox*" -or $appIdLower -like "*edge*" -or $appIdLower -like "*opera*" -or $appIdLower -like "*brave*") {
                            Write-Output "MEDIA|$info|$cleanTitle|$($props.Artist)"
                            break
                        }
                    }
                }
            }
            catch {
                Write-Output "ERROR|$_"
            }
            '''
            
            result = subprocess.run(['powershell', '-Command', powershell_cmd], 
                                  capture_output=True, text=True, timeout=2)
            
            if result.stdout and result.stdout.strip():
                output = result.stdout.strip()
                
                if output.startswith("ERROR|"):
                    print(f"PowerShell error: {output[6:]}")
                    return None
                
                if output.startswith("MEDIA|"):
                    parts = output.split("|", 4)  # Split into parts: MEDIA, AppId, Title, Artist
                    if len(parts) >= 3:
                        title = parts[2].strip()
                        if title:
                            return {"title": title, "source": "Browser"}
                                
        except subprocess.TimeoutExpired:
            print("PowerShell media check timed out")
            pass
        except Exception as e:
            print(f"Windows Media Session error: {e}")
            pass
        return None
        
    def _check_browser_window_titles(self):
        """Check browser window titles directly - fallback method for YouTube"""
        try:
            import win32gui
            
            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    
                    # Check for YouTube title format or JioCinema
                    if " - YouTube" in window_title:
                        title = window_title.split(" - YouTube")[0].strip()
                        if title and title != "YouTube":
                            results.append({"title": title, "source": "YouTube-Window"})
                    elif " - JioCinema" in window_title:
                        title = window_title.split(" - JioCinema")[0].strip()
                        if title:
                            results.append({"title": title, "source": "JioCinema"})
                    # Add more streaming services if needed
                    elif " | Disney+ Hotstar" in window_title:
                        title = window_title.split(" | Disney+ Hotstar")[0].strip()
                        if title:
                            results.append({"title": title, "source": "Hotstar"})
                    elif " | Netflix" in window_title:
                        title = window_title.split(" | Netflix")[0].strip()
                        if title:
                            results.append({"title": title, "source": "Netflix"})
                return True
                
            results = []
            win32gui.EnumWindows(enum_windows_callback, results)
            
            if results:
                print(f"Window title detection found: {results[0]}")
                return results[0]
            
        except ImportError:
            print("win32gui not available for window title detection")
        except Exception as e:
            print(f"Browser window detection error: {e}")
        
        return None

    def start_media_detection(self):
        """Optimized media detection with reduced frequency"""
        def media_detection_loop():
            self.detection_running = True
            detection_count = 0
            
            # Run one detection immediately at start
            try:
                detection_thread_job = threading.Thread(
                    target=self._perform_detection_async, 
                    daemon=True
                )
                detection_thread_job.start()
                detection_count += 1
            except Exception as e:
                print(f"Initial media detection error: {e}")
            
            # Then continue with normal detection loop
            while self.detection_running and hasattr(self, 'window'):
                try:
                    if not self.window.winfo_exists():
                        break
                    
                    if detection_count < 5:
                        current_interval = self.media_check_interval # Use renamed variable
                    elif detection_count < 10:
                        current_interval = self.media_check_interval * 1.5
                    else:
                        current_interval = self.media_check_interval * 2
                    
                    detection_thread_job = threading.Thread( # Renamed variable for clarity
                        target=self._perform_detection_async, 
                        daemon=True
                    )
                    detection_thread_job.start() # Renamed variable
                    
                    detection_count += 1
                    time.sleep(current_interval)
                    
                except Exception as e:
                    if hasattr(self, 'window') and self.window.winfo_exists():
                        print(f"Error in media detection loop: {e}")
                    else:
                        break 
                
            print("MediaWidget: Media detection loop stopped.")

        # Run detection in completely separate thread with lower priority
        main_detection_thread = threading.Thread(target=media_detection_loop, daemon=True) # Renamed
        main_detection_thread.start() # Renamed
    
    def _perform_detection_async(self):
        """Perform detection in separate thread"""
        try:
            media_info_result = self.detect_media_playback() # Renamed method call
            
            if hasattr(self, 'window') and self.window.winfo_exists():
                if media_info_result:
                    self.parent_root.after(0, lambda info=media_info_result: self.update_media_track_info(info)) # Renamed
                else:
                    self.parent_root.after(0, lambda: self.clear_media_track_info()) # Renamed
        except Exception as e:
            pass

    def update_media_track_info(self, media_info): # Renamed from update_youtube_track_info
        """Update UI with media track info"""
        if hasattr(self, 'media_info_label') and self.media_info_label.winfo_exists(): # Use renamed label
            title = media_info["title"].strip() 
            
            if len(title) > 40:
                title = title[:37] + "..."
            
            self.media_info_label.config(text=f"🎵 {title}", fg='white') # Use renamed label
    
    def clear_media_track_info(self): # Renamed from clear_youtube_track_info
        """Clear media track info"""
        if hasattr(self, 'media_info_label') and self.media_info_label.winfo_exists(): # Use renamed label
            self.media_info_label.config(text="🎵 No media detected", fg='#888888') # Use renamed label

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
        """Clean up widget"""
        self.detection_running = False
        self.detection_cache = None  # Clear cache
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
