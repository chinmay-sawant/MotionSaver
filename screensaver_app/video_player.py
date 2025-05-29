import tkinter as tk
import cv2
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
from central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('VideoPlayer')

from .PasswordConfig import load_config

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


class FrameProcessorThread(threading.Thread):
    """Enhanced thread for preprocessing frames with better performance"""
    def __init__(self, raw_frame_queue, processed_frame_queue, ui_elements_callback):
        super().__init__(daemon=True)
        self.raw_frame_queue = raw_frame_queue
        self.processed_frame_queue = processed_frame_queue
        self.ui_elements_callback = ui_elements_callback
        self.running = False
        self.frame_skip_counter = 0
        self.processing_times = collections.deque(maxlen=10)  # Reduced for faster response
        
    def run(self):
        self.running = True
        while self.running:
            try:
                raw_frame = self.raw_frame_queue.get(timeout=0.01)  # Much shorter timeout
                if raw_frame is None:  # Shutdown signal
                    break
                    
                process_start = time.perf_counter()
                
                # More aggressive frame skipping based on processing load
                if self.processed_frame_queue.qsize() > 0:
                    self.frame_skip_counter += 1
                    # Dynamic skip ratio based on processing times
                    avg_process_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
                    if avg_process_time > 0.012:  # If processing > 12ms (should be ~16ms for 60fps)
                        if self.frame_skip_counter % 3 == 0:  # Skip 2 out of 3 frames
                            continue
                    elif avg_process_time > 0.008:  # If processing > 8ms
                        if self.frame_skip_counter % 2 == 0:  # Skip every other frame
                            continue
                
                # Process frame with UI elements
                processed_frame = self.ui_elements_callback(raw_frame)
                
                process_time = time.perf_counter() - process_start
                self.processing_times.append(process_time)
                
                try:
                    self.processed_frame_queue.put_nowait(processed_frame)
                except queue.Full:
                    # Drop oldest frame and add new one
                    try:
                        self.processed_frame_queue.get_nowait()
                        self.processed_frame_queue.put_nowait(processed_frame)
                    except queue.Empty:
                        pass
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in frame processor: {e}")
                
    def stop(self):
        self.running = False
        try:
            self.raw_frame_queue.put(None, timeout=0.01)
        except queue.Full:
            pass

