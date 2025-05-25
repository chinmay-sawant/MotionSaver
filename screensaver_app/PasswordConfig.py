import tkinter as tk
from tkinter import ttk
import json
import os
import hashlib
from PIL import Image, ImageTk, ImageDraw, ImageFont

# Adjust path to go one level up to find config files in the root project directory
CONFIG_FILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config'))
USER_CONFIG_FILE = os.path.join(CONFIG_FILE_DIR, "userconfig.json") 
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "User" # Default for creating a new config if none exists

def load_config():
    """Load entire user configuration from userconfig.json"""
    if not os.path.exists(USER_CONFIG_FILE):
        default_hash = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
        default_config = {
            "users": [
                {"username": DEFAULT_USERNAME, "password_hash": default_hash}
            ],
            "default_user_for_display": DEFAULT_USERNAME,
            "profile_pic_path": "",
            "profile_pic_path_crop": "",  # Add crop path with empty default
            "video_path": "video.mp4",
            "theme": "light",
            "clock_font_family": "Segoe UI Emoji",
            "clock_font_size": 64,
            "ui_font_family": "Arial",
            "ui_font_size": 18
        }
        save_config(default_config)
        return default_config
    try:
        with open(USER_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure essential keys exist with defaults
            if "users" not in config or not isinstance(config["users"], list) or not config["users"]:
                default_hash = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
                config["users"] = [{"username": DEFAULT_USERNAME, "password_hash": default_hash}]
            if "default_user_for_display" not in config:
                config["default_user_for_display"] = config["users"][0].get("username", DEFAULT_USERNAME)
            if "profile_pic_path" not in config: config["profile_pic_path"] = ""
            if "profile_pic_path_crop" not in config: config["profile_pic_path_crop"] = config.get("profile_pic_path", "")
            if "video_path" not in config: config["video_path"] = "video.mp4"
            if "theme" not in config: config["theme"] = "light"
            if "clock_font_family" not in config: config["clock_font_family"] = "Segoe UI Emoji"
            if "clock_font_size" not in config: config["clock_font_size"] = 64
            if "ui_font_family" not in config: config["ui_font_family"] = "Arial"
            if "ui_font_size" not in config: config["ui_font_size"] = 18
            return config
    except Exception as e:
        print(f"Error loading user config: {e}, returning hardcoded defaults.")
        default_hash = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
        return { # Hardcoded fallback
            "users": [{"username": DEFAULT_USERNAME, "password_hash": default_hash}],
            "default_user_for_display": DEFAULT_USERNAME,
            "profile_pic_path": "", "profile_pic_path_crop": "",
            "video_path": "video.mp4", "theme": "light",
            "clock_font_family": "Segoe UI Emoji", "clock_font_size": 64,
            "ui_font_family": "Arial", "ui_font_size": 18
        }

def save_config(config_data):
    """Save entire configuration data to userconfig.json"""
    try:
        # Ensure the config directory exists
        os.makedirs(CONFIG_FILE_DIR, exist_ok=True)
        
        # Attempt to write to the file
        with open(USER_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # Verify by trying to read it back (optional, but good for diagnostics)
        # This step is more for confirming the write was successful immediately.
        # If this fails, it might indicate a more subtle issue than just permissions.
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                json.load(f)
            # print(f"Successfully saved and verified config to {USER_CONFIG_FILE}") # Optional success log
        except Exception as e_readback:
            print(f"CRITICAL ERROR: Config saved to {USER_CONFIG_FILE}, but failed to read back immediately: {e_readback}")
            print(f"This could indicate a problem with file corruption or very intermittent write issues.")
            # Depending on severity, you might want to return False here or handle it.
            # For now, we'll assume the primary write was okay if it didn't throw an exception.

        return True
    except IOError as e_io:
        print(f"IOError saving user config to {USER_CONFIG_FILE}: {e_io}")
        print(f"Please check file permissions and path.")
        return False
    except Exception as e:
        print(f"Unexpected error saving user config to {USER_CONFIG_FILE}: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        pwd_height = 60 # Reduced height since we only show password field now
        screen_w = self.parent.winfo_screenwidth()
        screen_h = self.parent.winfo_screenheight()
        
        profile_elements_bottom_approx = int(screen_h * 0.85) + 50 
        pos_x = (screen_w - pwd_width) // 2
        pos_y = profile_elements_bottom_approx + 10 
        
        if pos_y + pwd_height > screen_h:
            pos_y = screen_h - pwd_height - 10 

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

def verify_password_dialog_macos(root):
    """Shows a macOS-style password dialog, returns True if password was verified"""
    dialog = MacOSStyleLogin(root)
    root.wait_window(dialog.password_window)
    # Just return True/False for login success 
    return dialog.result