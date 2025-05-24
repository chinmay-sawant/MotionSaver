import tkinter as tk
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
import time
import os
import json
import threading
import queue

# Helper function to get username (can be shared or moved to a utility file)
def get_username_from_config():
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), "password_config.json")
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get('user', 'User')
    except:
        return 'User' # Default

USER_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "userconfig.json")

def get_user_config():
    """Load user-specific configuration."""
    if not os.path.exists(USER_CONFIG_FILE):
        # Create a default userconfig.json if it doesn't exist
        with open(USER_CONFIG_FILE, 'w') as f:
            json.dump({"profile_pic_path": ""}, f, indent=2)
        return {"profile_pic_path": ""}
    try:
        with open(USER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading user config: {e}")
        return {"profile_pic_path": ""}

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


class FrameReaderThread(threading.Thread):
    def __init__(self, video_path, frame_queue, target_fps):
        super().__init__(daemon=True)
        self.video_path = video_path
        self.frame_queue = frame_queue
        self.target_fps = target_fps # Informational, actual reading speed is as fast as possible
        self.cap = None
        self.running = False
        self.frame_interval_ms = 1000 / self.target_fps


    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.video_path, cv2.CAP_ANY)
        if not self.cap.isOpened():
            print(f"Error: Could not open video {self.video_path} in thread.")
            self.running = False
            return

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2) # Small buffer

        while self.running:
            read_start_time = time.perf_counter()
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Loop video
                ret, frame = self.cap.read()
                if not ret:
                    print("Error reading frame in thread, stopping.")
                    break 
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb).convert("RGBA")
            
            try:
                # Put frame in queue, but don't block indefinitely if queue is full
                # This helps skip frames if UI thread can't keep up, prioritizing recent frames
                self.frame_queue.put(pil_img, block=True, timeout=0.5) 
            except queue.Full:
                # If queue is full, it means UI is lagging. We can drop this frame.
                # Or, clear the queue and put the new one to always show the latest.
                try:
                    # Clear old frames and put the new one
                    while not self.frame_queue.empty():
                        self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(pil_img)
                except queue.Full:
                    pass # Still full, just drop
                except queue.Empty: # Should not happen if we just cleared
                    pass

            # Control read speed slightly if necessary, though usually we want to read as fast as possible
            # to keep the queue fresh. The UI thread will control display FPS.
            # time.sleep(0.001) # Small sleep to yield CPU if needed

        if self.cap:
            self.cap.release()
        print("FrameReaderThread finished.")

    def stop(self):
        self.running = False


