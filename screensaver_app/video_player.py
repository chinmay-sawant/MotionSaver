import tkinter as tk
import vlc
from PIL import Image, ImageTk, ImageDraw, ImageFont
import time
import os
import json
import threading
import queue
import tkinter.font as tkfont
import platform
from concurrent.futures import ThreadPoolExecutor
import collections
import getpass  # Added import
from utils.config_utils import find_user_config_path, load_config, save_config
# Add central logging
import sys
import subprocess
from utils.multi_monitor import update_secondary_monitor_blackouts
from utils.wallpaper import set_windows_wallpaper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('VideoPlayer')
# Try to import enhanced blocker first, fallback to basic blocker
try:
    from utils.enhanced_key_blocker import EnhancedKeyBlocker as KeyBlocker
    logger.info("Using enhanced key blocker")
except ImportError:
    from utils.blockit import KeyBlocker # Assuming blockit.py contains a basic KeyBlocker
    logger.info("Using basic key blocker from blockit.py")

# Custom UAC elevation functions to replace pyUAC
def is_admin():
    """Check if the current process is running with admin privileges."""
    logger.info("is_admin")
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Restart the current script with admin privileges without showing console window."""
    logger.info("run_as_admin")
    if platform.system() != "Windows":
        return False
    
    try:
        import ctypes
        # Get the current script path and arguments
        script = os.path.abspath(sys.argv[0])
        params = ' '.join(sys.argv[1:])
        
        # Use ShellExecuteW to run with admin privileges and hide console
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            f'"{script}" {params}', 
            None, 
            0  # SW_HIDE - hide the window
        )
        return True
    except Exception as e:
        logger.error(f"Failed to elevate privileges: {e}")
        return False

def hide_console_window():
    """Hide the console window for the current process."""
    logger.info("hide_console_window")
    if platform.system() == "Windows":
        try:
            import ctypes
            # Get console window handle
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                # Hide the console window
                ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE
                logger.info("Console window hidden successfully")
        except Exception as e:
            logger.warning(f"Failed to hide console window: {e}")

# For multi-monitor black-out and event hooking on Windows
WINDOWS_MULTI_MONITOR_SUPPORT = False
hWinEventHook = None
root_ref_for_hook = None # Global reference to the root window for the hook callback

# Global variables for tray mode and Ctrl+Alt+Del tracking
tray_running = False
win_s_blocker = None
tray_icon_instance = None
ctrl_alt_del_tracker = {"triggered": False, "timestamp": None}

callback_ref = None
secondary_screen_windows = [] 
def WinEventProcCallback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """Callback for Windows display change events."""
    logger.info("WinEventProcCallback")
    global root_ref_for_hook
    if event == EVENT_SYSTEM_DISPLAYSETTINGSCHANGED:  # Using our defined constant instead of win32con
        if root_ref_for_hook and root_ref_for_hook.winfo_exists():
            # Schedule the update on the main Tkinter thread
            root_ref_for_hook.after(50, lambda: update_secondary_monitor_blackouts(root_ref_for_hook)) # Small delay



# Define missing Windows constants
# From winuser.h: EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F
EVENT_SYSTEM_DISPLAYSETTINGSCHANGED = 0x000F

if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        # Remove win32ts import and any session monitoring references
        import win32event
        from ctypes import windll, CFUNCTYPE, c_int, c_uint, c_void_p, POINTER, Structure, c_size_t, byref, c_wchar_p, wintypes
        
        # Flag for multi-monitor support
        WINDOWS_MULTI_MONITOR_SUPPORT = True
        logger.info("Windows multi-monitor support enabled with pywin32")
        
        # Define the WinEventProc callback function type
        # WINEVENTPROC callback function prototype
        WinEventProcType = CFUNCTYPE(
            None,               # return type: void
            c_void_p,           # hWinEventHook
            c_uint,             # event
            c_void_p,           # hwnd
            c_int,              # idObject
            c_int,              # idChild
            c_uint,             # dwEventThread
            c_uint              # dwmsEventTime
        )
        
        # Define SetWinEventHook function prototype
        user32 = windll.user32
        user32.SetWinEventHook.argtypes = [
            c_uint,             # eventMin
            c_uint,             # eventMax
            c_void_p,           # hmodWinEventProc
            WinEventProcType,   # lpfnWinEventProc
            c_uint,             # idProcess
            c_uint,             # idThread
            c_uint              # dwFlags
        ]
        user32.SetWinEventHook.restype = c_void_p
        
        # Define UnhookWinEvent function prototype
        user32.UnhookWinEvent.argtypes = [c_void_p]  # hWinEventHook
        user32.UnhookWinEvent.restype = c_int        # BOOL
        
        # Use the properly defined functions
        SetWinEventHook = user32.SetWinEventHook
        UnhookWinEvent = user32.UnhookWinEvent
        
    except ImportError:
        logger.warning("pywin32 not installed, multi-monitor features and session monitoring will be limited.")

else:
    logger.info("Non-Windows OS detected, session monitoring not available")

def get_username_from_config():
    config = load_config()
    return config.get('default_user_for_display', 'User')

def get_user_config():
    return load_config()

def draw_rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=2):
    """Draws a rounded rectangle on a PIL Draw object."""
    x1, y1, x2, y2 = xy
    # Ensure coordinates are integers for drawing
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    radius = int(radius)

    draw.rectangle([(x1+radius, y1), (x2-radius, y2)], fill=fill, outline=outline if fill else None, width=width if fill else 0)
    draw.rectangle([(x1, y1+radius), (x2, y2-radius)], fill=fill, outline=outline if fill else None, width=width if fill else 0)
    
    # Pieslice requires integer coordinates
    draw.pieslice([(x1, y1), (x1+2*radius, y1+2*radius)], 180, 270, fill=fill, outline=outline if fill else None, width=width if fill else 0)
    draw.pieslice([(x2-2*radius, y1), (x2, y1+2*radius)], 270, 360, fill=fill, outline=outline if fill else None, width=width if fill else 0)
    draw.pieslice([(x1, y2-2*radius), (x1+2*radius, y2)], 90, 180, fill=fill, outline=outline if fill else None, width=width if fill else 0)
    draw.pieslice([(x2-2*radius, y2-2*radius), (x2, y2)], 0, 90, fill=fill, outline=outline if fill else None, width=width if fill else 0)
    
    if not fill and outline:  # Draw border if no fill
        draw.line([(x1+radius, y1), (x2-radius, y1)], fill=outline, width=width)
        draw.line([(x1+radius, y2), (x2-radius, y2)], fill=outline, width=width)  # Thicker bottom border
        draw.line([(x1, y1+radius), (x1, y2-radius)], fill=outline, width=width)
        draw.line([(x2, y1+radius), (x2, y2-radius)], fill=outline, width=width)



def find_font_path(font_family):
    """Try to find the font file path for a given font family name."""
    import glob

    font_dirs = []
    system = platform.system()
    if system == "Windows":
        font_dirs = [os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")]
        # Also check user fonts directory (Windows 10+)
        user_fonts = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts")
        if os.path.isdir(user_fonts):
            font_dirs.append(user_fonts)
    elif system == "Darwin":
        font_dirs = ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:  # Linux/Unix
        font_dirs = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]

    # Normalize font family for matching
    normalized_family = font_family.replace(" ", "").replace("-", "").replace("_", "").lower()

    # Try to find .ttf or .otf file matching the font family (exact and partial match, case-insensitive)
    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for root, dirs, files in os.walk(font_dir):
            for file in files:
                if file.lower().endswith((".ttf", ".otf")):
                    file_no_ext = os.path.splitext(file)[0].replace(" ", "").replace("-", "").replace("_", "").lower()
                    # Try exact match first (case-insensitive)
                    if normalized_family == file_no_ext:
                        return os.path.join(root, file)
                    # Then try partial match
                    if normalized_family in file_no_ext:
                        return os.path.join(root, file)
                    # Try matching with original font_family (for fonts with spaces/case)
                    if font_family.lower() in file.lower():
                        return os.path.join(root, file)
    # Try glob for fonts with spaces or special chars in filename
    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for ext in ("*.ttf", "*.otf"):
            for font_path in glob.glob(os.path.join(font_dir, ext)):
                base = os.path.splitext(os.path.basename(font_path))[0]
                base_norm = base.replace(" ", "").replace("-", "").replace("_", "").lower()
                if normalized_family == base_norm or normalized_family in base_norm or font_family.lower() in base.lower():
                    return font_path
    # Try to use tkinter's font actual() to get the font file (works on some systems)
    try:
        import tkinter.font as tkfont
        f = tkfont.Font(family=font_family)
        actual = f.actual()
        if "file" in actual and actual["file"]:
            return actual["file"]
    except Exception:
        pass
    return None  # Font not found

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from widgets.stock_widget import StockWidget
    from widgets.media_widget import MediaWidget
    from widgets.weather_widget import WeatherWidget
except ImportError as e:
    logger.error(f"Widget import error: {e}")
    StockWidget = None
    MediaWidget = None
    WeatherWidget = None

# This function will be called whenever the VLC player enters the paused state.
def handle_media_player_paused(event, player):
    global captured_pil_image # Declare that we are modifying the global variable

    logger.info("\n--- Player Paused ---")
    # Determine project root for snapshot path
    if getattr(sys, 'frozen', False):
        # If running as a PyInstaller executable
        project_root = os.path.dirname(sys.executable)
    else:
        # If running as a script
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    snapshot_path = os.path.join(project_root, "vlc_snapshot_temp.png")
    logger.info(f"Attempting to take snapshot to: {snapshot_path}")

    player.video_take_snapshot(0, snapshot_path, 0, 0)
    logger.info("Snapshot command issued. Waiting for file to be written...")

    # Verify if the snapshot file was successfully created
    if os.path.exists(snapshot_path):
        try:
            set_windows_wallpaper(snapshot_path)  # Set the captured image as wallpaper
            logger.info("Successfully set snapshot as wallpaper")
        except Exception as e:
            logger.error(f"Error opening or copying snapshot with PIL: {e}")
    else:
        logger.warning("Snapshot file was not found after taking snapshot. There might be an issue with VLC or permissions.")

class VideoClockScreenSaver:

    def __init__(self, master, video_path_arg=None, key_blocker_instance=None):
        logger.debug("Initializing VideoClockScreenSaver")
        try:
            self.master = master
            self.key_blocker_instance = key_blocker_instance  # Store the actual blocker instance
            master.attributes('-fullscreen', True)
            master.configure(bg='black')
            
            self.TRANSPARENT_KEY = '#010203'
            
            self.screen_width = master.winfo_screenwidth()
            self.screen_height = master.winfo_screenheight()
            
            self.user_config = load_config()
            
            system_user = getpass.getuser()
            self.username_to_display = system_user
            self.username = system_user
            
            video_path_from_config_or_default = self.user_config.get('video_path', 'video.mp4')
            actual_video_path = video_path_arg if video_path_arg else video_path_from_config_or_default
            
            if not os.path.isabs(actual_video_path):
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                actual_video_path = os.path.join(project_root, actual_video_path)
                logger.debug(f"Resolved relative video path to: {actual_video_path}")

            self.width = master.winfo_screenwidth() 
            self.height = master.winfo_screenheight()

            # Create a Frame container for VLC video
            self.video_frame = tk.Frame(master, bg='black', borderwidth=0, highlightthickness=0)
            self.video_frame.pack(fill=tk.BOTH, expand=True)

            # VLC-based video playback
            self.label = tk.Label(self.video_frame, bg='black', borderwidth=0, highlightthickness=0)
            self.label.place(x=0, y=0, width=self.width, height=self.height)

            # Overlay Toplevel window (transparent, always on top)
            self.overlay_win = tk.Toplevel(master)
            self.overlay_win.overrideredirect(True)
            self.overlay_win.attributes('-topmost', True)
            self.overlay_win.geometry(f'{self.width}x{self.height}+0+0')
            # Windows transparency
            if platform.system() == 'Windows':
                self.overlay_win.attributes('-transparentcolor', self.TRANSPARENT_KEY)
                self.overlay_win.config(bg=self.TRANSPARENT_KEY)
                self.overlay_canvas = tk.Canvas(self.overlay_win, bg=self.TRANSPARENT_KEY, highlightthickness=0, borderwidth=0)
            else:
                self.overlay_win.config(bg='black')
                self.overlay_canvas = tk.Canvas(self.overlay_win, bg='black', highlightthickness=0, borderwidth=0)
            self.overlay_canvas.place(x=0, y=0, width=self.width, height=self.height)

            # Make overlay window non-interactive but keep it visible
            # Remove the -disabled attribute as we're using WS_EX_TRANSPARENT instead
            if platform.system() == 'Windows':
                self.overlay_win.wm_attributes("-disabled", False)
            
            # Ensure main window can receive all key events
            master.focus_force()
            master.bind("<Key>", self._on_key_event)
            master.bind("<KeyPress>", self._on_key_event)
            master.bind("<Button-1>", self._on_click_event)
            master.bind("<Button-2>", self._on_click_event)
            master.bind("<Button-3>", self._on_click_event)
            
            # Also bind to video frame and label to ensure events are captured
            self.video_frame.bind("<Key>", self._on_key_event)
            self.video_frame.bind("<KeyPress>", self._on_key_event)
            self.video_frame.bind("<Button-1>", self._on_click_event)
            self.label.bind("<Key>", self._on_key_event)
            self.label.bind("<KeyPress>", self._on_key_event)
            self.label.bind("<Button-1>", self._on_click_event)

            self.overlay_canvas.bind("<Button-1>", self._on_click_event)
            self.overlay_canvas.focus_force()
            # Load clock font settings from config
            self.clock_font_family = self.user_config.get("clock_font_family", "Segoe UI Emoji")
            self.clock_font_size = self.user_config.get("clock_font_size", 64)

            # Load UI font settings from config
            self.ui_font_family = self.user_config.get("ui_font_family", "Arial")
            self.ui_font_size = self.user_config.get("ui_font_size", 30)

            font_path_used = None
            try:
                font_path = find_font_path(self.clock_font_family)
                if font_path:
                    self.clock_font = ImageFont.truetype(font_path, self.clock_font_size)
                    font_path_used = font_path
                    logger.debug(f"Using clock font file: {font_path}")
                else:
                    self.clock_font = ImageFont.truetype(self.clock_font_family, self.clock_font_size)
                    font_path_used = self.clock_font_family
                    logger.debug(f"Using clock font family: {self.clock_font_family}")
            except Exception as e:
                logger.warning(f"Warning: Clock font '{self.clock_font_family}' not found. Using PIL default. ({e})")
                self.clock_font = ImageFont.load_default()

            try:
                ui_font_path = find_font_path(self.ui_font_family)
                if ui_font_path:
                    self.profile_name_font = ImageFont.truetype(ui_font_path, self.ui_font_size)
                    self.profile_initial_font = ImageFont.truetype(ui_font_path, self.ui_font_size * 2)
                    logger.debug(f"Using UI font file: {ui_font_path}")
                else:
                    self.profile_name_font = ImageFont.truetype(self.ui_font_family, self.ui_font_size)
                    self.profile_initial_font = ImageFont.truetype(self.ui_font_family, self.ui_font_size * 2)
                    logger.debug(f"Using UI font family: {self.ui_font_family}")
            except Exception as e:
                logger.warning(f"Warning: UI font '{self.ui_font_family}' not found. Using PIL default. ({e})")
                self.profile_name_font = ImageFont.load_default()
                self.profile_initial_font = ImageFont.load_default()

            self.profile_pic_size = 80
            self.pre_rendered_profile_pic = None
            self.pre_rendered_username_label = None
            self.profile_pic_pos = (0,0)
            self.username_label_pos = (0,0)
            self.profile_pic_is_gif = False
            self.profile_pic_gif_frames = []
            self.profile_pic_gif_frame_index = 0
            self.profile_pic_gif_last_update = 0
            self.profile_pic_gif_duration = 100

            self.current_time_text = time.strftime('%I:%M:%S %p')
            self.last_clock_update = 0
            self.clock_x = 0
            self.clock_y = 0
            self.clock_text_width = 0

            self.first_frame_received = False
            self.widgets = []
            
            # Add flag to control focus management
            self.focus_management_active = True
      
            self.master.after(100, self.init_widgets)

            # VLC setup
            vlc_options = [
                '--no-osd',              # Disable On-Screen Display (OSD)
                '--no-snapshot-preview'  # Disable the snapshot preview thumbnail
            ]

            self.vlc_instance = vlc.Instance(vlc_options)
            self.vlc_player = self.vlc_instance.media_player_new()
            self.media = self.vlc_instance.media_new(actual_video_path)
            self.vlc_player.set_media(self.media)
            # Embed VLC video output into Tkinter Label
            self.vlc_player.set_hwnd(self.label.winfo_id())
            # Mute VLC player to remove sound
            self.vlc_player.audio_set_mute(True)
            
            # Configure video scaling to fill entire screen (removes black bars)
            # Set aspect ratio to match screen dimensions to stretch video
            screen_aspect = f"{self.screen_width}:{self.screen_height}"
            self.vlc_player.video_set_aspect_ratio(screen_aspect.encode('utf-8'))
            
            # Set video to stretch to fill the window completely
            self.vlc_player.video_set_scale(0)  # 0 = fit to window, stretching if necessary
            
            # Enable video looping
            media_list = self.vlc_instance.media_list_new([actual_video_path])
            media_list_player = self.vlc_instance.media_list_player_new()
            media_list_player.set_media_list(media_list)
            media_list_player.set_media_player(self.vlc_player)
            media_list_player.set_playback_mode(vlc.PlaybackMode.loop)
            self.media_list_player = media_list_player  # Store reference
            
            # Initialize UI elements immediately for VLC playback
            self._initialize_ui_elements_immediately()

            # Start playback with looping
            # Read last_video_timestamp from config (default to 0.0 if not present)
            last_video_timestamp = 0.0
            try:
                last_video_timestamp = float(self.user_config.get("last_video_timestamp", 0.0))
            except Exception as e:
                logger.warning(f"Could not parse last_video_timestamp from config: {e}")

            self.media_list_player.play()

            # Start video from last_video_timestamp (skip initial video)
            if last_video_timestamp > 0:
                # Wait briefly to ensure playback has started before seeking
                def seek_to_last_timestamp():
                    try:
                        if hasattr(self, 'vlc_player') and self.vlc_player:
                            self.vlc_player.set_time(int(last_video_timestamp * 1000))
                            logger.info(f"Seeked video to {last_video_timestamp} seconds")
                    except Exception as e:
                        logger.error(f"Error seeking to last_video_timestamp: {e}")
                self.master.after(0, seek_to_last_timestamp)
            
            # Additional video scaling configuration after playback starts
            def configure_video_after_start():
                try:
                    # Ensure video fills the entire window by setting crop geometry
                    self.vlc_player.video_set_crop_geometry(None)  # Remove any cropping
                    # Force aspect ratio again after video starts
                    self.vlc_player.video_set_aspect_ratio(screen_aspect.encode('utf-8'))
                except Exception as e:
                    logger.warning(f"Could not configure video scaling: {e}")
            
            # Schedule video configuration after a short delay to ensure video has started
            self.master.after(500, configure_video_after_start)
            
            # Get the event manager for the media player. This allows us to subscribe to events.
            event_manager = self.vlc_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerPaused, handle_media_player_paused, self.vlc_player)

            # Schedule overlays and ensure focus
            self.master.after(0, self.update_overlays)
            # Use a different approach - schedule periodic focus checks through update_overlays instead
            # Initial call to black out monitors, delayed slightly for fullscreen to establish
            if WINDOWS_MULTI_MONITOR_SUPPORT:
                self.master.after(0, lambda: update_secondary_monitor_blackouts(self.master))

                # Set up the Windows event hook for display changes using ctypes directly
                try:
                    # Convert Python callback to C callback
                    callback_ref = WinEventProcType(WinEventProcCallback)
                    
                    hWinEventHook = SetWinEventHook(
                        EVENT_SYSTEM_DISPLAYSETTINGSCHANGED, # Event Min - using our defined constant
                        EVENT_SYSTEM_DISPLAYSETTINGSCHANGED, # Event Max - using our defined constant
                        0, # hmodWinEventProc
                        callback_ref, # Callback function
                        0, # idProcess
                        0, # idThread
                        win32con.WINEVENT_OUTOFCONTEXT | win32con.WINEVENT_SKIPOWNPROCESS
                    )            
                    if not hWinEventHook:
                        logger.warning("Failed to set event hook")
                except Exception as e:
                    logger.error(f"Error setting up display change event hook: {e}")
                    hWinEventHook = None
            
            # Remove the old key bindings since VideoClockScreenSaver now handles them internally
            # The app now handles key events internally through _on_key_event and _on_click_event
            
            # Make sure the root window can receive focus for key events
            self.master.focus_set()
            self.master.focus_force()
            global ctrl_alt_del_detector
            ctrl_alt_del_detector = None
            
            # Force an immediate focus check to counter any startup focus stealing
            self.master.after(0, self._check_and_restore_focus)
    
        except Exception as e:
            logger.error(f"Exception in __init__: {e}")

    def _check_and_restore_focus(self):
        """Check and restore focus if needed - called from update_overlays"""
        try:
            if not self.focus_management_active:
                return
                
            if hasattr(self, 'master') and self.master and self.master.winfo_exists():
                current_focus = self.master.focus_get()
                if current_focus != self.master:
                    self.master.focus_set()
                    self.master.focus_force()
                    self.master.tkraise()
        except (tk.TclError, AttributeError):
            # Window destroyed or other Tkinter error - ignore
            pass
        except Exception as e:
            logger.error(f"Error in _check_and_restore_focus: {e}")

    def _on_key_event(self, event):
        """Handle all key events"""
        # logger.debug(f"Key event detected: {event.keysym}")
        if event.keysym in ['Escape', 'Return', 'KP_Enter', 'space']:
            self._trigger_password_dialog(event)
        return "break"  # Prevent further propagation

    def _on_click_event(self, event):
        """Handle click events"""
        logger.debug("Click event detected")
        self._trigger_password_dialog(event)
        return "break"  # Prevent further propagation

    def _trigger_password_dialog(self, event):
        """Trigger the password dialog"""
        try:
            global hWinEventHook
            global secondary_screen_windows
            global root_ref_for_hook
            # Import here to avoid circular imports
            from screensaver_app.PasswordConfig import verify_password_dialog_macos
            
            logger.info(f"Password dialog triggered by: {event.keysym if hasattr(event, 'keysym') else 'mouse click'}")
            
            # Pause focus management to prevent interference with dialog
            self.focus_management_active = False
            
            # Pause video before showing dialog
            VideoClockScreenSaver.pause_video(self)
            
            # Show password dialog
            success = verify_password_dialog_macos(self.master, video_clock_screensaver=self)
            logger.info(f"Password dialog returned success: {success}")
            # if success:
            #     logger.info("Password verification successful, closing screensaver")
            #     self.close()
            #     # The calling code will handle cleanup and restart
            # else:
            #     logger.info("Password verification failed, resuming video")
            #     # Resume focus management and restore focus
            #     self.focus_management_active = True
            #     self.master.focus_force()
            if success: 
                logger.info("Password verification successful, closing screensaver")
                self.master.destroy()  # Changed from self.master.close()
                if hWinEventHook: # Unhook before destroying windows
                    try:
                        UnhookWinEvent(hWinEventHook)  # Use ctypes function
                    except Exception as e_unhook:
                        logger.error(f"Error unhooking display event: {e_unhook}")
                    hWinEventHook = None
                root_ref_for_hook = None

                # Stop Ctrl+Alt+Del detector
                if ctrl_alt_del_detector:
                    ctrl_alt_del_detector.restart_pending = True  # Prevent restart during shutdown

                for sec_win in secondary_screen_windows:
                    if sec_win.winfo_exists():
                        sec_win.destroy()
                secondary_screen_windows = []
                
                # Add key blocker cleanup before quitting application
                logger.info("Performing key blocker cleanup to ensure all blocking is disabled...")
                try:
                    # Use the actual key blocker instance that was passed from PhotoEngine
                    if self.key_blocker_instance:
                        logger.info("Using passed key blocker instance for cleanup")
                        if hasattr(self.key_blocker_instance, 'stop_blocking'):
                            # Enhanced blocker
                            self.key_blocker_instance.stop_blocking()
                            logger.info("Enhanced blocker cleanup completed via passed instance.")
                        elif hasattr(self.key_blocker_instance, 'disable_all_blocking'):
                            # Basic blocker
                            self.key_blocker_instance.disable_all_blocking()
                            logger.info("Basic blocker cleanup completed via passed instance.")
                        else:
                            logger.warning("Passed key blocker instance doesn't have expected cleanup methods")
                    else:
                        logger.info("No key blocker instance passed, attempting fallback cleanup")
                        # Fallback: Try to import the same KeyBlocker that might have been used
                        try:
                            from utils.enhanced_key_blocker import EnhancedKeyBlocker as CleanupBlocker
                            cleanup_blocker = CleanupBlocker(debug_print=True)
                            if hasattr(cleanup_blocker, 'python_blocker') and cleanup_blocker.python_blocker:
                                cleanup_blocker.python_blocker.disable_all_blocking()
                                logger.info("Enhanced blocker cleanup completed via fallback.")
                        except ImportError:
                            from utils.key_blocker import KeyBlocker as CleanupBlocker
                            cleanup_blocker = CleanupBlocker(debug_print=True)
                            cleanup_blocker.disable_all_blocking()
                            logger.info("Basic blocker cleanup completed via fallback.")
                except Exception as e:
                    logger.warning(f"Error during key blocker cleanup: {e}")
                
                # --- Relaunch tray with same elevation ---
                try:
                    logger.info("Attempting to restart system tray after successful screensaver login...")
                    # Refactored for PyInstaller one-folder logic
                    if getattr(sys, 'frozen', False):
                        # For frozen executable, use the executable directly
                        python_exe = sys.executable
                        script_args = "--min --no-elevate"
                        logger.debug(f"Detected frozen executable. python_exe={python_exe}, args={script_args}")
                    else:
                        # For script mode
                        # Find PhotoEngine.py path relative to this file
                        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
                        script_path = os.path.join(project_root, "PhotoEngine.py")
                        python_exe = sys.executable
                        script_args = f'"{script_path}" --min --no-elevate'
                        logger.debug(f"Detected script mode. python_exe={python_exe}, args={script_args}")

                    # Check if we're running as admin and preserve elevation
                    if is_admin():
                        logger.info("Restarting tray with admin privileges...")
                        import ctypes
                        logger.debug(f"Using ShellExecuteW to restart tray with: {python_exe} {script_args}")
                        # Use ShellExecuteW to maintain admin privileges
                        result = ctypes.windll.shell32.ShellExecuteW(
                            None,
                            "runas",
                            python_exe,
                            script_args,
                            None,
                            0  # SW_HIDE
                        )
                        logger.debug(f"ShellExecuteW result: {result}")
                        if result <= 32:  # ShellExecuteW returns > 32 for success
                            logger.error(f"ShellExecuteW failed with result: {result}")
                    else:
                        logger.info("Restarting tray without admin privileges...")
                        if getattr(sys, 'frozen', False):
                            # For frozen executable
                            cmd_args = [python_exe, "--min", "--no-elevate"]
                        else:
                            # For script mode
                            # Find PhotoEngine.py path relative to this file
                            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
                            script_path = os.path.join(project_root, "PhotoEngine.py")
                            cmd_args = [python_exe, script_path, "--min", "--no-elevate"]
                        
                        logger.debug(f"Using subprocess.Popen to restart tray: {cmd_args}")
                        proc = subprocess.Popen(cmd_args,
                                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0)
                        logger.debug(f"subprocess.Popen returned pid: {proc.pid if proc else 'unknown'}")

                    logger.info("New tray process started, exiting current process.")
                    # Add a small delay to ensure the new process starts before we exit
                    time.sleep(1)
                    os._exit(0)
                except Exception as e:
                    logger.error(f"Failed to restart tray after login: {e}", exc_info=True)
            else:
                logger.info("Password verification failed, resuming video")
                VideoClockScreenSaver.resume_video(self)
                # Resume focus management and restore focus
                self.focus_management_active = True
                self.master.focus_force()
                
        except Exception as e:
            logger.error(f"Error in _trigger_password_dialog: {e}")
            # Ensure focus management is resumed even if there's an error
            self.focus_management_active = True

    def _initialize_ui_elements_immediately(self):
        logger.debug("Called _initialize_ui_elements_immediately")
        try:
            """Initialize UI elements immediately for VLC playback"""
            # Use screen dimensions since VLC handles video scaling
            self.width = self.screen_width
            self.height = self.screen_height
            
            self.profile_center_x = self.width // 2
            self.profile_name_y_base = int(self.height * 0.85) 
            self.profile_pic_y_base = self.profile_name_y_base - self.profile_pic_size - 10

            self.pre_rendered_profile_pic = self._create_pre_rendered_profile_pic()
            self.pre_rendered_username_label = self._create_pre_rendered_username_label()
            
            # GIF setup: if GIF frames exist, initialize timing
            if self.profile_pic_is_gif and self.profile_pic_gif_frames:
                self.profile_pic_gif_frame_index = 0
                self.profile_pic_gif_last_update = int(time.time() * 1000)
            
            self.profile_pic_pos = (self.profile_center_x - self.profile_pic_size // 2, self.profile_pic_y_base)
            label_width = self.pre_rendered_username_label.width
            self.username_label_pos = (self.profile_center_x - label_width // 2, self.profile_name_y_base)
            
            # Calculate initial clock position
            try: 
                clock_bbox = self.clock_font.getbbox(self.current_time_text)
                self.clock_text_width = clock_bbox[2] - clock_bbox[0]
            except AttributeError: 
                self.clock_text_width, _ = self.clock_font.getsize(self.current_time_text)
            
            self.clock_x = (self.width - self.clock_text_width) // 2
            self.clock_y = int(self.height * 0.1)
            
            self.first_frame_received = True
        except Exception as e:
            logger.error(f"Exception in _initialize_ui_elements_immediately: {e}")

    def init_widgets(self):
        logger.debug("Called init_widgets")
        try:
            """Initialize widgets based on configuration - optimized for faster startup"""
            config = load_config()
            
            screen_w = self.master.winfo_screenwidth()
            screen_h = self.master.winfo_screenheight()
            
            def create_widgets_async():
                """Create widgets in separate thread with optimized timing"""
                try:
                    # Reduced delay for faster startup
                    time.sleep(3)  # Reduced from 5
                    
                    widgets_to_create = []
                    
                    # Prepare weather widget creation (highest priority - lightweight)
                    if config.get("enable_weather_widget", True) and WeatherWidget:
                        pincode = config.get("weather_pincode", "400068")
                        country = config.get("weather_country", "IN")
                        widgets_to_create.append(("weather", (pincode, country)))
                    
                    # Prepare stock widget creation (medium priority)
                    if config.get("enable_stock_widget", False) and StockWidget:
                        widgets_to_create.append(("stock", config.get("stock_market", "NASDAQ")))
                    
                    # Prepare media widget creation (lower priority - more resource intensive)
                    if config.get("enable_media_widget", False) and MediaWidget:
                        widgets_to_create.append(("media", None))
                    
                    # Create widgets with minimal staggering for faster startup
                    for i, (widget_type, param) in enumerate(widgets_to_create):
                        if i > 0:
                            time.sleep(0.2)  # Reduced from 0.8
                        
                        # Schedule widget creation on main thread
                        if widget_type == "weather":
                            pincode, country = param
                            self.master.after(0, lambda p=pincode, c=country: self._create_weather_widget(p, c, screen_w, screen_h))
                        elif widget_type == "stock":
                            self.master.after(0, lambda market=param: self._create_stock_widget(market, screen_w, screen_h))
                        elif widget_type == "media":
                            time.sleep(0.1)  # Reduced delay for media widget
                            self.master.after(0, lambda: self._create_media_widget(screen_w, screen_h))
                            
                except Exception as e:
                    logger.error(f"Error in async widget creation: {e}")
            
            # Start widget creation in separate thread
            widget_thread = threading.Thread(target=create_widgets_async, daemon=True)
            widget_thread.start()
        except Exception as e:
            logger.error(f"Exception in init_widgets: {e}")

    def _create_weather_widget(self, pincode, country, screen_w, screen_h):
        logger.debug(f"Called _create_weather_widget with pincode={pincode}, country={country}")
        try:
            """Create weather widget on main thread and make it sticky"""
            weather_widget_toplevel = WeatherWidget(
                self.master, 
                self.TRANSPARENT_KEY, 
                screen_width=screen_w,
                screen_height=screen_h,
                pincode=pincode,
                country_code=country
            )
            # Make weather widget sticky (always on top)
            try:
                weather_widget_toplevel.window.attributes('-topmost', True)
                def keep_weather_widget_on_top():
                    if hasattr(weather_widget_toplevel, 'window') and weather_widget_toplevel.window.winfo_exists():
                        weather_widget_toplevel.window.attributes('-topmost', True)
                        self.master.after(1000, keep_weather_widget_on_top)
                self.master.after(1000, keep_weather_widget_on_top)
            except Exception as e:
                logger.warning(f"Could not set weather widget always on top: {e}")
            self.widgets.append(weather_widget_toplevel)
            logger.info(f"Weather widget created for {pincode}, {country}.")
        except Exception as e:
            logger.error(f"Exception in _create_weather_widget: {e}")

    def _create_stock_widget(self, market, screen_w, screen_h):
        logger.debug(f"Called _create_stock_widget with market={market}")
        try:
            """Create stock widget on main thread and make it sticky"""
            # Get the market from config, not symbols
            market_from_config = self.user_config.get("stock_market", "NASDAQ")
            stock_widget_toplevel = StockWidget(
                self.master, 
                self.TRANSPARENT_KEY, 
                screen_width=screen_w,
                screen_height=screen_h,
                initial_market=market_from_config,  # Use the market from config
                symbols=None  # Let the widget determine symbols based on market
            )
            # Make stock widget sticky (always on top)
            try:
                stock_widget_toplevel.window.attributes('-topmost', True)
                def keep_stock_widget_on_top():
                    if hasattr(stock_widget_toplevel, 'window') and stock_widget_toplevel.window.winfo_exists():
                        stock_widget_toplevel.window.attributes('-topmost', True)
                        self.master.after(1000, keep_stock_widget_on_top)
                self.master.after(1000, keep_stock_widget_on_top)
            except Exception as e:
                logger.warning(f"Could not set stock widget always on top: {e}")
            self.widgets.append(stock_widget_toplevel)
            logger.info(f"Stock widget (Toplevel) for {market_from_config} created.")
        except Exception as e:
            logger.error(f"Exception in _create_stock_widget: {e}")
        
    def _create_media_widget(self, screen_w, screen_h):
        logger.debug("Called _create_media_widget")
        try:
            """Create media widget on main thread and make it sticky"""
            media_widget_toplevel = MediaWidget(
                self.master, 
                self.TRANSPARENT_KEY,
                screen_width=screen_w,
                screen_height=screen_h
            )
            # Make media widget sticky (always on top)
            try:
                media_widget_toplevel.window.attributes('-topmost', True)
                def keep_media_widget_on_top():
                    if hasattr(media_widget_toplevel, 'window') and media_widget_toplevel.window.winfo_exists():
                        media_widget_toplevel.window.attributes('-topmost', True)
                        self.master.after(1000, keep_media_widget_on_top)
                self.master.after(1000, keep_media_widget_on_top)
            except Exception as e:
                logger.warning(f"Could not set media widget always on top: {e}")
            self.widgets.append(media_widget_toplevel)
            logger.info(f"Media widget (Toplevel) created.")
        except Exception as e:
            logger.error(f"Exception in _create_media_widget: {e}")

    def _initialize_ui_elements_after_first_frame(self, frame_width, frame_height):
        logger.debug(f"Called _initialize_ui_elements_after_first_frame with frame_width={frame_width}, frame_height={frame_height}")
        try:
            self.width = frame_width
            self.height = frame_height
            self.profile_center_x = self.width // 2
            self.profile_name_y_base = int(self.height * 0.85) 
            self.profile_pic_y_base = self.profile_name_y_base - self.profile_pic_size - 10

            self.pre_rendered_profile_pic = self._create_pre_rendered_profile_pic()
            self.pre_rendered_username_label = self._create_pre_rendered_username_label()
            # GIF setup: if GIF frames exist, initialize timing
            if self.profile_pic_is_gif and self.profile_pic_gif_frames:
                self.profile_pic_gif_frame_index = 0
                self.profile_pic_gif_last_update = int(time.time() * 1000)
            
            self.profile_pic_pos = (self.profile_center_x - self.profile_pic_size // 2, self.profile_pic_y_base)
            label_width = self.pre_rendered_username_label.width
            self.username_label_pos = (self.profile_center_x - label_width // 2, self.profile_name_y_base)
            
            # Calculate initial clock position
            try: 
                clock_bbox = self.clock_font.getbbox(self.current_time_text)
                self.clock_text_width = clock_bbox[2] - clock_bbox[0]
            except AttributeError: 
                self.clock_text_width, _ = self.clock_font.getsize(self.current_time_text)
            
            self.clock_x = (self.width - self.clock_text_width) // 2
            self.clock_y = int(self.height * 0.1)
            
            self.first_frame_received = True
        except Exception as e:
            logger.error(f"Exception in _initialize_ui_elements_after_first_frame: {e}")

    def _create_pre_rendered_profile_pic(self):
        logger.debug("Called _create_pre_rendered_profile_pic")
        try:
            size = self.profile_pic_size
            # Use profile_pic_path for GIF, otherwise fallback to profile_pic_path_crop or profile_pic_path
            config_pic_path = self.user_config.get("profile_pic_path", "")
            config_pic_crop_path = self.user_config.get("profile_pic_path_crop", "")
            custom_pic_path = ""

            if config_pic_crop_path:
                if not os.path.isabs(config_pic_crop_path):
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                    custom_pic_path = os.path.join(project_root, config_pic_crop_path)
                else:
                    custom_pic_path = config_pic_crop_path
            elif config_pic_path:
                if not os.path.isabs(config_pic_path):
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                    custom_pic_path = os.path.join(project_root, config_pic_path)
                else:
                    custom_pic_path = config_pic_path

            loaded_custom_image = None
            # GIF support
            self.profile_pic_is_gif = False
            self.profile_pic_gif_frames = []
            self.profile_pic_gif_duration = 100
            if custom_pic_path and os.path.exists(custom_pic_path):
                try:
                    if custom_pic_path.lower().endswith('.gif'):
                        gif = Image.open(custom_pic_path)
                        self.profile_pic_is_gif = True
                        self.profile_pic_gif_frames = []
                        durations = []
                        try:
                            while True:
                                frame = gif.convert("RGBA")
                                # Make square, but use transparent background (no black border)
                                square_img = Image.new('RGBA', (max(frame.width, frame.height), max(frame.width, frame.height)), (0,0,0,0))
                                paste_x = (square_img.width - frame.width) // 2
                                paste_y = (square_img.height - frame.height) // 2
                                square_img.paste(frame, (paste_x, paste_y))
                                square_img = square_img.resize((size, size), Image.Resampling.LANCZOS)
                                # Circular mask
                                mask = Image.new('L', (size, size), 0)
                                draw_mask = ImageDraw.Draw(mask)
                                draw_mask.ellipse((0, 0, size, size), fill=255)
                                circular_img = Image.new('RGBA', (size, size), (0,0,0,0))
                                circular_img.paste(square_img, (0, 0))
                                circular_img.putalpha(mask)
                                self.profile_pic_gif_frames.append(circular_img)
                                # Collect duration for each frame
                                durations.append(gif.info.get('duration', 100))
                                gif.seek(gif.tell() + 1)
                        except EOFError:
                            pass
                        # Use the minimum duration for smoothest animation, but not less than 20ms
                        if durations:
                            self.profile_pic_gif_duration = max(min(durations), 20)
                        if self.profile_pic_gif_frames:
                            loaded_custom_image = self.profile_pic_gif_frames[0]
                    else:
                        img = Image.open(custom_pic_path).convert("RGBA")
                        square_img = Image.new('RGBA', (max(img.width, img.height), max(img.width, img.height)), (0,0,0,0))
                        paste_x = (square_img.width - img.width) // 2
                        paste_y = (square_img.height - img.height) // 2
                        square_img.paste(img, (paste_x, paste_y))
                        square_img = square_img.resize((size, size), Image.Resampling.LANCZOS)
                        mask = Image.new('L', (size, size), 0)
                        draw_mask = ImageDraw.Draw(mask)
                        draw_mask.ellipse((0, 0, size, size), fill=255)
                        circular_img = Image.new('RGBA', (size, size), (0,0,0,0))
                        circular_img.paste(square_img, (0, 0))
                        circular_img.putalpha(mask)
                        loaded_custom_image = circular_img
                except Exception as e:
                    logger.error(f"Error loading or processing custom profile picture '{custom_pic_path}': {e}")
                    loaded_custom_image = None

            if loaded_custom_image:
                return loaded_custom_image

            # Default profile picture (circular gradient)
            image = Image.new('RGBA', (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(image)
            
            for i in range(size):
                for j in range(size):
                    distance_from_center = ((i - size//2)**2 + (j - size//2)**2)**0.5
                    if distance_from_center <= size//2:
                        r_val = int(80 + (i / size) * 120); g_val = int(120 + (j / size) * 100)
                        b_val = 230; alpha_val = 180
                        draw.point((i,j), fill=(r_val, g_val, b_val, alpha_val))
            
            initial = self.username[0].upper() if self.username else "U"
            try: 
                bbox = self.profile_initial_font.getbbox(initial)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                text_x_offset, text_y_offset = bbox[0], bbox[1]
            except AttributeError: 
                text_width, text_height = self.profile_initial_font.getsize(initial)
                text_x_offset, text_y_offset = 0, 0

            text_x = (size - text_width) / 2 - text_x_offset
            text_y = (size - text_height) / 2 - text_y_offset -3 
            draw.text((text_x, text_y), initial, fill=(255, 255, 255, 220), font=self.profile_initial_font)
            return image
        except Exception as e:
            logger.error(f"Exception in _create_pre_rendered_profile_pic: {e}")

    def _create_pre_rendered_username_label(self):
        logger.debug("Called _create_pre_rendered_username_label")
        try:
            """Create the username label below the profile picture."""
            name_text = self.username

            # Always use the configured UI font and size for the username label
            try:
                ui_font_path = find_font_path(self.ui_font_family)
                if ui_font_path:
                    username_font = ImageFont.truetype(ui_font_path, self.ui_font_size)
                else:
                    username_font = ImageFont.truetype(self.ui_font_family, self.ui_font_size)
            except Exception:
                username_font = ImageFont.load_default().font_variant(size=self.ui_font_size)

            try:
                bbox = username_font.getbbox(name_text)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                text_x_offset, text_y_offset = bbox[0], bbox[1]
            except AttributeError:
                text_width, text_height = username_font.getsize(name_text)
                text_x_offset, text_y_offset = 0, 0

            padding = 15  # Increased padding for better appearance
            rect_width = text_width + 2 * padding
            rect_height = text_height + 2 * padding

            image = Image.new('RGBA', (int(rect_width), int(rect_height)), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            # Make the background transparent and remove the border
            draw_rounded_rectangle(draw, (0, 0, rect_width - 1, rect_height - 1),
                                   radius=12, fill=(0, 0, 0, 0), outline=None, width=0)

            draw.text((padding - text_x_offset, padding - text_y_offset),
                      name_text, font=username_font, fill=(255, 255, 255, 255))
            return image
        except Exception as e:
            logger.error(f"Exception in _create_pre_rendered_username_label: {e}")

    def _process_frame_with_ui(self, pil_img):
        logger.debug("Called _process_frame_with_ui")
        try:
            """Optimized frame processing with minimal overhead"""
            # Store the raw frame before adding UI elements
            self.last_raw_frame = pil_img.copy()

            if not self.first_frame_received:
                # This path is taken for the very first frame.
                # self.clock_x and self.clock_y are not used yet for drawing here.
                return pil_img
                
            frame = pil_img

            # Profile pic rendering (GIF support)
            profile_pic_img = self.pre_rendered_profile_pic
            if self.profile_pic_is_gif and self.profile_pic_gif_frames:
                now_ms = int(time.time() * 1000)
                if now_ms - self.profile_pic_gif_last_update >= self.profile_pic_gif_duration:
                    self.profile_pic_gif_frame_index = (self.profile_pic_gif_frame_index + 1) % len(self.profile_pic_gif_frames)
                    self.profile_pic_gif_last_update = now_ms
                profile_pic_img = self.profile_pic_gif_frames[self.profile_pic_gif_frame_index]

            if profile_pic_img and self.pre_rendered_username_label:
                profile_pic_pos_int = (int(self.profile_pic_pos[0]), int(self.profile_pic_pos[1]))
                username_label_pos_int = (int(self.username_label_pos[0]), int(self.username_label_pos[1]))
                frame.paste(profile_pic_img, profile_pic_pos_int, profile_pic_img)
                frame.paste(self.pre_rendered_username_label, username_label_pos_int, self.pre_rendered_username_label)

            # Highly optimized clock rendering - update less frequently
            current_time_ms = int(time.time() * 1000)
            if current_time_ms - self.last_clock_update >= 1000:  # Update every second
                new_time_text = time.strftime('%I:%M:%S %p')
                if new_time_text != self.current_time_text:  # Only update if time actually changed
                    self.current_time_text = new_time_text
                    
                    # Cache clock dimensions - ensure we have width and height before calculating position
                    try: 
                        clock_bbox = self.clock_font.getbbox(self.current_time_text)
                        self.clock_text_width = clock_bbox[2] - clock_bbox[0]
                    except AttributeError: 
                        self.clock_text_width, _ = self.clock_font.getsize(self.current_time_text)
                    
                    # Only calculate position if we have valid frame dimensions
                    # self.width and self.height should be correctly set by _initialize_ui_elements_after_first_frame
                    if self.width > 0 and self.height > 0:
                        self.clock_x = (self.width - self.clock_text_width) // 2
                        self.clock_y = int(self.height * 0.1)
                    # The else fallback for clock_x=50 is less likely to be needed now for initial positioning.
                    # else:
                    #     self.clock_x = 50 
                    #     self.clock_y = 50
                
                self.last_clock_update = current_time_ms
            
            # Draw clock with cached positions - self.clock_x and self.clock_y should be correctly initialized
            # by _initialize_ui_elements_after_first_frame before this drawing part is reached for the first time with UI.
            draw = ImageDraw.Draw(frame)
            shadow_offset = 2
            draw.text((int(self.clock_x + shadow_offset), int(self.clock_y + shadow_offset)), 
                     self.current_time_text, font=self.clock_font, fill=(0,0,0,128))
            draw.text((int(self.clock_x), int(self.clock_y)), 
                     self.current_time_text, font=self.clock_font, fill=(255,255,255,220))
            
            return frame
        except Exception as e:
            logger.error(f"Exception in _process_frame_with_ui: {e}")

    def update_overlays(self):
        # logger.debug("Called update_overlays")
        try:
            """Draw overlays (clock, profile, widgets) over VLC video using a transparent Canvas."""
            # Ensure overlay window is properly configured and stays on top
            if platform.system() == 'Windows':
                self.overlay_win.config(bg=self.TRANSPARENT_KEY)
                self.overlay_canvas.config(bg=self.TRANSPARENT_KEY)
                # Ensure overlay stays on top and non-interactive
                self.overlay_win.attributes('-topmost', True)
                self.overlay_win.wm_attributes("-disabled", False)
            
            # Clear previous overlays
            self.overlay_canvas.delete('all')

            # Only proceed if UI elements are initialized
            if not self.first_frame_received:
                self.master.after(30, self.update_overlays)
                return

            # Update clock text if needed
            current_time_ms = int(time.time() * 1000)
            if current_time_ms - self.last_clock_update >= 1000:
                new_time_text = time.strftime('%I:%M:%S %p')
                if new_time_text != self.current_time_text:
                    self.current_time_text = new_time_text
                    try:
                        clock_bbox = self.clock_font.getbbox(self.current_time_text)
                        self.clock_text_width = clock_bbox[2] - clock_bbox[0]
                    except AttributeError:
                        self.clock_text_width, _ = self.clock_font.getsize(self.current_time_text)
                    if self.width > 0 and self.height > 0:
                        self.clock_x = (self.width - self.clock_text_width) // 2
                        self.clock_y = int(self.height * 0.1)
                self.last_clock_update = current_time_ms

            # Render clock with PIL and display on canvas
            clock_img = Image.new('RGBA', (self.clock_text_width+20, self.clock_font_size+20), (0,0,0,0))
            draw = ImageDraw.Draw(clock_img)
            shadow_offset = 2
            draw.text((shadow_offset, shadow_offset), self.current_time_text, font=self.clock_font, fill=(0,0,0,128))
            draw.text((0, 0), self.current_time_text, font=self.clock_font, fill=(255,255,255,220))
            self.clock_tk_img = ImageTk.PhotoImage(clock_img)
            self.overlay_canvas.create_image(self.clock_x, self.clock_y, anchor='nw', image=self.clock_tk_img)

            # Profile pic and username rendering
            if self.pre_rendered_profile_pic and self.pre_rendered_username_label:
                # Handle GIF animation
                profile_pic_img = self.pre_rendered_profile_pic
                if self.profile_pic_is_gif and self.profile_pic_gif_frames:
                    now_ms = int(time.time() * 1000)
                    if now_ms - self.profile_pic_gif_last_update >= self.profile_pic_gif_duration:
                        self.profile_pic_gif_frame_index = (self.profile_pic_gif_frame_index + 1) % len(self.profile_pic_gif_frames)
                        self.profile_pic_gif_last_update = now_ms
                    profile_pic_img = self.profile_pic_gif_frames[self.profile_pic_gif_frame_index]
                
                self.profile_pic_tk_img = ImageTk.PhotoImage(profile_pic_img)
                self.overlay_canvas.create_image(self.profile_pic_pos[0], self.profile_pic_pos[1], anchor='nw', image=self.profile_pic_tk_img)
                
                self.username_label_tk_img = ImageTk.PhotoImage(self.pre_rendered_username_label)
                self.overlay_canvas.create_image(self.username_label_pos[0], self.username_label_pos[1], anchor='nw', image=self.username_label_tk_img)

            # Ensure main window maintains focus for key events
            if not hasattr(self, '_focus_check_count'):
                self._focus_check_count = 0
            
            # Reduce frequency of focus checks and only when focus management is active
            if self._focus_check_count % 33 == 0 and self.focus_management_active:  # Check every ~1 second (33 * 30ms)
                self._check_and_restore_focus()
            self._focus_check_count += 1

            # Schedule next overlay update
            self.master.after(30, self.update_overlays)
        except Exception as e:
            logger.error(f"Exception in update_overlays: {e}")

    def close(self):        
        logger.debug("Called close")
        try:
            """Clean shutdown of the screensaver"""
            logger.info("Closing VideoClockScreenSaver and its widgets...")
            # Clean up widgets        
            if hasattr(self, 'widgets'):
                for widget in self.widgets:
                    if hasattr(widget, 'destroy') and callable(widget.destroy):
                        widget.destroy()
                self.widgets.clear()
            else:
                logger.warning("No widgets attribute found during close.")
            
            logger.info("Closing VideoClockScreenSaver...")
            
            # Non-blocking VLC cleanup with timeout
            def cleanup_vlc():
                try:
                    if hasattr(self, 'vlc_player') and self.vlc_player:
                        logger.info("Stopping VLC player...")
                        self.vlc_player.stop()
                        logger.info("VLC player stopped")
                        self.vlc_player.release()
                        logger.info("VLC player released")
                        self.vlc_player = None

                    if hasattr(self, 'media') and self.media:
                        self.media.release()
                        self.media = None
                        logger.info("VLC media released")

                    if hasattr(self, 'vlc_instance') and self.vlc_instance:
                        logger.info("Releasing VLC instance...")
                        self.vlc_instance.release()
                        self.vlc_instance = None
                        logger.info("VLC instance released")
                        
                except Exception as e:
                    logger.error(f"Exception during VLC cleanup: {e}")
                
            # Run VLC cleanup in separate thread with timeout
            cleanup_thread = threading.Thread(target=cleanup_vlc, daemon=True)
            cleanup_thread.start()
            
            # Wait for cleanup with timeout (max 2 seconds)
            cleanup_thread.join(timeout=2.0)
            
            if cleanup_thread.is_alive():
                logger.warning("VLC cleanup thread did not finish within timeout - proceeding anyway")
            else:
                logger.info("VLC cleanup completed successfully")
                
            logger.info("VLC player exited.")
            logger.info("VideoClockScreenSaver closed.")
            
        except Exception as e:
            logger.error(f"Exception in close: {e}")

    @staticmethod
    def pause_video(self):
        """Pause VLC video playback (for user prompt display)"""
        logger.debug("Pausing VLC video playback")
        try:
            if hasattr(self, 'vlc_player') and self.vlc_player:
                self.vlc_player.set_pause(1)
        except Exception as e:
            logger.error(f"Exception in pause_video: {e}")

    @staticmethod
    def resume_video(self):
        """Resume VLC video playback (after user prompt is hidden)"""
        logger.debug("Resuming VLC video playback")
        try:
            if hasattr(self, 'vlc_player') and self.vlc_player:
                self.vlc_player.set_pause(0)
        except Exception as e:
            logger.error(f"Exception in resume_video: {e}")

    @staticmethod
    def get_current_time_seconds(self):
        # get_time() returns the time in milliseconds
        if hasattr(self, 'vlc_player') and self.vlc_player:
            current_time_ms = self.vlc_player.get_time()
            # Convert milliseconds to seconds
            current_time_seconds = current_time_ms / 1000.0 
            return current_time_seconds
        return 0.0