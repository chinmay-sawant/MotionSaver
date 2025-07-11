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
import sys

# Add central logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('MediaWidget')

# Add imports for Windows SDK (only used on Windows)
WINSDK_AVAILABLE = False
if platform.system() == "Windows":
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
        from winsdk.windows.storage.streams import DataReader, Buffer, InputStreamOptions
        WINSDK_AVAILABLE = True    
    except ImportError:
        logger.warning("Windows SDK not available. Install with: pip install winsdk")
        WINSDK_AVAILABLE = False

class MediaWidget:    
    def __init__(self, parent_root, transparent_key='#010203', screen_width=0, screen_height=0):  # Updated default
        logger.info("Initializing MediaWidget")
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
        
        try:
            pygame.mixer.init()
        except Exception as e:
            logger.warning(f"Pygame mixer init failed: {e}")

        # Create window with proper error handling
        try:
            self.window = tk.Toplevel(self.parent_root)
            self.window.overrideredirect(True)
            self.window.attributes('-transparentcolor', self.transparent_key)
            self.window.configure(bg=self.transparent_key)
            self.window.attributes('-topmost', True)
            
            # Remove any focus-related attributes that might interfere
            self.window.attributes('-disabled', False)  # Ensure it's interactive

            widget_width = 350  # Increased width to accommodate thumbnail
            widget_height = 120  # Increased height for better visibility
            
            if screen_width == 0: screen_width = self.parent_root.winfo_screenwidth()
            if screen_height == 0: screen_height = self.parent_root.winfo_screenheight()

            # Position at bottom left instead of bottom right
            x_pos = 20
            y_pos = screen_height - widget_height - 20  # Bottom left positioning
            
            logger.info(f"MediaWidget positioning: {widget_width}x{widget_height}+{x_pos}+{y_pos}")
            self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
            
            # Ensure window is visible and properly stacked
            self.window.deiconify()
            self.window.lift()
            self.window.focus_set()  # Allow focus for interactions
            
            logger.info("MediaWidget window created successfully")
            
        except Exception as e:
            logger.error(f"Error creating MediaWidget window: {e}")
            return
        
        # Reduced initialization delay for faster startup
        self.init_thread = threading.Thread(target=self._initialize_widget_async, daemon=True)
        self.init_thread.start()
    
    def _initialize_widget_async(self):
        """Initialize widget content in separate thread"""
        try:
            # Reduced delay for faster startup
            time.sleep(0.3)  # Reduced from 1.5
            
            # Schedule UI creation on main thread
            if hasattr(self, 'window') and self.window.winfo_exists():
                self.parent_root.after(0, self._create_widget_ui)
            else:
                logger.error("MediaWidget window no longer exists during async init")
            
        except Exception as e:
            logger.error(f"Error in media widget async initialization: {e}")
    
    def _create_widget_ui(self):
        """Create widget UI on main thread"""
        try:
            if not hasattr(self, 'window') or not self.window.winfo_exists():
                logger.error("MediaWidget window does not exist when creating UI")
                return
                
            logger.info("Creating MediaWidget UI content")
            self.create_widget_content()
            self.initialized = True
            
            # Start detection in separate thread after UI is ready
            self.detection_thread = threading.Thread(target=self._start_detection_async, daemon=True)            
            self.detection_thread.start()
            
            logger.info("MediaWidget UI created successfully")
            
        except Exception as e:
            logger.error(f"Error creating media widget UI: {e}")

    def create_widget_content(self):
        """Create the media widget UI content within its Toplevel window"""
        try:
            # Remove debug frame and use proper transparent background
            # Create main frame to hold thumbnail and text
            main_frame = tk.Frame(self.window, bg=self.transparent_key)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Thumbnail label (left side) - make it clickable
            self.thumbnail_label = tk.Label(
                main_frame,
                bg=self.transparent_key,
                width=6,  # Roughly thumbnail_size in characters
                height=3,
                cursor='hand2'  # Add hand cursor for clickability
            )
            self.thumbnail_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Text frame (right side)
            text_frame = tk.Frame(main_frame, bg=self.transparent_key)
            text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Media info label with better visibility and clickability
            self.media_info_label = tk.Label(
                text_frame,
                text="🎵 Media Widget Active",  # Changed initial text for visibility
                bg=self.transparent_key, 
                fg='white',
                font=('Segoe UI', 12, 'bold'),  # Slightly larger font
                wraplength=220,  # Reduced to account for thumbnail
                anchor='w',
                justify=tk.LEFT,
                cursor='hand2'  # Add hand cursor for clickability
            )
            self.media_info_label.pack(fill=tk.X, pady=2)
            
            # Control buttons - make them more interactive
            self.control_frame = tk.Frame(text_frame, bg=self.transparent_key)
            self.control_frame.pack(pady=(5, 0))
            
            btn_config = {
                'bg': self.transparent_key,
                'fg': 'white',
                'font': ('Segoe UI', 16),
                'width': 2,
                'height': 1,
                'activebackground': '#333333',
                'activeforeground': 'white',
                'relief': 'flat',
                'bd': 0,
                'highlightthickness': 0,
                'cursor': 'hand2'  # Add hand cursor for all buttons
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

            logger.info("MediaWidget content created successfully")
            
        except Exception as e:
            logger.error(f"Error creating MediaWidget content: {e}")
            # Create minimal fallback UI
            try:
                fallback_label = tk.Label(
                    self.window,
                    text="🎵 Media Widget (Fallback)",
                    bg='red',  # Visible background for debugging
                    fg='white',
                    font=('Arial', 10)
                )
                fallback_label.pack(fill=tk.BOTH, expand=True)
            except Exception as fallback_error:
                logger.error(f"Even fallback UI creation failed: {fallback_error}")

    def _start_detection_async(self):
        """Start media detection in completely separate thread""" 
        try:
            time.sleep(2.0)  # Increased delay
            logger.info("Starting media detection")
            self.media_detection_loop()
        except Exception as e:
            logger.error(f"Error starting media detection: {e}")

    def send_media_key(self, key):
        """Send media key commands to control browser playback"""
        try:
            system = platform.system()
            
            if system == "Windows":
                # Use Windows API to send media keys
                try:
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
                        time.sleep(0.05)  # Small delay
                        win32api.keybd_event(media_keys[key], 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up
                        logger.debug(f"Sent media key: {key}")
                        return True
                except ImportError:
                    logger.warning("win32api not available, trying alternative method")
                    # Fallback to keyboard module if available
                    try:
                        import keyboard
                        key_map = {
                            'play_pause': 'play/pause media',
                            'next': 'next track',
                            'previous': 'previous track'
                        }
                        if key in key_map:
                            keyboard.press_and_release(key_map[key])
                            return True
                    except ImportError:
                        logger.warning("keyboard module not available")
                        return False
                    
            elif system == "Darwin":  # macOS
                # Use AppleScript to send media keys
                scripts = {
                    'play_pause': 'tell application "System Events" to key code 16',  # Play/Pause
                    'next': 'tell application "System Events" to key code 17',       # Next
                    'previous': 'tell application "System Events" to key code 18'   # Previous
                }
                if key in scripts:
                    subprocess.run(['osascript', '-e', scripts[key]], capture_output=True)
                    logger.debug(f"Sent media key: {key}")
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
                    logger.debug(f"Sent media key: {key}")
                    return True
                    
        except Exception as e:
            logger.error(f"Error sending media key {key}: {e}")
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
            
            # Debug output for troubleshooting            if result:
                logger.debug(f"Detected media: {result}")
                
            # Cache the result
            self.detection_cache = result
            self.last_detection_time = current_time
            return result
            
        except Exception as e:
            logger.error(f"Error in media detection: {e}")
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
            logger.error(f"Error in winsdk media detection: {e}")
            return self._check_browser_window_titles()
    
    async def _get_media_info_async(self):
        """Async function to get media info via Windows SDK with enhanced video detection"""
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
                    logger.error(f"Error processing session: {e}")
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
                
                # Enhanced thumbnail handling for video content
                thumbnail_base64 = ""
                if props.thumbnail:
                    try:
                        # Open the thumbnail stream
                        stream_ref = await props.thumbnail.open_read_async()
                        
                        # Check if the stream is valid and has a reasonable size
                        if stream_ref and stream_ref.size > 0 and stream_ref.size < 1000000:
                            # Create a buffer to hold the thumbnail data
                            buffer_size = int(stream_ref.size)
                            readable_buffer = Buffer(buffer_size)
                            
                            # Read the stream into the buffer
                            await stream_ref.read_async(readable_buffer, readable_buffer.capacity, InputStreamOptions.READ_AHEAD)
                            
                            # Use DataReader to extract bytes
                            data_reader = DataReader.from_buffer(readable_buffer)
                            bytes_available = data_reader.unconsumed_buffer_length
                            
                            if bytes_available > 0:
                                # --- FIX STARTS HERE ---
                                
                                # 1. Create a mutable bytearray to serve as the destination buffer.
                                image_bytes = bytearray(bytes_available)
                                
                                # 2. Call read_bytes() to fill the bytearray you just created.
                                #    This method does not return anything; it modifies image_bytes in-place.
                                data_reader.read_bytes(image_bytes)
                                
                                # --- FIX ENDS HERE ---
                                
                                # Now, `image_bytes` is a bytearray containing the data.
                                # You can encode it directly to base64.
                                import base64
                                thumbnail_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            
                            # Clean up
                            data_reader.close()

                        # Always close the stream reference
                        if stream_ref:
                            stream_ref.close()

                    except Exception as e:
                        # Use logger.exception to get the full stack trace for debugging.
                        # This is more informative than logger.debug.
                        logger.exception(f"Thumbnail extraction failed (normal for some media): {e}")
                # Format the display title
                display_title = title
                if artist:
                    display_title = f"{artist} - {title}"
                
                # Get friendly app name and detect video content
                source = self._get_app_friendly_name(app_id)
                
                # Create and return the media info dictionary
                media_info = {
                    "title": display_title,
                    "source": source,
                    "status": status,
                    "app_id": app_id,
                    "raw_title": title,
                    "artist": artist,
                    "album": album,
                    "is_video": self._is_video_content(title, artist, source)
                }
                
                if thumbnail_base64:
                    media_info["thumbnail_base64"] = thumbnail_base64
                
                return media_info
        except Exception as e:
            logger.error(f"Error in _get_media_info_async: {e}")
            
        return None

    def _is_video_content(self, title, artist, source):
        """Detect if the content is likely video based on title, artist, and source"""
        video_indicators = [
            "youtube", "video", "movie", "film", "episode", "season",
            "trailer", "clip", "vlog", "documentary", "netflix", "prime",
            "disney", "hbo", "twitch", "stream"
        ]
        
        text_to_check = f"{title} {artist} {source}".lower()
        return any(indicator in text_to_check for indicator in video_indicators)

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

    def toggle_play_pause(self):
        """Toggle play/pause for browser media"""
        logger.info("Play/pause button clicked")
        success = self.send_media_key('play_pause')
        if success:
            logger.info("Play/pause command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send play/pause command")
            
    def previous_track(self):
        """Previous track for browser media"""
        logger.info("Previous button clicked")
        success = self.send_media_key('previous')
        if success:
            logger.info("Previous track command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send previous track command")
        
    def next_track(self):
        """Next track for browser media"""
        logger.info("Next button clicked")
        success = self.send_media_key('next')
        if success:
            logger.info("Next track command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send next track command")

    def _force_update_detection(self):
        """Force an immediate media detection update"""
        try:
            self.detection_cache = None  # Clear cache to force fresh detection
            self.last_detection_time = 0
            # Run detection in separate thread
            detection_thread = threading.Thread(target=self._perform_detection_async, daemon=True)
            detection_thread.start()
        except Exception as e:
            logger.error(f"Error in forced detection update: {e}")

    def show(self):
        """Show the media widget"""
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            logger.info("MediaWidget shown")

    def hide(self):
        """Hide the media widget"""
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.withdraw()
            logger.info("MediaWidget hidden")

    def destroy(self):
        """Clean up widget"""
        self.detection_running = False
        self.detection_cache = None  # Clear cache
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
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
                logger.error(f"Initial media detection error: {e}")
            
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
                        logger.error(f"Error in media detection loop: {e}")
                    else:
                        break 
                
            logger.debug("MediaWidget: Media detection loop stopped.")

        # Run detection in completely separate thread with lower priority
        main_detection_thread = threading.Thread(target=self.media_detection_loop, daemon=True) # Renamed
        main_detection_thread.start() # Renamed

    def media_detection_loop(self):
        """Continuously detect media playback in a background thread."""
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
            logger.error(f"Initial media detection error: {e}")

        # Then continue with normal detection loop
        while self.detection_running and hasattr(self, 'window'):
            try:
                if not self.window.winfo_exists():
                    break

                if detection_count < 5:
                    current_interval = self.media_check_interval
                elif detection_count < 10:
                    current_interval = self.media_check_interval * 1.5
                else:
                    current_interval = self.media_check_interval * 2

                detection_thread_job = threading.Thread(
                    target=self._perform_detection_async,
                    daemon=True
                )
                detection_thread_job.start()

                detection_count += 1
                time.sleep(current_interval)
            except Exception as e:
                if hasattr(self, 'window') and self.window.winfo_exists():
                    logger.error(f"Error in media detection loop: {e}")
                else:
                    break

        logger.debug("MediaWidget: Media detection loop stopped.")
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
                                          font=('Segoe UI', 20))
                self.current_thumbnail = None
        except Exception as e:
            logger.error(f"Error updating thumbnail: {e}")
            # Fallback to music note emoji
            if hasattr(self, 'thumbnail_label'):
                self.thumbnail_label.config(image='', text='🎵', fg='white', bg=self.transparent_key,
                                          font=('Segoe UI', 20))
                self.current_thumbnail = None

    def clear_media_track_info(self):
        """Clear media track info and thumbnail"""
        if hasattr(self, 'media_info_label') and self.media_info_label.winfo_exists():
            self.media_info_label.config(text="🎵 No media detected", fg='#888888')
        
        # Clear thumbnail
        if hasattr(self, 'thumbnail_label') and self.thumbnail_label.winfo_exists():
            self.thumbnail_label.config(image='', text='♪', fg='#888888', bg=self.transparent_key,
                                      font=('Segoe UI', 16))
            self.current_thumbnail = None

    def toggle_play_pause(self):
        """Toggle play/pause for browser media"""
        logger.info("Play/pause button clicked")
        success = self.send_media_key('play_pause')
        if success:
            logger.info("Play/pause command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send play/pause command")
            
    def previous_track(self):
        """Previous track for browser media"""
        logger.info("Previous button clicked")
        success = self.send_media_key('previous')
        if success:
            logger.info("Previous track command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send previous track command")
        
    def next_track(self):
        """Next track for browser media"""
        logger.info("Next button clicked")
        success = self.send_media_key('next')
        if success:
            logger.info("Next track command sent successfully")
            # Force update detection after a short delay
            threading.Timer(0.5, self._force_update_detection).start()
        else:
            logger.warning("Failed to send next track command")

    def _force_update_detection(self):
        """Force an immediate media detection update"""
        try:
            self.detection_cache = None  # Clear cache to force fresh detection
            self.last_detection_time = 0
            # Run detection in separate thread
            detection_thread = threading.Thread(target=self._perform_detection_async, daemon=True)
            detection_thread.start()
        except Exception as e:
            logger.error(f"Error in forced detection update: {e}")

    def show(self):
        """Show the media widget"""
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            logger.info("MediaWidget shown")

    def hide(self):
        """Hide the media widget"""
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.withdraw()
            logger.info("MediaWidget hidden")

    def destroy(self):
        """Clean up widget"""
        self.detection_running = False
        self.detection_cache = None  # Clear cache
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
