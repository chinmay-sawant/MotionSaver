import tkinter as tk
from tkinter import ttk
import json
import os
import hashlib
from PIL import Image, ImageTk, ImageDraw, ImageFont

# Constants
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "password_config.json")
DEFAULT_PASSWORD = "1234"  # Default password

def load_password():
    """Load password hash from config file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('password_hash')
        except Exception as e:
            print(f"Error loading password config: {e}")
    
    # If file doesn't exist or error occurred, create with default password
    default_hash = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()
    save_password_hash(default_hash)
    return default_hash

def save_password_hash(password_hash):
    """Save password hash to config file"""
    config = {'password_hash': password_hash}
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Error saving password config: {e}")
        return False

def verify_password(password):
    """Verify if the given password is correct"""
    stored_hash = load_password()
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return input_hash == stored_hash

def change_password(old_password, new_password):
    """Change the password if old password is correct"""
    if verify_password(old_password):
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        if save_password_hash(new_hash):
            return True
    return False

class MacOSStyleLogin:
    def __init__(self, parent):
        self.parent = parent
        self.result = False
        self.TRANSPARENT_KEY = '#123456' # Color to be made transparent

        # Create a Toplevel window for the overlay
        self.password_window = tk.Toplevel(self.parent)
        self.password_window.overrideredirect(True) # Remove window decorations
        self.password_window.attributes('-transparentcolor', self.TRANSPARENT_KEY)
        self.password_window.configure(bg=self.TRANSPARENT_KEY)
        
        # Make it stay on top
        self.password_window.attributes('-topmost', True)

        # Position the password input box (e.g., centered, slightly above bottom)
        pwd_width = 300
        pwd_height = 60
        screen_w = self.parent.winfo_screenwidth()
        screen_h = self.parent.winfo_screenheight()

        # Positioning logic:
        # VideoClockScreenSaver draws profile name around screen_h * 0.85 (profile_name_y_base)
        # Profile pic is above that. Username label has some height.
        # Let's estimate the bottom of the username label and place password input below that.
        # Approximate height of username label (font size + padding) could be ~40-50px.
        # profile_name_y_base is the top of the username label.
        # So, bottom of username label is roughly screen_h * 0.85 + 40.
        # We want password input below this.
        
        profile_elements_bottom_approx = int(screen_h * 0.85) + 50 # Estimate bottom of username label
        pos_x = (screen_w - pwd_width) // 2
        pos_y = profile_elements_bottom_approx + 10 # Place 10px below the estimated profile elements
        
        # Ensure it doesn't go off screen
        if pos_y + pwd_height > screen_h:
            pos_y = screen_h - pwd_height - 10 # Place 10px from bottom if too low

        self.password_window.geometry(f"{pwd_width}x{pwd_height}+{pos_x}+{pos_y}")
        
        self.password_input_container = tk.Frame(self.password_window, bg=self.TRANSPARENT_KEY, bd=0, highlightthickness=0)
        self.password_input_container.pack(fill=tk.BOTH, expand=True)

        # Create password entry frame (initially hidden)
        self.create_password_entry()

        # Bind events
        self.setup_bindings()
        
        # Initially focus on the parent to capture key events
        self.parent.focus_set()
        self.password_entry_widget.focus_set()


    def create_password_entry(self):
        """Create password entry with rounded corners"""
        # Use a transparent background for the password frame
        self.password_canvas = tk.Canvas(
            self.password_input_container,
            width=280, height=50, # Adjusted size for a cleaner look
            bg=self.TRANSPARENT_KEY,
            highlightthickness=0, bd=0
        )
        self.password_canvas.pack(pady=5, padx=10)

        x1, y1, x2, y2, r = 5, 5, 275, 45, 15 # Slightly larger radius, adjusted coords
        # Draw rounded rectangle for the input box (macOS style)
        # Fill: A slightly lighter, less opaque dark gray for the input field itself
        # Outline: A subtle gray, changes on focus (focus handled by Entry widget's own mechanisms or custom binding)
        fill_color = '#404040' # Darker gray for input field
        outline_color = '#555555' # Subtle border

        self.password_canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90,
                                        fill=fill_color, outline=outline_color, width=1)
        self.password_canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90,
                                        fill=fill_color, outline=outline_color, width=1)
        self.password_canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90,
                                        fill=fill_color, outline=outline_color, width=1)
        self.password_canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90,
                                        fill=fill_color, outline=outline_color, width=1)
        self.password_canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill_color, outline='')
        self.password_canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill_color, outline='')
        # Lines for border (if not relying on arc outlines)
        self.password_canvas.create_line(x1+r, y1, x2-r, y1, fill=outline_color, width=1)
        self.password_canvas.create_line(x1+r, y2, x2-r, y2, fill=outline_color, width=1)
        self.password_canvas.create_line(x1, y1+r, x1, y2-r, fill=outline_color, width=1)
        self.password_canvas.create_line(x2, y1+r, x2, y2-r, fill=outline_color, width=1)


        self.password_var = tk.StringVar()
        self.password_entry_widget = tk.Entry(
            self.password_canvas, textvariable=self.password_var,
            show='•', font=("Segoe UI", 14), # Slightly larger font
            bg=fill_color, fg='white', insertbackground='white', # Match canvas fill
            relief=tk.FLAT, bd=0, justify='center',
            highlightthickness=1, highlightbackground=outline_color, highlightcolor='#007AFF' # macOS blue focus
        )
        self.password_canvas.create_window(
            (x1+x2)//2, (y1+y2)//2, window=self.password_entry_widget,
            width=(x2-x1)- (2*r) + 10, height=(y2-y1) - r # Adjust width/height for padding
        )

    def setup_bindings(self):
        """Setup event bindings"""
        self.password_window.bind('<KeyPress>', self.on_key_press_pwd_window) # Different handler if needed
        self.password_window.bind('<Return>', self.verify_password_event)
        self.password_window.bind('<Escape>', self.cancel_login)
        
        self.password_entry_widget.bind('<Return>', self.verify_password_event)
        # Let Toplevel Escape handle closing the password entry
        # self.password_entry_widget.bind('<Escape>', self.cancel_login) 
        
    def on_key_press_pwd_window(self, event):
        """Handle any key press in password window"""
        pass # This window primarily reacts to Enter/Escape
    
    def cancel_login(self, event=None):
        self.result = False
        self.cleanup()
    
    def verify_password_event(self, event=None):
        """Verify the entered password"""
        password = self.password_var.get()
        print(f"Attempting to verify password: {password}")  # Debug
        
        if verify_password(password):
            print("Password verified successfully!")  # Debug
            self.result = True
            self.cleanup()
        else:
            print("Password verification failed!")  # Debug
            # Shake animation for wrong password
            self.shake_animation()
            self.password_var.set("")
            self.password_entry_widget.focus_set() # Keep focus after shake
    
    def shake_animation(self):
        """Perform shake animation for wrong password"""
        # Shake the Toplevel window itself
        original_x = self.password_window.winfo_x()
        original_y = self.password_window.winfo_y()
        for i in range(8):
            offset = 15 if i % 2 == 0 else -15
            self.password_window.geometry(f"+{original_x + offset}+{original_y}")
            self.password_window.update_idletasks()
            self.password_window.after(40)
        self.password_window.geometry(f"+{original_x}+{original_y}")
    
    def cleanup(self):
        """Clean up the login interface"""
        if hasattr(self, 'password_window') and self.password_window.winfo_exists():
            self.password_window.destroy()

def verify_password_dialog_macos(parent):
    """Show the macOS-style login screen and return whether verification succeeded"""
    login_screen = MacOSStyleLogin(parent)
    # This makes the call blocking until the Toplevel window is destroyed
    parent.wait_window(login_screen.password_window)
    return login_screen.result
