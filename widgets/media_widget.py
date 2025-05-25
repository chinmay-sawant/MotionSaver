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
import asyncio
import io
from PIL import Image, ImageTk

# Add imports for Windows SDK (only used on Windows)
WINSDK_AVAILABLE = False
if platform.system() == "Windows":
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
        from winsdk.windows.storage.streams import DataReader, Buffer, InputStreamOptions
        WINSDK_AVAILABLE = True
    except ImportError:
        print("Windows SDK not available. Install with: pip install winsdk")
        WINSDK_AVAILABLE = False

class MediaWidget:
    def __init__(self, parent_root, transparent_key='#123456', screen_width=0, screen_height=0):
        self.parent_root = parent_root
        self.transparent_key = transparent_key
        
        self.media_track_info = None
        self.media_check_interval = 20
        self.detection_running = False
        self.initialized = False
        self.last_detection_time = 0
        self.detection_cache = None
        self.cache_timeout = 5
        
        # Add thumbnail support
        self.current_thumbnail = None
        self.thumbnail_size = 50  # Size for the thumbnail
        
        pygame.mixer.init()

        self.window = tk.Toplevel(self.parent_root)
        self.window.overrideredirect(True)
        self.window.attributes('-transparentcolor', self.transparent_key)
        self.window.configure(bg=self.transparent_key)
        self.window.attributes('-topmost', True)

        widget_width = 350  # Increased width to accommodate thumbnail
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
        
        # Create main frame to hold thumbnail and text
        main_frame = tk.Frame(self.window, bg=self.transparent_key)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Thumbnail label (left side)
        self.thumbnail_label = tk.Label(
            main_frame,
            bg=self.transparent_key,
            width=6,  # Roughly thumbnail_size in characters
            height=3
        )
        self.thumbnail_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Text frame (right side)
        text_frame = tk.Frame(main_frame, bg=self.transparent_key)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Media info label
        self.media_info_label = tk.Label(
            text_frame,
            text="🎵 No media detected",
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 11, 'bold'),
            wraplength=220,  # Reduced to account for thumbnail
            anchor='w',
            justify=tk.LEFT
        )
        self.media_info_label.pack(fill=tk.X)
        
        # Control buttons - simplified layout with transparent background
        self.control_frame = tk.Frame(text_frame, bg=self.transparent_key)
        self.control_frame.pack(pady=(5, 0))
        
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
        """Enhanced media detection using Windows Media Session API via winsdk"""
        current_time = time.time()
        
        # Use cached result if still valid
        if (self.detection_cache and 
            current_time - self.last_detection_time < self.cache_timeout):
            return self.detection_cache
        
        try:
            system = platform.system()
            result = None
            
            if system == "Windows" and WINSDK_AVAILABLE:
                # Use Windows SDK for media session detection
                result = self._check_windows_media_session_winsdk()
                
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
    
    def _check_windows_media_session_winsdk(self):
        """Windows Media Session check using winsdk (similar to t2.py approach)"""
        try:
            # Create and run the async task to get media info
            result = asyncio.run(self._get_media_info_async())
            
            # If we got a result, return it
            if result:
                return result
                
            # Otherwise, fall back to browser window check
            return self._check_browser_window_titles()
            
        except Exception as e:
            print(f"Error in winsdk media detection: {e}")
            return self._check_browser_window_titles()
    
    async def _get_media_info_async(self):
        """Async function to get media info via Windows SDK"""
        try:
            # Request the session manager
            manager = await MediaManager.request_async()
            if not manager:
                return None
                
            # Get all sessions
            sessions = manager.get_sessions()
            if not sessions or len(sessions) == 0:
                return None
                
            # Track best session and its info
            best_session = None
            best_session_state = -1  # -1 = none, 0 = other, 1 = paused, 2 = playing
            
            # Check each session to find the best one (playing preferred over paused)
            for session in sessions:
                try:
                    if not session:
                        continue
                        
                    # Get playback info to check status
                    playback_info = session.get_playback_info()
                    if not playback_info:
                        continue
                    
                    # Determine session state
                    current_state = 0  # Default = other
                    if playback_info.playback_status.value == 4:  # 4 = Playing
                        current_state = 2
                    elif playback_info.playback_status.value == 3:  # 3 = Paused
                        current_state = 1
                    
                    # Only update best session if this one is better
                    if current_state > best_session_state:
                        best_session = session
                        best_session_state = current_state
                        
                except Exception as e:
                    print(f"Error processing session: {e}")
                    continue
            
            # If we found a good session, extract its details
            if best_session:
                # Get app ID
                app_id = best_session.source_app_user_model_id if best_session.source_app_user_model_id else "Unknown"
                
                # Get media properties
                props = await best_session.try_get_media_properties_async()
                if not props or not props.title:
                    return None
                
                # Extract basic info
                status = "Playing" if best_session_state == 2 else "Paused" if best_session_state == 1 else "Unknown"
                title = props.title.strip()
                artist = props.artist.strip() if props.artist else ""
                album = props.album_title.strip() if props.album_title else ""
                
                # Get thumbnail if available
                thumbnail_base64 = ""
                if props.thumbnail:
                    try:
                        # Open the thumbnail stream
                        stream_ref = await props.thumbnail.open_read_async()
                        if stream_ref and stream_ref.size > 0 and stream_ref.size < 500000:  # 500KB limit
                            # Create a buffer to hold the thumbnail data
                            buffer_size = int(stream_ref.size)
                            readable_buffer = Buffer(buffer_size)
                            
                            # Read the stream into the buffer
                            await stream_ref.read_async(readable_buffer, readable_buffer.capacity, InputStreamOptions.READ_AHEAD)
                            
                            # Use DataReader to extract bytes
                            data_reader = DataReader.from_buffer(readable_buffer)
                            bytes_available = data_reader.unconsumed_buffer_length
                            if bytes_available > 0:
                                # Read the bytes and convert to base64
                                image_bytes = data_reader.read_bytes(bytes_available)
                                import base64
                                thumbnail_base64 = base64.b64encode(bytes(image_bytes)).decode('utf-8')
                            
                            # Clean up
                            data_reader.close()
                        stream_ref.close()
                    except Exception as e:
                        print(f"Error getting thumbnail: {e}")
                
                # Format the display title
                display_title = title
                if artist:
                    display_title = f"{artist} - {title}"
                
                # Get friendly app name
                source = self._get_app_friendly_name(app_id)
                
                # Create and return the media info dictionary
                media_info = {
                    "title": display_title,
                    "source": source,
                    "status": status,
                    "app_id": app_id,
                    "raw_title": title,
                    "artist": artist,
                    "album": album
                }
                
                if thumbnail_base64:
                    media_info["thumbnail_base64"] = thumbnail_base64
                
                return media_info
        
        except Exception as e:
            print(f"Error in _get_media_info_async: {e}")
            
        return None

    def _get_app_friendly_name(self, app_id):
        """Convert Windows app ID to friendly name"""
        app_id_lower = app_id.lower()
        
        # Common media applications
        if "spotify" in app_id_lower:
            return "Spotify"
        elif "chrome" in app_id_lower:
            return "Chrome"
        elif "firefox" in app_id_lower:
            return "Firefox"
        elif "msedge" in app_id_lower or "edge" in app_id_lower:
            return "Edge"
        elif "vlc" in app_id_lower:
            return "VLC"
        elif "wmplayer" in app_id_lower or "mediaplayer" in app_id_lower:
            return "Windows Media Player"
        elif "itunes" in app_id_lower:
            return "iTunes"
        elif "musicbee" in app_id_lower:
            return "MusicBee"
        elif "foobar" in app_id_lower:
            return "Foobar2000"
        elif "aimp" in app_id_lower:
            return "AIMP"
        elif "winamp" in app_id_lower:
            return "Winamp"
        elif "discord" in app_id_lower:
            return "Discord"
        elif "teams" in app_id_lower:
            return "Teams"
        elif "zoom" in app_id_lower:
            return "Zoom"
        elif "netflix" in app_id_lower:
            return "Netflix"
        elif "prime" in app_id_lower or "amazon" in app_id_lower:
            return "Prime Video"
        elif "youtube" in app_id_lower:
            return "YouTube"
        elif "groove" in app_id_lower:
            return "Groove Music"
        else:
            return "Media Player"

    # Remove the old _check_windows_media_session_fast method
    # Keep _check_browser_window_titles as fallback for older systems
    
    def _check_browser_window_titles(self):
        """Check browser window titles directly - fallback method"""
        try:
            import win32gui
            
            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    
                    # Check for various streaming services
                    patterns = [
                        (" - YouTube", "YouTube"),
                        (" - JioCinema", "JioCinema"),
                        (" | Disney+ Hotstar", "Disney+ Hotstar"),
                        (" | Netflix", "Netflix"),
                        (" - Prime Video", "Prime Video"),
                        (" - Spotify", "Spotify"),
                        (" - SoundCloud", "SoundCloud")
                    ]
                    
                    for pattern, source in patterns:
                        if pattern in window_title:
                            title = window_title.split(pattern)[0].strip()
                            if title and title != source:
                                results.append({
                                    "title": title, 
                                    "source": f"{source} (Window)",
                                    "status": "Playing"
                                })
                                break
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

    def update_media_track_info(self, media_info):
        """Update UI with comprehensive media track info including thumbnail"""
        if hasattr(self, 'media_info_label') and self.media_info_label.winfo_exists():
            title = media_info["title"].strip()
            source = media_info.get("source", "Media")
            status = media_info.get("status", "Playing")
            
            # Handle thumbnail
            self._update_thumbnail(media_info.get("thumbnail_base64"))
            
            # Truncate long titles for performance
            if len(title) > 30:  # Shorter due to thumbnail space
                title = title[:27] + "..."
            
            # Add status indicator
            status_icon = "▶️" if status == "Playing" else "⏸️" if status == "Paused" else "🎵"
            
            display_text = f"{status_icon} {title}"
            self.media_info_label.config(text=display_text, fg='white')
    
    def _update_thumbnail(self, thumbnail_base64):
        """Update the thumbnail image"""
        try:
            if thumbnail_base64 and hasattr(self, 'thumbnail_label'):
                import base64
                from PIL import Image, ImageTk
                import io
                
                # Decode base64 thumbnail
                thumbnail_bytes = base64.b64decode(thumbnail_base64)
                thumbnail_image = Image.open(io.BytesIO(thumbnail_bytes))
                
                # Resize to fit the thumbnail area
                thumbnail_image = thumbnail_image.resize((self.thumbnail_size, self.thumbnail_size), Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage
                self.current_thumbnail = ImageTk.PhotoImage(thumbnail_image)
                self.thumbnail_label.config(image=self.current_thumbnail, bg=self.transparent_key)
                
            elif hasattr(self, 'thumbnail_label'):
                # Clear thumbnail if no image available
                self.thumbnail_label.config(image='', text='🎵', fg='white', bg=self.transparent_key, 
                                          font=('Arial', 20))
                self.current_thumbnail = None
                
        except Exception as e:
            print(f"Error updating thumbnail: {e}")
            # Fallback to music note emoji
            if hasattr(self, 'thumbnail_label'):
                self.thumbnail_label.config(image='', text='🎵', fg='white', bg=self.transparent_key,
                                          font=('Arial', 20))
                self.current_thumbnail = None

    def clear_media_track_info(self):
        """Clear media track info and thumbnail"""
        if hasattr(self, 'media_info_label') and self.media_info_label.winfo_exists():
            self.media_info_label.config(text="🎵 No media detected", fg='#888888')
        
        # Clear thumbnail
        if hasattr(self, 'thumbnail_label') and self.thumbnail_label.winfo_exists():
            self.thumbnail_label.config(image='', text='♪', fg='#888888', bg=self.transparent_key,
                                      font=('Arial', 16))
            self.current_thumbnail = None

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
