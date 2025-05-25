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
        
        # Heavily optimized YouTube integration
        self.youtube_track_info = None
        self.youtube_check_interval = 20  # Increased to 20 seconds to reduce overhead
        self.detection_running = False
        self.initialized = False
        self.last_detection_time = 0
        self.detection_cache = None
        self.cache_timeout = 5  # Cache results for 5 seconds
        
        # Initialize pygame mixer (still needed for potential future use)
        pygame.mixer.init()

        # Create window immediately but defer content creation
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
        """Start YouTube detection in completely separate thread"""
        try:
            # Much longer delay before starting detection
            time.sleep(3.0)  # Wait 3 seconds before starting detection
            self.start_youtube_detection()
        except Exception as e:
            print(f"Error starting media detection: {e}")

    def create_widget_content(self):
        """Create the media widget UI content within its Toplevel window"""
        
        # YouTube section - simplified with better transparency and text alignment
        self.youtube_info_label = tk.Label(
            self.window,
            text="🎵 No YouTube video detected",
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 11, 'bold'),
            wraplength=280,
            anchor='w',
            justify=tk.LEFT
        )
        self.youtube_info_label.pack(fill=tk.X, pady=5, padx=5)
        
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

    def detect_youtube_playback(self):
        """Ultra-lightweight YouTube detection with caching"""
        current_time = time.time()
        
        # Use cached result if still valid
        if (self.detection_cache and 
            current_time - self.last_detection_time < self.cache_timeout):
            return self.detection_cache
        
        try:
            system = platform.system()
            result = None
            
            if system == "Windows":
                # Only use the fastest method - Windows Media Session
                result = self._check_windows_media_session_fast()
                
            elif system == "Darwin":  # macOS
                # Ultra-simplified macOS approach
                result = self._check_macos_chrome_fast()
            
            # Cache the result
            self.detection_cache = result
            self.last_detection_time = current_time
            return result
            
        except Exception as e:
            print(f"Error in lightweight YouTube detection: {e}")
            return None
    
    def _check_windows_media_session_fast(self):
        """Ultra-fast Windows Media Session check"""
        try:
            # Simplified PowerShell command with shorter timeout
            powershell_cmd = '''
            $sessions = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetAwaiter().GetResult().GetSessions()
            foreach ($session in $sessions) {
                $props = $session.TryGetMediaPropertiesAsync().GetAwaiter().GetResult()
                if ($props.Title -and $props.Title -ne "") {
                    $app = $session.SourceAppUserModelId
                    if ($app -like "*chrome*" -or $app -like "*firefox*" -or $app -like "*edge*") {
                        Write-Output $props.Title
                        break
                    }
                }
            }
            '''
            
            result = subprocess.run(['powershell', '-Command', powershell_cmd], 
                                  capture_output=True, text=True, timeout=1.5)  # Reduced timeout
            
            if result.stdout and result.stdout.strip():
                title = result.stdout.strip()
                # Basic check if it's likely YouTube
                if len(title) > 3 and title != "YouTube":
                    return {"title": title, "source": "YouTube"}
                                
        except subprocess.TimeoutExpired:
            pass  # Timeout is expected with heavy loads
        except Exception as e:
            pass  # Silently handle errors to avoid spam
        return None
    
    def _check_macos_chrome_fast(self):
        """Ultra-fast macOS Chrome check"""
        try:
            # Very minimal AppleScript
            script = '''
            tell application "Google Chrome"
                if it is running then
                    try
                        set activeTab to active tab of front window
                        set tabTitle to title of activeTab
                        if tabTitle contains " - YouTube" then
                            return tabTitle
                        end if
                    end try
                end if
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, timeout=1.0)  # Very short timeout
            if result.stdout and " - YouTube" in result.stdout:
                title = result.stdout.strip()
                video_title = title.split(" - YouTube")[0].strip()
                
                if video_title and video_title != "YouTube":
                    return {"title": video_title, "source": "YouTube"}
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            pass
        return None

    def start_youtube_detection(self):
        """Optimized YouTube detection with reduced frequency"""
        def youtube_detection_loop():
            self.detection_running = True
            detection_count = 0
            
            while self.detection_running and hasattr(self, 'window'):
                try:
                    if not self.window.winfo_exists():
                        break
                    
                    # Progressive interval increase - check less frequently over time
                    if detection_count < 5:
                        current_interval = self.youtube_check_interval
                    elif detection_count < 10:
                        current_interval = self.youtube_check_interval * 1.5
                    else:
                        current_interval = self.youtube_check_interval * 2  # Check every 40 seconds after 10 attempts
                    
                    # Run detection in separate thread to avoid blocking even this loop
                    detection_thread = threading.Thread(
                        target=self._perform_detection_async, 
                        daemon=True
                    )
                    detection_thread.start()
                    
                    detection_count += 1
                    time.sleep(current_interval)
                    
                except Exception as e:
                    if hasattr(self, 'window') and self.window.winfo_exists():
                        print(f"Error in YouTube detection loop: {e}")
                    else:
                        break 
                
            print("MediaWidget: YouTube detection loop stopped.")

        # Run detection in completely separate thread with lower priority
        detection_thread = threading.Thread(target=youtube_detection_loop, daemon=True)
        detection_thread.start()
    
    def _perform_detection_async(self):
        """Perform detection in separate thread"""
        try:
            youtube_info = self.detect_youtube_playback()
            
            # Only update UI if window still exists
            if hasattr(self, 'window') and self.window.winfo_exists():
                if youtube_info:
                    self.parent_root.after(0, lambda info=youtube_info: self.update_youtube_track_info(info))
                else:
                    self.parent_root.after(0, lambda: self.clear_youtube_track_info())
        except Exception as e:
            pass  # Silently handle errors in background detection

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
        """Clean up widget"""
        self.detection_running = False
        self.detection_cache = None  # Clear cache
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
