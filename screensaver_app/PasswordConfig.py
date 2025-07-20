import tkinter as tk
from tkinter import ttk
import json
import os

from PIL import Image, ImageTk, ImageDraw, ImageFont
import hashlib
# Add central logging
import sys

from screensaver_app.video_player import VideoClockScreenSaver
# Ensure parent directory is in sys.path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('PasswordConfig')

from utils.config_utils import find_user_config_path, load_config, save_config
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "User" # Default for creating a new config if none exists
from utils.wallpaper import set_windows_wallpaper

def verify_password(username_attempt, password_attempt):
    """Verify if the given username and password are correct."""
    config = load_config()
    users = config.get("users", [])
    for user in users:
        if user.get("username") == username_attempt:
            stored_hash = user.get("password_hash")
            if stored_hash:
                input_hash = hashlib.sha256(password_attempt.encode()).hexdigest()
                if input_hash == stored_hash:
                    return True # Correct username and password
            return False # Username found, but password incorrect or hash missing
    return False # Username not found

def change_password(username_to_change, old_password, new_password):
    """Change the password for a specific user if old password is correct."""
    config = load_config()
    users = config.get("users", [])
    user_found_and_changed = False
    for user_obj in users:
        if user_obj.get("username") == username_to_change:
            stored_hash = user_obj.get("password_hash")
            input_old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            if stored_hash == input_old_hash:
                new_hash = hashlib.sha256(new_password.encode()).hexdigest()
                user_obj["password_hash"] = new_hash
                user_found_and_changed = True
                break 
    if user_found_and_changed:
        return save_config(config)
    return False

def add_user(username, password):
    """Add a new user."""
    config = load_config()
    users = config.get("users", [])
    if any(u.get("username") == username for u in users):
        return False, "Username already exists."
    
    new_hash = hashlib.sha256(password.encode()).hexdigest()
    users.append({"username": username, "password_hash": new_hash})
    config["users"] = users
    
    # If this is the first user being added after a potential empty list (e.g. manual config edit)
    if len(users) == 1 and not config.get("default_user_for_display"):
        config["default_user_for_display"] = username
    print (f"Adding new user: {username}, default_user_for_display: {config.get('default_user_for_display')}")
    if save_config(config):
        return True, "User added successfully."
    return False, "Failed to save configuration."

def delete_user(username_to_delete):
    """Delete a user."""
    config = load_config()
    users = config.get("users", [])
    
    if len(users) <= 1:
        return False, "Cannot delete the last user."

    user_found = any(u.get("username") == username_to_delete for u in users)
    if not user_found:
        return False, "User not found."

    users = [user for user in users if user.get("username") != username_to_delete]
    config["users"] = users
    
    # If the deleted user was the default user, set a new default
    if config.get("default_user_for_display") == username_to_delete:
        if users: # If there are remaining users
            config["default_user_for_display"] = users[0].get("username")
        else: # This case should be prevented by "Cannot delete the last user" check
            config["default_user_for_display"] = "" 

    if save_config(config):
        return True, "User deleted successfully."
    return False, "Failed to save configuration."

def verify_password_hash(password, stored_hash):
    """Verify if the given password matches the stored hash."""
    if not stored_hash:
        return False
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return input_hash == stored_hash