class VideoClockScreenSaver:
    def __init__(self, master, video_path):
        self.master = master
        master.attributes('-fullscreen', True)
        master.configure(bg='black')
        
        # Video properties are read by the thread, but we can get them once for UI setup
        # temp_cap = cv2.VideoCapture(video_path)
        # self.width = int(temp_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        # self.height = int(temp_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # temp_cap.release()
        # For simplicity, assume a common size or get from first frame later
        # Let's get width/height from the first frame received from the queue
        self.width = master.winfo_screenwidth() # Fallback to screen size
        self.height = master.winfo_screenheight()

        self.target_fps = 30
        self.frame_interval = int(1000 / self.target_fps)
        
        self.label = tk.Label(master, bg='black')
        self.label.pack(fill=tk.BOTH, expand=True)
        
        font_path = None
        for f_path in ["C:/Windows/Fonts/seguiemj.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            if os.path.exists(f_path):
                font_path = f_path
                break
        self.clock_font = ImageFont.truetype(font_path, 64) if font_path else ImageFont.load_default()
        self.profile_name_font = ImageFont.truetype(font_path, 18) if font_path else ImageFont.load_default()
        self.profile_initial_font = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()

        self.username = get_username_from_config()
        self.user_config = get_user_config() # Load user config
        self.profile_pic_size = 80 
        
        # Pre-render static profile elements (will use self.width/height for positioning)
        self.pre_rendered_profile_pic = None
        self.pre_rendered_username_label = None
        self.profile_pic_pos = (0,0)
        self.username_label_pos = (0,0)
        # self._initialize_ui_elements_after_first_frame() will be called once a frame is received

        self.imgtk = None
        self.after_id = None
        self.current_time_text = time.strftime('%I:%M:%S %p')
        self.last_clock_update = 0
        
        self.start_time = time.perf_counter()
        self.frames_processed_in_ui = 0 # Renamed to avoid confusion with thread
        
        self.frame_queue = queue.Queue(maxsize=2) # Small queue to keep frames fresh
        self.frame_reader_thread = FrameReaderThread(video_path, self.frame_queue, self.target_fps)
        self.frame_reader_thread.start()
        
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
        custom_pic_path = self.user_config.get("profile_pic_path", "")
        
        loaded_custom_image = None
        if custom_pic_path and os.path.exists(custom_pic_path):
            try:
                img = Image.open(custom_pic_path).convert("RGBA")
                # Resize to fit the profile pic size, maintaining aspect ratio (cropping if necessary)
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                # Create a circular mask
                mask = Image.new('L', (size, size), 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.ellipse((0, 0, size, size), fill=255)
                
                # Apply mask to the loaded image
                # Create a new transparent image of the target size
                circular_img = Image.new('RGBA', (size, size), (0,0,0,0))
                # Paste the (potentially smaller) thumbnail onto the center of the circular_img
                paste_x = (size - img.width) // 2
                paste_y = (size - img.height) // 2
                circular_img.paste(img, (paste_x, paste_y))
                circular_img.putalpha(mask) # Apply circular mask
                loaded_custom_image = circular_img
            except Exception as e:
                print(f"Error loading or processing custom profile picture '{custom_pic_path}': {e}")
                loaded_custom_image = None

        if loaded_custom_image:
            return loaded_custom_image

        # Fallback to gradient + initial
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
        try: # Pillow 9+
            bbox = self.profile_initial_font.getbbox(initial)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x_offset, text_y_offset = bbox[0], bbox[1]
        except AttributeError: # Older Pillow
            text_width, text_height = self.profile_initial_font.getsize(initial)
            text_x_offset, text_y_offset = 0, 0


        text_x = (size - text_width) / 2 - text_x_offset
        text_y = (size - text_height) / 2 - text_y_offset -3 # Small adjustment
        draw.text((text_x, text_y), initial, fill=(255, 255, 255, 220), font=self.profile_initial_font)
        return image

    def _create_pre_rendered_username_label(self):
        name_text = self.username
        try: # Pillow 9+
            bbox = self.profile_name_font.getbbox(name_text)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x_offset, text_y_offset = bbox[0], bbox[1]
        except AttributeError: # Older Pillow
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

    def update_frame(self):
        start_processing_time = time.perf_counter()
        
        try:
            pil_img_from_queue = self.frame_queue.get(block=False) # Non-blocking
        except queue.Empty:
            # No new frame from thread yet, schedule next check
            delay = self.frame_interval // 2 # Check more frequently if queue is empty
            self.after_id = self.master.after(delay, self.update_frame)
            return

        if not self.first_frame_received:
            self._initialize_ui_elements_after_first_frame(pil_img_from_queue.width, pil_img_from_queue.height)

        # Make a copy if you plan to modify it, though paste and draw should be fine on the object from queue
        pil_img = pil_img_from_queue # .copy() if needed

        # Paste pre-rendered profile elements
        if self.pre_rendered_profile_pic and self.pre_rendered_username_label:
            profile_pic_pos_int = (int(self.profile_pic_pos[0]), int(self.profile_pic_pos[1]))
            username_label_pos_int = (int(self.username_label_pos[0]), int(self.username_label_pos[1]))
            pil_img.paste(self.pre_rendered_profile_pic, profile_pic_pos_int, self.pre_rendered_profile_pic)
            pil_img.paste(self.pre_rendered_username_label, username_label_pos_int, self.pre_rendered_username_label)

        # Draw clock
        current_time_ms = int(time.time() * 1000)
        if current_time_ms - self.last_clock_update >= 1000:
            self.current_time_text = time.strftime('%I:%M:%S %p')
            self.last_clock_update = current_time_ms
        
        draw = ImageDraw.Draw(pil_img)
        try: 
            clock_bbox = self.clock_font.getbbox(self.current_time_text)
            clock_text_width = clock_bbox[2] - clock_bbox[0]
        except AttributeError: 
            clock_text_width, _ = self.clock_font.getsize(self.current_time_text)

        clock_x = (self.width - clock_text_width) // 2
        clock_y = int(self.height * 0.1)
        draw.text((int(clock_x+2), int(clock_y+2)), self.current_time_text, font=self.clock_font, fill=(0,0,0,128))
        draw.text((int(clock_x), int(clock_y)), self.current_time_text, font=self.clock_font, fill=(255,255,255,220))

        try:
            self.imgtk = ImageTk.PhotoImage(pil_img)
            self.label.config(image=self.imgtk)
        except Exception as e:
            print(f"Error updating label image: {e}") # Catch errors during PhotoImage conversion or config
            # This can happen if the window is destroyed while an update is pending
        
        self.frames_processed_in_ui += 1
        if self.frames_processed_in_ui % (self.target_fps * 5) == 0:
            elapsed_perf = time.perf_counter() - self.start_time
            if elapsed_perf > 0:
                 fps_perf = self.frames_processed_in_ui / elapsed_perf
                 print(f"UI Update rate: {fps_perf:.2f} FPS (Queue size: {self.frame_queue.qsize()})")
            self.frames_processed_in_ui = 0
            self.start_time = time.perf_counter() 
        
        processing_duration_ms = (time.perf_counter() - start_processing_time) * 1000
        delay = max(1, int(self.frame_interval - processing_duration_ms))
        
        self.after_id = self.master.after(delay, self.update_frame)

    def close(self):
        print("Closing VideoClockScreenSaver...")
        if self.after_id:
            self.master.after_cancel(self.after_id)
            self.after_id = None 
        
        if self.frame_reader_thread and self.frame_reader_thread.is_alive():
            print("Stopping frame reader thread...")
            self.frame_reader_thread.stop()
            self.frame_reader_thread.join(timeout=2) 
            if self.frame_reader_thread.is_alive():
                print("Frame reader thread did not stop in time.")
        print("VideoClockScreenSaver closed.")
