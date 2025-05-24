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

from .PasswordConfig import load_config

def get_username_from_config():
    config = load_config()
    return config.get('default_user_for_display', 'User')

def get_user_config():
    return load_config()

def draw_rounded_rectangle(draw, xy, radius, fill=None, outline=None, width=1):
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
    
    if not fill and outline: # Draw border if no fill
        draw.line([(x1+radius,y1),(x2-radius,y1)],fill=outline,width=width)
        draw.line([(x1+radius,y2),(x2-radius,y2)],fill=outline,width=width)
        draw.line([(x1,y1+radius),(x1,y2-radius)],fill=outline,width=width)
        draw.line([(x2,y1+radius),(x2,y2-radius)],fill=outline,width=width)


class FrameProcessorThread(threading.Thread):
    """Thread for preprocessing frames (adding UI elements)"""
    def __init__(self, raw_frame_queue, processed_frame_queue, ui_elements_callback):
        super().__init__(daemon=True)
        self.raw_frame_queue = raw_frame_queue
        self.processed_frame_queue = processed_frame_queue
        self.ui_elements_callback = ui_elements_callback
        self.running = False
        self.frame_skip_counter = 0
        
    def run(self):
        self.running = True
        while self.running:
            try:
                raw_frame = self.raw_frame_queue.get(timeout=0.05)  # Reduced timeout
                if raw_frame is None:  # Shutdown signal
                    break
                    
                # Skip frames if processing queue is backing up
                if self.processed_frame_queue.qsize() > 0:
                    self.frame_skip_counter += 1
                    if self.frame_skip_counter % 2 == 0:  # Skip every other frame when backed up
                        continue
                
                # Process frame with UI elements in background thread
                processed_frame = self.ui_elements_callback(raw_frame)
                
                try:
                    # Use put_nowait to avoid blocking
                    self.processed_frame_queue.put_nowait(processed_frame)
                except queue.Full:
                    # Drop oldest frame and add new one
                    try:
                        self.processed_frame_queue.get_nowait()  # Remove oldest
                        self.processed_frame_queue.put_nowait(processed_frame)
                    except queue.Empty:
                        pass
                        
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in frame processor: {e}")
                
    def stop(self):
        self.running = False
        try:
            self.raw_frame_queue.put(None, timeout=0.05)  # Shutdown signal
        except queue.Full:
            pass

class FrameReaderThread(threading.Thread):
    def __init__(self, video_path, frame_queue, target_fps):
        super().__init__(daemon=True)
        self.video_path = video_path
        self.frame_queue = frame_queue
        self.target_fps = target_fps 
        self.cap = None
        self.running = False
        self.frame_interval = 1.0 / self.target_fps
        self.last_frame_time = 0
        self.frame_skip_threshold = 2  # Skip frames if queue is backing up

    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.video_path, cv2.CAP_ANY)
        if not self.cap.isOpened():
            print(f"Error: Could not open video {self.video_path} in thread.")
            self.running = False
            return

        # Aggressive optimization for video capture
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        # Try to set hardware acceleration if available
        try:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
        except:
            pass

        frame_count = 0
        while self.running:
            current_time = time.perf_counter()
            
            # Precise frame timing
            time_since_last = current_time - self.last_frame_time
            if time_since_last < self.frame_interval:
                sleep_time = self.frame_interval - time_since_last
                if sleep_time > 0.001:  # Only sleep if significant time left
                    time.sleep(sleep_time * 0.9)  # Sleep slightly less to avoid overshooting
                continue
                
            # Skip frames if queue is backing up to maintain real-time performance
            if self.frame_queue.qsize() >= self.frame_skip_threshold:
                frame_count += 1
                if frame_count % 2 == 0:  # Skip every other frame when backed up
                    self.last_frame_time = current_time
                    continue
            
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) 
                ret, frame = self.cap.read()
                if not ret:
                    print("Error reading frame in thread, stopping.")
                    break 
            
            # Direct conversion without ThreadPoolExecutor for better performance
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb).convert("RGBA")
                
                try:
                    self.frame_queue.put_nowait(pil_img)
                except queue.Full:
                    # Drop oldest frame
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait(pil_img)
                    except queue.Empty:
                        pass
                
                self.last_frame_time = current_time
                frame_count += 1
                
            except Exception as e:
                print(f"Error processing frame: {e}")
                continue
        
        if self.cap:
            self.cap.release()
        print("FrameReaderThread finished.")

    def stop(self):
        self.running = False