class MacOSStyleLogin:
    def __init__(self, parent):
        self.parent = parent
        self.result = False # Will be True on success, False otherwise
        self.TRANSPARENT_KEY = '#123456' 

        self.config = load_config() # Load config to get default user
        self.username_to_verify = self.config.get("default_user_for_display", DEFAULT_USERNAME)
        # Ensure the default_user_for_display actually exists, or pick the first user
        user_exists = any(u.get("username") == self.username_to_verify for u in self.config.get("users", []))
        if not user_exists and self.config.get("users"):
            self.username_to_verify = self.config.get("users")[0].get("username", DEFAULT_USERNAME)

        self.password_window = tk.Toplevel(self.parent)
        self.password_window.overrideredirect(True) 
        self.password_window.attributes('-transparentcolor', self.TRANSPARENT_KEY)
        self.password_window.configure(bg=self.TRANSPARENT_KEY)
        self.password_window.attributes('-topmost', True)

        pwd_width = 300
        pwd_height = 60 
        
        # Get geometry of the parent window (the main screensaver window)
        # to determine which screen it is on and its dimensions.
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()

        # Position at center bottom of the parent's screen area
        pos_x = parent_x + (parent_width - pwd_width) // 2
        # Position at 95% down from the top (very close to bottom)
        pos_y = parent_y + parent_height - pwd_height

        # Ensure it doesn't go off-screen
        if pos_y + pwd_height > parent_y + parent_height:
            pos_y = parent_y + parent_height - pwd_height - 10  # 10px margin from bottom
        if pos_y < parent_y:
            pos_y = parent_y + 10  # 10px margin from top
        if pos_x < parent_x:
            pos_x = parent_x + 10  # 10px margin from left
        if pos_x + pwd_width > parent_x + parent_width:
            pos_x = parent_x + parent_width - pwd_width - 10  # 10px margin from right

        self.password_window.geometry(f"{pwd_width}x{pwd_height}+{pos_x}+{pos_y}")
        
        self.password_input_container = tk.Frame(self.password_window, bg=self.TRANSPARENT_KEY, bd=0, highlightthickness=0)
        self.password_input_container.pack(fill=tk.BOTH, expand=True, pady=5)

        self.create_login_fields() 
        self.setup_bindings()
        
        self.password_window.focus_force()
        self.password_entry_widget.focus_set()

    def create_login_fields(self):
        # Password field (only field shown now)
        self.password_canvas = tk.Canvas(
            self.password_input_container,
            width=280, height=50, 
            bg=self.TRANSPARENT_KEY,
            highlightthickness=0, bd=0
        )
        self.password_canvas.pack(pady=5)

        x1, y1, x2, y2, r = 5, 5, 275, 45, 15 
        outline_color = '#888888' 
        border_width = 1    

        self.password_canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90,
                                        style=tk.ARC, outline=outline_color, width=border_width)
        self.password_canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90,
                                        style=tk.ARC, outline=outline_color, width=border_width)
        self.password_canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90,
                                        style=tk.ARC, outline=outline_color, width=border_width)
        self.password_canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90,
                                        style=tk.ARC, outline=outline_color, width=border_width)
        
        self.password_canvas.create_line(x1+r, y1, x2-r, y1, fill=outline_color, width=border_width)
        self.password_canvas.create_line(x1+r, y2, x2-r, y2, fill=outline_color, width=border_width)
        self.password_canvas.create_line(x1, y1+r, x1, y2-r, fill=outline_color, width=border_width)
        self.password_canvas.create_line(x2, y1+r, x2, y2-r, fill=outline_color, width=border_width)

        self.password_var = tk.StringVar()
        self.password_entry_widget = tk.Entry(
            self.password_canvas, textvariable=self.password_var,
            font=("Segoe UI", 14), 
            bg=self.TRANSPARENT_KEY, 
            fg='white', insertbackground='white', 
            relief=tk.FLAT, bd=0, show="•",
            justify='center',
            highlightthickness=0,
        )
        self.password_canvas.create_window(
            (x1+x2)//2, (y1+y2)//2, window=self.password_entry_widget,
            width=(x2-x1)- (2*r) + 10, height=(y2-y1) - r
        )

    def setup_bindings(self):
        # Key bindings 
        self.password_entry_widget.bind("<Return>", self.verify_password)
        self.password_entry_widget.bind("<Escape>", self.cancel)

    def verify_password(self, event=None):
        password = self.password_var.get()
        for user in self.config.get("users", []):
            if user.get("username") == self.username_to_verify:
                stored_hash = user.get("password_hash", "")
                if verify_password_hash(password, stored_hash):
                    self.result = True
                    self.close()
                    return
                else:
                    self.shake_window()
                    self.password_var.set("")
                    return
        # No matching username or incorrect password
        self.shake_window()
        self.password_var.set("")

    def shake_window(self):
        # Simple window shaking animation for wrong password
        original_pos_x = self.password_window.winfo_x()
        original_pos_y = self.password_window.winfo_y()
        
        shake_distances = [15, -15, 10, -10, 5, -5, 0]
        delay = 50  # milliseconds
        
        def _shake(distances):
            if not distances:
                self.password_window.geometry(f"+{original_pos_x}+{original_pos_y}")
                return
                
            d = distances[0]
            self.password_window.geometry(f"+{original_pos_x + d}+{original_pos_y}")
            self.password_window.after(
                delay, _shake, distances[1:]
            )
            
        _shake(shake_distances)

    def cancel(self, event=None):
        self.result = False
        self.close()

    def close(self):
        self.password_window.destroy()

def verify_password_dialog_macos(root, video_clock_screensaver=None):
    """Shows a macOS-style password dialog, returns True if password was verified.
    Pauses video, saves timestamp, and sets lock screen image if video_clock_screensaver is provided."""
    # Pause video and save timestamp if screensaver instance is provided
    if video_clock_screensaver:
        try:
            # 1. Pause video thread
      
            VideoClockScreenSaver.pause_video(video_clock_screensaver)
            # 2. Get current timestamp from the frame reader thread
            timestamp = VideoClockScreenSaver.get_current_time_seconds(video_clock_screensaver)
            # 3. Save timestamp to config
            config = load_config()
            config['last_video_timestamp'] = timestamp if timestamp else 0
            save_config(config)

            # 4. Take screenshot of the RAW frame (no UI) and set as lock screen
            raw_frame_pil = getattr(video_clock_screensaver, 'last_raw_frame', None)
            if raw_frame_pil:
                from PIL import Image, ImageFilter, ImageTk
                import tempfile
                
                # Save the clean raw frame to a temp file for the lock screen
                temp_path = os.path.join(tempfile.gettempdir(), "screensaver_lock_screen.png")
                # Save screenshot to temp file
                # Determine the directory of PhotoEngine.py or PhotoEngine.exe
                if getattr(sys, 'frozen', False):
                    # Running as PyInstaller EXE
                    engine_dir = os.path.dirname(sys.executable)
                else:
                    # Running as script
                    engine_dir = os.path.dirname(os.path.abspath(__file__))
                temp_path = os.path.join(engine_dir, "screensaver_lock_screen.png")
                raw_frame_pil.save(temp_path, format="PNG")
                set_windows_wallpaper(temp_path)

            # 5. Take screenshot of the PROCESSED frame (with UI), apply blur, and update display
            processed_frame_pil = getattr(video_clock_screensaver, 'last_processed_frame', None)
            if processed_frame_pil:
                from PIL import Image, ImageFilter, ImageTk
                
                # Apply a glassy blur effect
                blurred_frame = processed_frame_pil.filter(ImageFilter.GaussianBlur(radius=15))
                
                # Update the screensaver display with the blurred frame
                if video_clock_screensaver.label.winfo_exists():
                    imgtk_blurred = ImageTk.PhotoImage(blurred_frame)
                    video_clock_screensaver.imgtk = imgtk_blurred # Keep reference
                    video_clock_screensaver.label.config(image=imgtk_blurred)
                    video_clock_screensaver.label.update_idletasks()

        except Exception as e:
            logger.error(f"Error during pause/screenshot/lockscreen: {e}")

    dialog = MacOSStyleLogin(root)
    root.wait_window(dialog.password_window)
    # Just return True/False for login success 
    return dialog.result