class FrameReaderThread(threading.Thread):
    def __init__(self, video_path, frame_queue, target_fps): # target_fps is the display target
        super().__init__(daemon=True)
        self.video_path = video_path
        self.frame_queue = frame_queue
        # self.target_fps = target_fps # Not directly used for reader's sleep timing
        self.cap = None
        self.running = False
        # self.frame_interval = 1.0 / self.target_fps # Not used for sleeping
        self.last_frame_time = 0
        self.frame_skip_threshold = 1 
        self.video_fps = None  # Store actual video FPS
        self.actual_frame_interval = 1.0 / 30.0 # Default if video_fps is not found, ensure float

    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.video_path, cv2.CAP_ANY)        
        if not self.cap.isOpened():
            logger.error(f"Could not open video {self.video_path} in thread")
            self.running = False
            return

        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.video_fps <= 0 or self.video_fps > 120:  # Fallback for invalid FPS
            self.video_fps = 30.0 # Ensure float for division
        
        logger.info(f"Video FPS: {self.video_fps:.2f}")  # Display actual video FPS
        
        self.actual_frame_interval = 1.0 / self.video_fps
        
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        try:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            cv2.setNumThreads(1)  # Reduced to 1 to minimize CPU contention
        except:
            pass

        frame_count = 0
        last_perf_time = time.perf_counter()
        
        while self.running:
            current_time = time.perf_counter()
            
            time_since_last = current_time - self.last_frame_time
            if time_since_last < self.actual_frame_interval:
                sleep_time = self.actual_frame_interval - time_since_last
                if sleep_time > 0.001:
                    time.sleep(sleep_time * 0.9) 
                continue
            
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)                
                ret, frame = self.cap.read()
                if not ret:
                    logger.error("Error reading frame in FrameReaderThread, stopping.")
                    break 
            
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb, mode='RGB').convert("RGBA")
                
                try:
                    self.frame_queue.put_nowait(pil_img)
                except queue.Full:
                    try:
                        self.frame_queue.get_nowait() # Drop oldest
                        self.frame_queue.put_nowait(pil_img) # Put current
                    except queue.Empty:
                        pass # Queue became empty in between
                
                self.last_frame_time = current_time
                frame_count += 1
                
                if frame_count % 120 == 0: # Approx every 2-4 seconds
                    elapsed = current_time - last_perf_time
                    actual_read_fps = 120 / elapsed if elapsed > 0 else 0
                    if actual_read_fps < self.video_fps * 0.8:                    logger.debug(f"Frame reader read FPS: {actual_read_fps:.1f} (video native: {self.video_fps:.1f})")
                    last_perf_time = current_time
                
            except Exception as e:
                logger.error(f"Error processing frame in FrameReaderThread: {e}")
                continue
        
        if self.cap:
            self.cap.release()
        logger.info("FrameReaderThread finished.")

    def stop(self):
        self.running = False

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
    def __init__(self, master, video_path_arg=None): # video_path_arg is for CLI override
        self.master = master
        self.root = master  # Add this line to fix the AttributeError
        master.attributes('-fullscreen', True)
        master.configure(bg='black')
        
        # Define transparent key for widgets
        self.TRANSPARENT_KEY = '#123456'
        
        # Store screen dimensions for widget positioning
        self.screen_width = master.winfo_screenwidth()
        self.screen_height = master.winfo_screenheight()
        
        self.user_config = load_config()
        
        # Fetch system user name
        system_user = getpass.getuser()
        self.username_to_display = system_user
        self.username = system_user
        
        # Use video_path from arg (CLI) if provided, else from config, else default
        # Default to "video.mp4" which is expected to be in the project root (ScreenSaver directory)
        video_path_from_config_or_default = self.user_config.get('video_path', 'video.mp4')
        actual_video_path = video_path_arg if video_path_arg else video_path_from_config_or_default
        
        # Ensure video path is absolute. If relative, assume it's relative to the project root.
        if not os.path.isabs(actual_video_path):
            # Project root is two levels up from this file (screensaver_app/video_player.py -> ScreenSaver/)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            actual_video_path = os.path.join(project_root, actual_video_path)
            logger.debug(f"Resolved relative video path to: {actual_video_path}")


        self.width = master.winfo_screenwidth() 
        self.height = master.winfo_screenheight()

        self.target_fps = 30
        self.frame_interval = int(1000 / self.target_fps) # For UI update scheduling if queue empty
        
        # Slightly larger queues for a bit more buffering
        self.raw_frame_queue = queue.Queue(maxsize=2)
        self.processed_frame_queue = queue.Queue(maxsize=2)
        
        self.label = tk.Label(master, bg='black')
        self.label.pack(fill=tk.BOTH, expand=True)
        
        # Load clock font settings from config
        self.clock_font_family = self.user_config.get("clock_font_family", "Segoe UI Emoji")
        self.clock_font_size = self.user_config.get("clock_font_size", 64)
        
        # Load UI font settings from config
        self.ui_font_family = self.user_config.get("ui_font_family", "Arial")
        # Use a much larger font size for username label
        self.ui_font_size = self.user_config.get("ui_font_size", 30)  # Significantly increase UI font size

        # CLOCK FONT
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

        # UI FONT
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

        # self.username is already set from self.user_config
        # self.user_config is already loaded
        
        self.profile_pic_size = 80 
        
        self.pre_rendered_profile_pic = None
        self.pre_rendered_username_label = None
        self.profile_pic_pos = (0,0)
        self.username_label_pos = (0,0)

        self.imgtk = None
        self.after_id = None
        self.current_time_text = time.strftime('%I:%M:%S %p')
        self.last_clock_update = 0
        
        # Initialize clock positioning variables to prevent AttributeError
        self.clock_x = 0
        self.clock_y = 0
        self.clock_text_width = 0
        
        # Performance tracking with moving average
        self.start_time = time.perf_counter()
        self.frames_processed_in_ui = 0 
        self.last_fps_print = time.perf_counter()
        self.fps_history = collections.deque(maxlen=30)  # Track last 30 frame times
        
        # Start threaded pipeline
        self.frame_reader_thread = FrameReaderThread(actual_video_path, self.raw_frame_queue, self.target_fps)
        self.frame_processor_thread = FrameProcessorThread(
            self.raw_frame_queue, 
            self.processed_frame_queue, 
            self._process_frame_with_ui
        )
        
        self.frame_reader_thread.start()
        self.frame_processor_thread.start()
        
        self.first_frame_received = False
        self.update_frame()

        # Initialize widgets based on config
        self.widgets = []
        self.master.after(1000, self.init_widgets)  # Use self.master instead of self.root
        
    def init_widgets(self):
        """Initialize widgets based on configuration - now fully async with priorities"""
        config = load_config()
        
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        
        def create_widgets_async():
            """Create widgets in separate thread with proper prioritization"""
            try:
                # Longer delay to ensure video pipeline is fully stable
                time.sleep(0.5)
                
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
                
                # Create widgets with staggered timing
                for i, (widget_type, param) in enumerate(widgets_to_create):
                    if i > 0:
                        time.sleep(0.8)  # Stagger widget creation
                    
                    # Schedule widget creation on main thread
                    if widget_type == "weather":
                        pincode, country = param
                        self.master.after(0, lambda p=pincode, c=country: self._create_weather_widget(p, c, screen_w, screen_h))
                    elif widget_type == "stock":
                        self.master.after(0, lambda market=param: self._create_stock_widget(market, screen_w, screen_h))
                    elif widget_type == "media":
                        time.sleep(0.5)  # Extra delay for media widget                        self.master.after(0, lambda: self._create_media_widget(screen_w, screen_h))
                        
            except Exception as e:
                logger.error(f"Error in async widget creation: {e}")
        
        # Start widget creation in separate thread
        widget_thread = threading.Thread(target=create_widgets_async, daemon=True)
        widget_thread.start()

    def _create_weather_widget(self, pincode, country, screen_w, screen_h):
        """Create weather widget on main thread"""
        try:
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
            logger.error(f"Failed to create weather widget: {e}")

    def _create_stock_widget(self, market, screen_w, screen_h):
        """Create stock widget on main thread"""
        try:
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
            logger.error(f"Failed to create stock widget (Toplevel): {e}")
    
    def _create_media_widget(self, screen_w, screen_h):
        """Create media widget on main thread"""
        try:
            media_widget_toplevel = MediaWidget(
                self.master, 
                self.TRANSPARENT_KEY,
                screen_width=screen_w,
                screen_height=screen_h
            )
            self.widgets.append(media_widget_toplevel)
            logger.info(f"Media widget (Toplevel) created.")
            
        except Exception as e:
            logger.error(f"Failed to create media widget (Toplevel): {e}")

    def _initialize_ui_elements_after_first_frame(self, frame_width, frame_height):
        self.width = frame_width
        self.height = frame_height
        self.profile_center_x = self.width // 2
        self.profile_name_y_base = int(self.height * 0.85) 
        self.profile_pic_y_base = self.profile_name_y_base - self.profile_pic_size - 10

        self.pre_rendered_profile_pic = self._create_pre_rendered_profile_pic()
        self.pre_rendered_username_label = self._create_pre_rendered_username_label()
        
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


    def _create_pre_rendered_profile_pic(self):
        size = self.profile_pic_size
        # Use cropped profile pic path if available, otherwise fall back to original path
        custom_pic_path_from_config = self.user_config.get("profile_pic_path_crop", "")
        if not custom_pic_path_from_config:
            custom_pic_path_from_config = self.user_config.get("profile_pic_path", "")
            
        custom_pic_path = ""
        if custom_pic_path_from_config:
            if not os.path.isabs(custom_pic_path_from_config):
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                custom_pic_path = os.path.join(project_root, custom_pic_path_from_config)
            else:
                custom_pic_path = custom_pic_path_from_config
        
        loaded_custom_image = None
        if custom_pic_path and os.path.exists(custom_pic_path):
            try:
                img = Image.open(custom_pic_path).convert("RGBA")
                
                # Create a perfect square image with transparent background
                square_img = Image.new('RGBA', (max(img.width, img.height), max(img.width, img.height)), (0,0,0,0))
                paste_x = (square_img.width - img.width) // 2
                paste_y = (square_img.height - img.height) // 2
                square_img.paste(img, (paste_x, paste_y))
                
                # Resize the square to fit our target size
                square_img = square_img.resize((size, size), Image.Resampling.LANCZOS)
                
                # Create circular mask
                mask = Image.new('L', (size, size), 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.ellipse((0, 0, size, size), fill=255)
                
                # Apply mask to get circular image
                circular_img = Image.new('RGBA', (size, size), (0,0,0,0))
                circular_img.paste(square_img, (0, 0))
                circular_img.putalpha(mask)                
                loaded_custom_image = circular_img
                
            except Exception as e:
                logger.error(f"Error loading or processing custom profile picture '{custom_pic_path}': {e}")
                loaded_custom_image = None

        if loaded_custom_image:
            return loaded_custom_image

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
    def _create_pre_rendered_username_label(self):
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

    def _process_frame_with_ui(self, pil_img):
        """Optimized frame processing with minimal overhead"""
        if not self.first_frame_received:
            # This path is taken for the very first frame.
            # self.clock_x and self.clock_y are not used yet for drawing here.
            return pil_img
            
        # Work directly on the image for better performance
        frame = pil_img
        
        # Add profile elements with minimal processing
        if self.pre_rendered_profile_pic and self.pre_rendered_username_label:
            profile_pic_pos_int = (int(self.profile_pic_pos[0]), int(self.profile_pic_pos[1]))
            username_label_pos_int = (int(self.username_label_pos[0]), int(self.username_label_pos[1]))
            frame.paste(self.pre_rendered_profile_pic, profile_pic_pos_int, self.pre_rendered_profile_pic)
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

    def update_frame(self):
        """Optimized UI thread for better performance with widgets"""
        frame_start_time = time.perf_counter()
        
        processed_frame = None
        try:
            processed_frame = self.processed_frame_queue.get_nowait()
        except queue.Empty:
            # No frame ready, schedule next attempt.
            # Use a slightly more relaxed delay if the queue is consistently empty.
            delay = max(1, self.frame_interval // 4) 
            self.after_id = self.master.after(delay, self.update_frame)
            return

        # Initialize UI elements on first frame if a frame was successfully dequeued
        if not self.first_frame_received and processed_frame:
            self._initialize_ui_elements_after_first_frame(processed_frame.width, processed_frame.height)        
        if processed_frame:
            try:
                self.imgtk = ImageTk.PhotoImage(processed_frame)
                self.label.config(image=self.imgtk)
            except Exception as e:
                logger.error(f"Error updating label image: {e}") 
        
        # Lightweight performance monitoring
        frame_time = time.perf_counter() - frame_start_time
        self.fps_history.append(frame_time)
        self.frames_processed_in_ui += 1
        current_time = time.perf_counter()
        
        # Less frequent performance logging to reduce overhead
        if current_time - self.last_fps_print >= 5.0:  # Every 5 seconds            if self.fps_history:
                avg_frame_time = sum(self.fps_history) / len(self.fps_history)
                estimated_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
                queue_info = f"Raw: {self.raw_frame_queue.qsize()}, Processed: {self.processed_frame_queue.qsize()}"
                widget_count = len(self.widgets)
                logger.debug(f"UI FPS: {estimated_fps:.1f}, Widgets: {widget_count}, Queues: {queue_info}")
        self.frames_processed_in_ui = 0
        self.start_time = current_time
        self.last_fps_print = current_time
        
        # Optimized scheduling for the next frame
        ui_update_duration_ms = (time.perf_counter() - frame_start_time) * 1000
        target_cycle_time_ms = 1000.0 / self.target_fps # e.g., 33.3ms for 30fps
        
        delay = int(target_cycle_time_ms - ui_update_duration_ms)
        
        if delay < 1: # Ensure delay is at least 1ms
            delay = 1 
        
        self.after_id = self.master.after(delay, self.update_frame)

    def close(self):        
        """Clean shutdown of the screensaver"""
        logger.info("Closing VideoClockScreenSaver and its widgets...")
        # Clean up widgets
        for widget in self.widgets:
            if hasattr(widget, 'destroy') and callable(widget.destroy):
                widget.destroy()
        self.widgets.clear()
        
        print("Closing VideoClockScreenSaver...")
        if self.after_id:
            self.master.after_cancel(self.after_id)
            self.after_id = None 
        
        # Stop processor thread first
        if hasattr(self, 'frame_processor_thread') and self.frame_processor_thread.is_alive():
            print("Stopping frame processor thread...")
            self.frame_processor_thread.stop()
            self.frame_processor_thread.join(timeout=2)
        
        # Then stop reader thread
        if hasattr(self, 'frame_reader_thread') and self.frame_reader_thread.is_alive():
            print("Stopping frame reader thread...")
            self.frame_reader_thread.stop()
            self.frame_reader_thread.join(timeout=2) 
            if self.frame_reader_thread.is_alive():
                print("Frame reader thread did not stop in time.")
        print("VideoClockScreenSaver closed.")