def find_font_path(font_family):
    """Try to find the font file path for a given font family name."""
    # Try to find the font in common system font directories
    font_dirs = []
    system = platform.system()
    if system == "Windows":
        font_dirs = [os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")]
    elif system == "Darwin":
        font_dirs = ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:  # Linux/Unix
        font_dirs = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]

    # Normalize font family for matching
    normalized_family = font_family.replace(" ", "").lower()

    # Try to find .ttf or .TTF file matching the font family
    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for root, dirs, files in os.walk(font_dir):
            for file in files:
                if file.lower().endswith(".ttf") or file.lower().endswith(".otf"):
                    file_no_ext = os.path.splitext(file)[0].replace(" ", "").lower()
                    if normalized_family in file_no_ext:
                        return os.path.join(root, file)
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

class VideoClockScreenSaver:
    def __init__(self, master, video_path_arg=None): # video_path_arg is for CLI override
        self.master = master
        master.attributes('-fullscreen', True)
        master.configure(bg='black')
        
        self.user_config = load_config()
        
        # Determine the username to display on the screensaver
        self.username_to_display = self.user_config.get('default_user_for_display')
        user_exists = False
        if self.username_to_display:
            for u in self.user_config.get("users", []):
                if u.get("username") == self.username_to_display:
                    user_exists = True
                    break
        if not user_exists: # Fallback to first user if default not set or not found
             self.username_to_display = self.user_config.get("users", [{}])[0].get("username", "User")
        
        self.username = self.username_to_display # Used for drawing profile elements
        
        # Use video_path from arg (CLI) if provided, else from config, else default
        # Default to "video.mp4" which is expected to be in the project root (ScreenSaver directory)
        video_path_from_config_or_default = self.user_config.get('video_path', 'video.mp4')
        actual_video_path = video_path_arg if video_path_arg else video_path_from_config_or_default
        
        # Ensure video path is absolute. If relative, assume it's relative to the project root.
        if not os.path.isabs(actual_video_path):
            # Project root is two levels up from this file (screensaver_app/video_player.py -> ScreenSaver/)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            actual_video_path = os.path.join(project_root, actual_video_path)
            print(f"Resolved relative video path to: {actual_video_path}") # Debug print


        self.width = master.winfo_screenwidth() 
        self.height = master.winfo_screenheight()

        self.target_fps = 30
        self.frame_interval = int(1000 / self.target_fps)
        
        # Optimized queues with smaller sizes for lower latency
        self.raw_frame_queue = queue.Queue(maxsize=1)  # Reduced queue size
        self.processed_frame_queue = queue.Queue(maxsize=1)  # Reduced queue size
        
        self.label = tk.Label(master, bg='black')
        self.label.pack(fill=tk.BOTH, expand=True)
        
        # Load clock font settings from config
        self.clock_font_family = self.user_config.get("clock_font_family", "Segoe UI Emoji")
        self.clock_font_size = self.user_config.get("clock_font_size", 64)
        
        # Load UI font settings from config
        self.ui_font_family = self.user_config.get("ui_font_family", "Arial")
        self.ui_font_size = self.user_config.get("ui_font_size", 18)
        
        # CLOCK FONT
        font_path_used = None
        try:
            font_path = find_font_path(self.clock_font_family)
            if font_path:
                self.clock_font = ImageFont.truetype(font_path, self.clock_font_size)
                font_path_used = font_path
                print(f"Using clock font file: {font_path}")
            else:
                self.clock_font = ImageFont.truetype(self.clock_font_family, self.clock_font_size)
                font_path_used = self.clock_font_family
                print(f"Using clock font family: {self.clock_font_family}")
        except Exception as e:
            print(f"Warning: Clock font '{self.clock_font_family}' not found. Using PIL default. ({e})")
            self.clock_font = ImageFont.load_default()

        # UI FONT
        ui_font_path_used = None
        try:
            ui_font_path = find_font_path(self.ui_font_family)
            if ui_font_path:
                self.profile_name_font = ImageFont.truetype(ui_font_path, self.ui_font_size)
                self.profile_initial_font = ImageFont.truetype(ui_font_path, self.ui_font_size * 2)
                ui_font_path_used = ui_font_path
                print(f"Using UI font file: {ui_font_path}")
            else:
                self.profile_name_font = ImageFont.truetype(self.ui_font_family, self.ui_font_size)
                self.profile_initial_font = ImageFont.truetype(self.ui_font_family, self.ui_font_size * 2)
                ui_font_path_used = self.ui_font_family
                print(f"Using UI font family: {self.ui_font_family}")
        except Exception as e:
            print(f"Warning: UI font '{self.ui_font_family}' not found. Using PIL default. ({e})")
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
                print(f"Error loading or processing custom profile picture '{custom_pic_path}': {e}")
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
        name_text = self.username
        try: 
            bbox = self.profile_name_font.getbbox(name_text)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x_offset, text_y_offset = bbox[0], bbox[1]
        except AttributeError: 
            text_width, text_height = self.profile_name_font.getsize(name_text)
            text_x_offset, text_y_offset = 0, 0
        
        padding = 10
        rect_width = text_width + 2 * padding
        rect_height = text_height + 2 * padding
        
        image = Image.new('RGBA', (int(rect_width), int(rect_height)), (0,0,0,0))
        draw = ImageDraw.Draw(image)
        draw_rounded_rectangle(draw, (0,0, rect_width-1, rect_height-1), 
                               radius=8, fill=(30, 30, 30, 180))
        
        draw.text((padding - text_x_offset, padding - text_y_offset), name_text, font=self.profile_name_font, fill=(255, 255, 255, 230))
        return image

    def _process_frame_with_ui(self, pil_img):
        """Process frame with UI elements in background thread - optimized"""
        if not self.first_frame_received:
            return pil_img
            
        # Work directly on the image instead of copying for better performance
        frame = pil_img
        
        # Add profile elements (these are pre-rendered, so it's fast)
        if self.pre_rendered_profile_pic and self.pre_rendered_username_label:
            profile_pic_pos_int = (int(self.profile_pic_pos[0]), int(self.profile_pic_pos[1]))
            username_label_pos_int = (int(self.username_label_pos[0]), int(self.username_label_pos[1]))
            frame.paste(self.pre_rendered_profile_pic, profile_pic_pos_int, self.pre_rendered_profile_pic)
            frame.paste(self.pre_rendered_username_label, username_label_pos_int, self.pre_rendered_username_label)

        # Cache clock rendering to avoid redrawing every frame
        current_time_ms = int(time.time() * 1000)
        if current_time_ms - self.last_clock_update >= 1000:
            self.current_time_text = time.strftime('%I:%M:%S %p')
            self.last_clock_update = current_time_ms
            
            # Pre-calculate clock position (cache this)
            try: 
                clock_bbox = self.clock_font.getbbox(self.current_time_text)
                self.clock_text_width = clock_bbox[2] - clock_bbox[0]
            except AttributeError: 
                self.clock_text_width, _ = self.clock_font.getsize(self.current_time_text)
            
            self.clock_x = (self.width - self.clock_text_width) // 2
            self.clock_y = int(self.height * 0.1)
        
        # Draw clock with cached positions
        draw = ImageDraw.Draw(frame)
        draw.text((int(self.clock_x+2), int(self.clock_y+2)), self.current_time_text, font=self.clock_font, fill=(0,0,0,128))
        draw.text((int(self.clock_x), int(self.clock_y)), self.current_time_text, font=self.clock_font, fill=(255,255,255,220))
        
        return frame

    def update_frame(self):
        """Main UI thread - optimized for performance"""
        frame_start_time = time.perf_counter()
        
        try:
            # Get processed frame (non-blocking)
            processed_frame = self.processed_frame_queue.get_nowait()
        except queue.Empty:
            # No processed frame ready, schedule next update with adaptive delay
            delay = max(1, self.frame_interval // 8)  # Faster polling when no frames
            self.after_id = self.master.after(delay, self.update_frame)
            return

        # Initialize UI elements on first frame
        if not self.first_frame_received:
            self._initialize_ui_elements_after_first_frame(processed_frame.width, processed_frame.height)

        # Convert to Tkinter format and display
        try:
            self.imgtk = ImageTk.PhotoImage(processed_frame)
            self.label.config(image=self.imgtk)
        except Exception as e:
            print(f"Error updating label image: {e}") 
        
        # Performance monitoring with moving average
        frame_time = time.perf_counter() - frame_start_time
        self.fps_history.append(frame_time)
        self.frames_processed_in_ui += 1
        current_time = time.perf_counter()
        
        if current_time - self.last_fps_print >= 3.0:  # Print every 3 seconds
            if self.fps_history:
                avg_frame_time = sum(self.fps_history) / len(self.fps_history)
                estimated_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
                print(f"UI FPS: {estimated_fps:.1f} (avg frame time: {avg_frame_time*1000:.1f}ms), Raw Queue: {self.raw_frame_queue.qsize()}, Processed Queue: {self.processed_frame_queue.qsize()}")
            self.frames_processed_in_ui = 0
            self.start_time = current_time
            self.last_fps_print = current_time
        
        # Adaptive scheduling based on performance
        processing_time_ms = frame_time * 1000
        if processing_time_ms < self.frame_interval * 0.5:
            # We're running fast, normal delay
            delay = max(1, int(self.frame_interval - processing_time_ms))
        else:
            # We're running slow, minimal delay
            delay = 1
        
        self.after_id = self.master.after(delay, self.update_frame)

    def close(self):
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