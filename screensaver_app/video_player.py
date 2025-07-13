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

# Add central logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('VideoPlayer')

from .PasswordConfig import load_config
from utils.gpu_utils import get_gpu_manager, get_preferred_opencv_backend, setup_gpu_environment

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

class VideoClockScreenSaver:

    def __init__(self, master, video_path_arg=None):
        logger.debug("Initializing VideoClockScreenSaver")
        try:
            self.master = master
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
                self.overlay_win.config(bg='black')  # Fix: use a valid color name instead of ""
                self.overlay_canvas = tk.Canvas(self.overlay_win, bg='black', highlightthickness=0, borderwidth=0)
            self.overlay_canvas.place(x=0, y=0, width=self.width, height=self.height)

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
            # Add dummy attributes to prevent AttributeError from other modules
            self.frame_reader_thread = None
            self.frame_processor_thread = None
            self.after_id = None

            self.master.after(100, self.init_widgets)

            # VLC setup
            self.vlc_instance = vlc.Instance()
            self.vlc_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(actual_video_path)
            self.vlc_player.set_media(media)
            # Embed VLC video output into Tkinter Label
            self.vlc_player.set_hwnd(self.label.winfo_id())
            # Mute VLC player to remove sound
            self.vlc_player.audio_set_mute(True)
            
            # Initialize UI elements immediately for VLC playback
            self._initialize_ui_elements_immediately()
            
            self.vlc_player.play()

            # Schedule overlays
            self.master.after(10, self.update_overlays)
        except Exception as e:
            logger.error(f"Exception in __init__: {e}")

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
                    time.sleep(0.1)  # Reduced from 0.5
                    
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
            """Create weather widget on main thread"""
            weather_widget_toplevel = WeatherWidget(
                self.master, 
                self.TRANSPARENT_KEY, 
                screen_width=screen_w,
                screen_height=screen_h,
                pincode=pincode,
                country_code=country
            )
            
            self.widgets.append(weather_widget_toplevel)
            logger.info(f"Weather widget created for {pincode}, {country}.")
            
        except Exception as e:
            logger.error(f"Exception in _create_weather_widget: {e}")

    def _create_stock_widget(self, market, screen_w, screen_h):
        logger.debug(f"Called _create_stock_widget with market={market}")
        try:
            """Create stock widget on main thread"""
            stock_widget_toplevel = StockWidget(
                self.master, 
                self.TRANSPARENT_KEY, 
                screen_width=screen_w,
                screen_height=screen_h,
                initial_market=market
            )
            
            self.widgets.append(stock_widget_toplevel)
            logger.info(f"Stock widget (Toplevel) for {market} created.")
            
        except Exception as e:
            logger.error(f"Exception in _create_stock_widget: {e}")
    
    def _create_media_widget(self, screen_w, screen_h):
        logger.debug("Called _create_media_widget")
        try:
            """Create media widget on main thread"""
            media_widget_toplevel = MediaWidget(
                self.master, 
                self.TRANSPARENT_KEY,
                screen_width=screen_w,
                screen_height=screen_h
            )
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
            
            # Calculate initial clock position here, now that frame dimensions are known
            try: 
                clock_bbox = self.clock_font.getbbox(self.current_time_text) # Use current_time_text from __init__
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
        logger.debug("Called update_overlays")
        try:
            """Draw overlays (clock, profile, widgets) over VLC video using a transparent Canvas."""
            # Ensure overlay window is properly configured
            if platform.system() == 'Windows':
                self.overlay_win.config(bg=self.TRANSPARENT_KEY)
                self.overlay_canvas.config(bg=self.TRANSPARENT_KEY)
            
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
            if hasattr(self, 'after_id') and self.after_id:
                self.master.after_cancel(self.after_id)
                self.after_id = None 
            
            # Stop processor thread first
            if hasattr(self, 'frame_processor_thread') and self.frame_processor_thread.is_alive():
                logger.debug("Stopping frame processor thread...")
                self.frame_processor_thread.stop()
                self.frame_processor_thread.join(timeout=2)
            
            # Then stop reader thread
            if hasattr(self, 'frame_reader_thread'):
                if hasattr(self.frame_reader_thread, 'is_alive') and self.frame_reader_thread.is_alive():
                    logger.debug("Stopping frame reader thread...")
                    if hasattr(self.frame_reader_thread, 'paused'):
                        self.frame_reader_thread.paused = False # Ensure it's not stuck in a paused state
                    if hasattr(self.frame_reader_thread, 'running'):
                        self.frame_reader_thread.running = False # Set running to false to exit loop
                    self.frame_reader_thread.join(timeout=2) 
                    if hasattr(self.frame_reader_thread, 'is_alive') and self.frame_reader_thread.is_alive():
                        logger.warning("Frame reader thread did not stop in time.")
            logger.info("VideoClockScreenSaver closed.")
        except Exception as e:
            logger.error(f"Exception in close: {e}")

    def pause_video(self):
        """Pause VLC video playback (for user prompt display)"""
        logger.debug("Pausing VLC video playback")
        try:
            if self.vlc_player:
                self.vlc_player.pause()
        except Exception as e:
            logger.error(f"Exception in pause_video: {e}")

    def resume_video(self):
        """Resume VLC video playback (after user prompt is hidden)"""
        logger.debug("Resuming VLC video playback")
        try:
            if self.vlc_player:
                self.vlc_player.play()
        except Exception as e:
            logger.error(f"Exception in resume_video: {e}")