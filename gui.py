import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
from PIL import Image, ImageTk, ImageDraw 
import os
import json
import sys # Import sys
import time # Import time for typeahead timeout
import subprocess
import win32serviceutil
import win32service

# Initialize central logging
from central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('GUI')

# Assuming PasswordConfig.py is in the same directory (package)
# This will work when gui.py is imported as part of the package
# For direct execution, sys.path needs adjustment (see if __name__ == '__main__')
try:
    from screensaver_app.PasswordConfig import load_config, save_config, change_password, add_user, delete_user
except ImportError:
    # Fallback for direct script execution (no parent package)
    # import sys # sys already imported
    # import os # os already imported
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'screensaver_app')))
    from screensaver_app.PasswordConfig import load_config, save_config, change_password, add_user, delete_user

# Define paths relative to this file's location if needed, or use absolute paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# Define icons path
ICONS_DIR = os.path.join(os.path.dirname(__file__), 'screensaver_app', 'icons')

# USER_CONFIG_PATH is now implicitly handled by load_config/save_config

class CroppingWindow(tk.Toplevel):
    def __init__(self, parent, image_path, save_path=None):
        super().__init__(parent)
        self.title("Crop Image")
        self.image_path = image_path
        self.save_path = save_path
        self.crop_coords = None
        self.original_image = Image.open(image_path)
        self.crop_saved = False  # Flag to track if cropping was completed
        
        # Resize for display if too large, but keep original for cropping
        self.display_image = self.original_image.copy()
        max_display_size = (600, 400)
        self.display_image.thumbnail(max_display_size, Image.Resampling.LANCZOS)
        self.img_tk = ImageTk.PhotoImage(self.display_image)

        self.canvas = tk.Canvas(self, width=self.display_image.width, height=self.display_image.height, cursor="cross")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img_tk)
        self.canvas.pack(pady=10, padx=10)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Improved button frame with better styling
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        
        # Style for the buttons
        btn_style = ttk.Style()
        btn_style.configure("Action.TButton", padding=5)
        
        # Crop and Save button with more prominent styling
        self.crop_btn = ttk.Button(btn_frame, text="Crop and Save", command=self.crop_and_save, style="Action.TButton")
        self.crop_btn.pack(side=tk.LEFT, padx=10)
        
        # Cancel button
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.on_cancel, style="Action.TButton")
        self.cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # Properly handle window closing
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.grab_set() # Make modal
        self.wait_window() # Wait until this window is closed

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_mouse_drag(self, event):
        cur_x, cur_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        # Ensure coordinates are ordered correctly (top-left, bottom-right)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Scale crop coordinates from display image to original image
        scale_x = self.original_image.width / self.display_image.width
        scale_y = self.original_image.height / self.display_image.height
        
        self.crop_coords = (int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y))

    def crop_and_save(self):
        if self.crop_coords:
            try:
                cropped_image = self.original_image.crop(self.crop_coords)
                save_path = self.save_path
                
                # If no specific save path was provided, ask the user
                if not save_path:
                    save_path = filedialog.asksaveasfilename(
                        initialfile=os.path.basename(self.image_path),
                        defaultextension=".png", # Or original extension
                        filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
                    )
                    
                if save_path:
                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                    cropped_image.save(save_path)
                    messagebox.showinfo("Success", f"Cropped image saved to {save_path}")
                    self.image_path = save_path # Update path to the new cropped image
                    self.crop_saved = True  # Mark as successfully saved
                    self.destroy()
                else: # User cancelled save dialog
                    self.crop_coords = None # Reset if save is cancelled
            except Exception as e:
                messagebox.showerror("Error", f"Failed to crop or save image: {e}")
        else:
            messagebox.showwarning("No Selection", "Please select an area to crop.")
    
    def on_cancel(self):
        # Just close the window without setting crop_saved flag
        self.destroy()

class ScreenSaverApp:
    def __init__(self, master):
        self.master = master
        master.title("Screen Saver Settings")
        master.state('zoomed') # Open maximized

        self.config = load_config()
        self.current_theme = tk.StringVar(value=self.config.get("theme", "light"))
        self.selected_clock_font_family = tk.StringVar(value=self.config.get("clock_font_family", "Segoe UI Emoji"))
        self.selected_clock_font_size = tk.IntVar(value=self.config.get("clock_font_size", 64))
        self.selected_ui_font_family = tk.StringVar(value=self.config.get("ui_font_family", "Arial"))
        self.selected_ui_font_size = tk.IntVar(value=self.config.get("ui_font_size", 18))
        
        # New variables for additional features
        self.screensaver_timer = tk.IntVar(value=self.config.get("screensaver_timer_minutes", 10))
        self.enable_stock_widget = tk.BooleanVar(value=self.config.get("enable_stock_widget", False))
        self.enable_media_widget = tk.BooleanVar(value=self.config.get("enable_media_widget", False))
        self.stock_market = tk.StringVar(value=self.config.get("stock_market", "NASDAQ"))
        self.weather_widget_var = tk.BooleanVar(value=self.config.get("enable_weather_widget", True))
        self.weather_pincode_var = tk.StringVar(value=self.config.get("weather_pincode", "400068"))
        self.weather_country_var = tk.StringVar(value=self.config.get("weather_country", "IN"))
        self.admin_mode_var = tk.BooleanVar(value=self.config.get("run_as_admin", False))


        # For combobox typeahead
        self.combo_typeahead_state = {} 

        self.setup_styles()
       
        # Load icons
        self.add_user_icon = None
        self.change_password_icon = None
        self.copilot_icon = None # For footer
        try:
            add_icon_path = os.path.join(ICONS_DIR, "add_user_icon.png")
            if os.path.exists(add_icon_path):
                self.add_user_icon = ImageTk.PhotoImage(Image.open(add_icon_path).resize((20, 20), Image.Resampling.LANCZOS))
            
            change_pwd_icon_path = os.path.join(ICONS_DIR, "change_password_icon.png")
            if os.path.exists(change_pwd_icon_path):
                self.change_password_icon = ImageTk.PhotoImage(Image.open(change_pwd_icon_path).resize((20, 20), Image.Resampling.LANCZOS))
            
            copilot_icon_path = os.path.join(ICONS_DIR, "copilot.png") # Copilot icon
            if os.path.exists(copilot_icon_path):
                self.copilot_icon = ImageTk.PhotoImage(Image.open(copilot_icon_path).resize((20, 20), Image.Resampling.LANCZOS))        
        except Exception as e:
            logger.error(f"Error loading icons: {e}")
         # --- Main Frame ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid columns for main_frame to have 2 expanding columns
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        current_row = 0
        current_col = 0

        # --- Profile Picture ---
        pic_frame = ttk.LabelFrame(main_frame, text="Profile Picture", padding="10")
        pic_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col += 1

        self.profile_pic_path_var = tk.StringVar(value=self.config.get("profile_pic_path", ""))
        self.profile_pic_path_crop_var = tk.StringVar(value=self.config.get("profile_pic_path_crop", ""))
        if not self.profile_pic_path_crop_var.get() and self.profile_pic_path_var.get():
            # Initialize crop path with original path if not already set
            self.profile_pic_path_crop_var.set(self.profile_pic_path_var.get())
            
        ttk.Label(pic_frame, text="Path:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.profile_pic_entry = ttk.Entry(pic_frame, textvariable=self.profile_pic_path_var, width=40)
        self.profile_pic_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(pic_frame, text="Browse...", command=self.browse_profile_pic).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(pic_frame, text="Crop Image", command=self.crop_profile_pic).grid(row=0, column=3, padx=5, pady=5)
        pic_frame.columnconfigure(1, weight=1)


        # --- Video Path ---
        video_frame = ttk.LabelFrame(main_frame, text="Screen Saver Video", padding="10")
        video_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col = 0 # Reset column
        current_row += 1 # Move to next row

        self.video_path_var = tk.StringVar(value=self.config.get("video_path", "video.mp4"))
        ttk.Label(video_frame, text="Path:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.video_path_entry = ttk.Entry(video_frame, textvariable=self.video_path_var, width=40)
        self.video_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(video_frame, text="Browse...", command=self.browse_video).grid(row=0, column=2, padx=5, pady=5)
        video_frame.columnconfigure(1, weight=1)

        # --- Clock Font Settings ---
        font_frame = ttk.LabelFrame(main_frame, text="Clock Appearance", padding="10")
        font_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col += 1

        ttk.Label(font_frame, text="Font Family:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_families = sorted(list(tkfont.families(root=self.master))) 
        self.font_combo = ttk.Combobox(font_frame, textvariable=self.selected_clock_font_family, values=self.font_families, width=37, state="readonly")
        self.font_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.style.configure('FontCombo.TCombobox', background="#222222", foreground="#FFFFFF", fieldbackground="#222222", selectbackground="#222222")
        self.font_combo.configure(style='FontCombo.TCombobox')
        current_font_in_list = self.selected_clock_font_family.get()
        if current_font_in_list in self.font_families:
            self.font_combo.set(current_font_in_list)
        elif self.font_families: 
            self.font_combo.current(0) 
            self.selected_clock_font_family.set(self.font_combo.get())
        else: 
            self.selected_clock_font_family.set("Default") 
        self.font_preview_label = ttk.Label(font_frame, text="Preview Text", font=(self.selected_clock_font_family.get(), 12))
        self.font_preview_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.font_combo.bind("<<ComboboxSelected>>", self.update_font_preview)
        self.font_combo.bind("<Up>", lambda e: self._combo_nav(self.font_combo, -1) or "break")
        self.font_combo.bind("<Down>", lambda e: self._combo_nav(self.font_combo, 1) or "break")
        self.font_combo.bind("<Key>", lambda e: self._combo_typeahead(self.font_combo, e))
        ttk.Label(font_frame, text="Font Size:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_size_spinbox = ttk.Spinbox(font_frame, from_=10, to=200, increment=2, textvariable=self.selected_clock_font_size, width=5)
        self.font_size_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        font_frame.columnconfigure(1, weight=1)


        # --- UI Font Settings ---
        ui_font_frame = ttk.LabelFrame(main_frame, text="UI Appearance", padding="10")
        ui_font_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col = 0
        current_row += 1

        ttk.Label(ui_font_frame, text="Font Family:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ui_font_families = sorted(list(tkfont.families(root=self.master))) 
        self.ui_font_combo = ttk.Combobox(ui_font_frame, textvariable=self.selected_ui_font_family, values=self.ui_font_families, width=37, state="readonly")
        self.ui_font_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.style.configure('UIFontCombo.TCombobox', background="#222222", foreground="#FFFFFF", fieldbackground="#222222", selectbackground="#222222")
        self.ui_font_combo.configure(style='UIFontCombo.TCombobox')
        current_ui_font_in_list = self.selected_ui_font_family.get()
        if current_ui_font_in_list in self.ui_font_families:
            self.ui_font_combo.set(current_ui_font_in_list)
        elif self.ui_font_families: 
            self.ui_font_combo.current(0) 
            self.selected_ui_font_family.set(self.ui_font_combo.get())
        else: 
            self.selected_ui_font_family.set("Default") 
        self.ui_font_preview_label = ttk.Label(ui_font_frame, text="Preview Text", font=(self.selected_ui_font_family.get(), 12))
        self.ui_font_preview_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.ui_font_combo.bind("<<ComboboxSelected>>", self.update_ui_font_preview)
        self.ui_font_combo.bind("<Up>", lambda e: self._combo_nav(self.ui_font_combo, -1) or "break")
        self.ui_font_combo.bind("<Down>", lambda e: self._combo_nav(self.ui_font_combo, 1) or "break")
        self.ui_font_combo.bind("<Key>", lambda e: self._combo_typeahead(self.ui_font_combo, e))
        ttk.Label(ui_font_frame, text="Font Size:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.ui_font_size_spinbox = ttk.Spinbox(ui_font_frame, from_=10, to=200, increment=2, textvariable=self.selected_ui_font_size, width=5)
        self.ui_font_size_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ui_font_frame.columnconfigure(1, weight=1)

        # --- Theme Toggle ---
        theme_frame = ttk.LabelFrame(main_frame, text="Appearance", padding="10")
        theme_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col += 1
        self.theme_toggle_button = ttk.Checkbutton(
            theme_frame, text="Dark Mode", variable=self.current_theme,
            onvalue="dark", offvalue="light", command=self.toggle_theme
        )
        self.theme_toggle_button.pack(anchor=tk.W, padx=5, pady=5) # pack is fine for simple content

        # --- Timer Configuration ---
        timer_frame = ttk.LabelFrame(main_frame, text="Screensaver Timer", padding="10")
        timer_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col = 0
        current_row += 1
        ttk.Label(timer_frame, text="Start after (minutes):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.timer_spinbox = ttk.Spinbox(timer_frame, from_=1, to=120, increment=1, textvariable=self.screensaver_timer, width=10)
        self.timer_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # --- Service Management ---
        service_frame = ttk.LabelFrame(main_frame, text="Windows Service", padding="10")
        service_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col += 1
        self.service_status_label = ttk.Label(service_frame, text="Service Status: Unknown")
        self.service_status_label.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W) # Adjusted columnspan
        ttk.Button(service_frame, text="Install Service", command=self.install_service).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(service_frame, text="Start Service", command=self.start_service).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(service_frame, text="Stop Service", command=self.stop_service).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(service_frame, text="Uninstall Service", command=self.uninstall_service).grid(row=1, column=3, padx=5, pady=5) # Moved to col 3


        # --- Widget Configuration ---
        widget_frame = ttk.LabelFrame(main_frame, text="Widgets", padding="10")
        widget_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        current_col = 0
        current_row += 1
        self.stock_check = ttk.Checkbutton(
            widget_frame, 
            text="Enable Stock Market Widget", 
            variable=self.enable_stock_widget
        )
        self.stock_check.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Label(widget_frame, text="Market:").grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.stock_market_combo = ttk.Combobox(
            widget_frame, 
            textvariable=self.stock_market,
            values=["NASDAQ", "NYSE", "CRYPTO", "NSE"], 
            state="readonly",
            width=15,
            style="StockMarketCombo.TCombobox" # Assign a specific style
        )
        self.stock_market_combo.grid(row=0, column=2, padx=5, pady=5)
        self.media_check = ttk.Checkbutton(
            widget_frame, 
            text="Enable Media Player Widget", 
            variable=self.enable_media_widget
        )
        self.media_check.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W) # Span for better layout

        # Media Widget Toggle
        media_frame = ttk.Frame(widget_frame)
        media_frame.grid(row=2, column=0, columnspan=3, pady=5, sticky="ew")
        
        self.media_widget_var = tk.BooleanVar(value=self.config.get("enable_media_widget", False))
        media_check = ttk.Checkbutton(media_frame, text="Enable Media Widget", variable=self.media_widget_var)
        media_check.pack(side=tk.LEFT, padx=5)
        
        # Weather Widget Toggle
        weather_frame = ttk.Frame(widget_frame)
        weather_frame.grid(row=3, column=0, columnspan=3, pady=5, sticky="ew")
        
        self.weather_widget_var = tk.BooleanVar(value=self.config.get("enable_weather_widget", True))
        weather_check = ttk.Checkbutton(weather_frame, text="Enable Weather Widget", variable=self.weather_widget_var)
        weather_check.pack(side=tk.LEFT, padx=5)
        
        # Weather settings sub-frame
        weather_settings_frame = ttk.Frame(weather_frame)
        weather_settings_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        ttk.Label(weather_settings_frame, text="Pincode:").pack(side=tk.LEFT, padx=(0, 5))
        self.weather_pincode_var = tk.StringVar(value=self.config.get("weather_pincode", "400068"))
        pincode_entry = ttk.Entry(weather_settings_frame, textvariable=self.weather_pincode_var, width=10)
        pincode_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(weather_settings_frame, text="Country:").pack(side=tk.LEFT, padx=(0, 5))
        self.weather_country_var = tk.StringVar(value=self.config.get("weather_country", "IN"))
        country_entry = ttk.Entry(weather_settings_frame, textvariable=self.weather_country_var, width=5)
        country_entry.pack(side=tk.LEFT)

        # --- System Settings (Admin Toggle) ---
        system_settings_frame = ttk.LabelFrame(main_frame, text="System Settings", padding="10")
        system_settings_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        # If current_col was 0 after widget_frame, this new frame might go to column 0 or 1
        # depending on how you want the layout. Let's assume it takes the next available slot.
        # If widget_frame took current_row, col 0, then this could be current_row, col 1
        # Or if widget_frame spanned, this is next_row, col 0.
        # Based on previous grid, widget_frame was (current_row, col 0). So this is (current_row, col 1)
        # Or if widget_frame was the last in its row, this starts a new row:
        # current_col = 0 # Reset column for new conceptual row if needed
        # current_row +=1 # Increment row
        # system_settings_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Let's assume it's placed after widget_frame in the grid flow
        # If widget_frame was at (current_row, 0) and was the only item in that column for that row:
        current_col +=1 # Move to next column if previous was single column
        if current_col >= 2: # Max 2 columns, so start new row
            current_col = 0
            current_row +=1
        system_settings_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")
        # And then the user management frame would follow.
        # This logic depends heavily on the exact state of current_row and current_col before this block.
        # A simpler approach is to just increment current_row if the previous section filled the columns.
        # Let's assume widget_frame was at (current_row, 0). If it's the only thing in that row,
        # then system_settings_frame can go to (current_row, 1).
        # If widget_frame spanned 2 columns, then system_settings_frame must go to (current_row + 1, 0).

        # Given the previous structure, widget_frame was at (current_row, 0).
        # Let's put System Settings next to it if there's space, or on a new row.
        # If current_col was 0 after widget_frame, this means widget_frame was the start of a row.
        # So, system_settings_frame can go to (current_row, 1)
        # system_settings_frame.grid(row=current_row, column=1, padx=5, pady=5, sticky="nsew")
        # current_col = 0 # Reset for next row
        # current_row += 1 # Next section will be on a new row

        # Simpler: Assume each major section gets its own row or pair.
        # If widget_frame was the last item on its row:
        # current_row += 1
        # current_col = 0
        # system_settings_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")


        admin_check = ttk.Checkbutton(system_settings_frame, text="Run as Administrator (requires app restart)",
                                      variable=self.admin_mode_var)
        admin_check.pack(anchor=tk.W, padx=5, pady=5)
        admin_info_label = ttk.Label(system_settings_frame,
                                     text="Enable if certain features require admin rights (e.g., service management, task manager control).",
                                     font=('Arial', 8), wraplength=300, justify=tk.LEFT)
        admin_info_label.pack(anchor=tk.W, padx=5, pady=(0,5))


        # --- User Management ---
        user_mgmt_frame = ttk.LabelFrame(main_frame, text="User Management", padding="10")
        # Ensure user_mgmt_frame is placed correctly after system_settings_frame
        current_row += 1 # Increment row after the row containing system_settings_frame
        current_col = 0  # Reset column for the new row
        user_mgmt_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        current_row += 1 # current_row is now the row *after* user_mgmt_frame
        # current_col is implicitly 0 after a columnspan

        self.user_tree = ttk.Treeview(user_mgmt_frame, columns=("username",), show="headings", height=3)
        self.user_tree.heading("username", text="Username")
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5) # pack is fine here
        
        user_actions_frame = ttk.Frame(user_mgmt_frame)
        user_actions_frame.pack(side=tk.LEFT, padx=5, fill=tk.Y) # pack is fine here

        add_user_btn = ttk.Button(user_actions_frame, text="Add", image=self.add_user_icon, compound=tk.LEFT, command=self.add_user_dialog)
        add_user_btn.pack(fill=tk.X, pady=3, ipady=2) 
        
        change_pwd_btn = ttk.Button(user_actions_frame, text="Password", image=self.change_password_icon, compound=tk.LEFT, command=self.change_password_dialog)
        change_pwd_btn.pack(fill=tk.X, pady=3, ipady=2)

        delete_user_btn = ttk.Button(user_actions_frame, text="Delete User", command=self.delete_user_dialog) 
        delete_user_btn.pack(fill=tk.X, pady=3, ipady=2)
        
        self.load_users_to_tree()

        # --- Footer Label ---
        # current_row is the first row available after user_mgmt_frame.
        # Skip one row means placing the footer at current_row + 1.
        footer_row = current_row + 1 
        
        footer_outer_frame = ttk.Frame(main_frame) # Frame to help with centering
        footer_outer_frame.grid(row=footer_row, column=0, columnspan=2, pady=(10,0)) # pady top for "skip row" effect

        self.footer_label = ttk.Label(
            footer_outer_frame, 
            text="Made In India With \u2665 Using GitHub Copilot", 
            image=self.copilot_icon, 
            compound=tk.RIGHT # Icon to the right of text
        )
        self.footer_label.pack() # Pack will center it in the footer_outer_frame

        # --- Save Button ---
        save_button_row = footer_row + 1
        save_button = ttk.Button(main_frame, text="Save Settings", command=self.save_settings)
        save_button.grid(row=save_button_row, column=0, columnspan=2, pady=20, sticky="s") 
        main_frame.rowconfigure(save_button_row, weight=1) # Allow space below last content to push save button down

        
        # Configure grid column weights for resizing (already done for main_frame)
        # For individual LabelFrames, internal column weights are set where needed.
        
        master.minsize(600, 700) # Adjusted minsize for better grid layout view
        self.apply_theme()

        self.update_service_status()

    def load_users_to_tree(self):
        for i in self.user_tree.get_children():
            self.user_tree.delete(i)
        
        self.config = load_config() # Reload config
        users = self.config.get("users", [])
        for user in users:
            self.user_tree.insert("", tk.END, values=(user.get("username", "N/A"),))

    def add_user_dialog(self):
        dialog = AddUserDialog(self.master)
        # Wait for the dialog to close. The dialog sets self.result before destroying itself.
        self.master.wait_window(dialog) 
        
        if dialog.result: # Now dialog.result will have the value set by the dialog
            username, password = dialog.result
            # This is where PasswordConfig.add_user is called
            success, message = add_user(username, password) 
            if success:
                messagebox.showinfo("Success", message)
                self.load_users_to_tree()
            else:
                messagebox.showerror("Error", message)

    def change_password_dialog(self):
        selected_item = self.user_tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Required", "Please select a user from the table.")
            return
        
        username = self.user_tree.item(selected_item)['values'][0]
        dialog = ChangePasswordDialog(self.master, username)
        if dialog.result:
            old_password, new_password = dialog.result
            success, message = self._handle_password_change(username, old_password, new_password)
            if success:
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)
    
    def _handle_password_change(self, username, old_password, new_password):
        # This function calls the existing change_password from PasswordConfig
        # It might need adjustment if admin privileges are introduced later
        # For now, it assumes the user whose password is being changed provides their old password
        return change_password(username, old_password, new_password)


    def delete_user_dialog(self):
        selected_item = self.user_tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Required", "Please select a user from the table.")
            return
        
        username = self.user_tree.item(selected_item)['values'][0]
        
        if len(self.config.get("users", [])) <= 1:
            messagebox.showerror("Error", "Cannot delete the last user.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{username}'?"):
            success, message = delete_user(username)
            if success:
                messagebox.showinfo("Success", message)
                self.load_users_to_tree() # Refresh user list
            else:
                messagebox.showerror("Error", message)

    def setup_styles(self):
        self.style = ttk.Style()
        # Light Theme (default ttk is usually light)
        self.style.theme_use('clam') # or 'default', 'alt', 'vista', 'xpnative'

        # Dark Theme
        self.style.configure("Dark.TFrame", background="#333333")
        self.style.configure("Dark.TLabel", background="#333333", foreground="#FFFFFF")
        self.style.configure("Dark.TButton", background="#555555", foreground="#FFFFFF")
        self.style.map("Dark.TButton", background=[('active', '#666666')])
        self.style.configure("Dark.TEntry", fieldbackground="#555555", foreground="#FFFFFF", insertcolor="#FFFFFF")
        self.style.configure("Dark.TLabelFrame", background="#333333", bordercolor="#666666")
        self.style.configure("Dark.TLabelFrame.Label", background="#333333", foreground="#FFFFFF")
        self.style.configure("Dark.TCheckbutton", background="#333333", foreground="#FFFFFF", indicatorcolor="#555555")
        self.style.map("Dark.TCheckbutton",
                       indicatorcolor=[('selected', '#007AFF'), ('!selected', '#555555')],
                       background=[('active', '#444444')])  

    def apply_theme(self):
        theme = self.current_theme.get()
        if theme == "dark":
            self.master.configure(bg="#333333")
            self.style.configure(".", background="#333333", foreground="#FFFFFF") # Global
            for widget_class in ["TFrame", "TLabel", "TButton", "TLabelFrame", "TCheckbutton", "Treeview"]: # Added Treeview
                self.style.configure(f"Dark.{widget_class}", background="#333333", foreground="#FFFFFF")
            
            # Configure ttk widget styles for dark mode
            self.style.configure("TEntry", fieldbackground="#222222", foreground="#FFFFFF", insertbackground="#FFFFFF")
            self.style.configure("TCombobox", 
                                 fieldbackground="#222222", 
                                 foreground="#FFFFFF", 
                                 selectbackground="#222222",
                                 selectforeground="#FFFFFF",
                                 background="#222222")
            self.style.configure("TSpinbox", 
                                 fieldbackground="#222222", 
                                 foreground="#FFFFFF", 
                                 insertbackground="#FFFFFF",
                                 background="#222222",
                                 arrowcolor="#FFFFFF")

            self.style.configure('TLabelframe.Label', background='#333333', foreground='#FFFFFF')
            
            # Explicitly define and apply dark style for both comboboxes
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox', 'StockMarketCombo.TCombobox']: # Added StockMarketCombo
                self.style.configure(style_name, 
                                    fieldbackground="#222222", # This matches TSpinbox fieldbackground
                                    background="#222222", 
                                    foreground="#FFFFFF", 
                                    arrowcolor="#FFFFFF",
                                    selectbackground="#333333", 
                                    selectforeground="#FFFFFF")
                self.style.map(style_name,
                               fieldbackground=[('readonly', '#222222')],
                               selectbackground=[('readonly', '#333333')],
                               background=[('readonly', '#222222')])
            try:
                self.font_combo.configure(style='FontCombo.TCombobox')
                self.ui_font_combo.configure(style='UIFontCombo.TCombobox')
                self.stock_market_combo.configure(style='StockMarketCombo.TCombobox') # Apply the style
            except Exception:
                pass

            # Treeview specific styles
            self.style.configure("Treeview.Heading", background="#444444", foreground="#FFFFFF", relief="flat")
            self.style.map("Treeview.Heading", background=[('active', '#555555')])
            self.style.configure("Treeview", 
                                 background="#2C2C2C", 
                                 fieldbackground="#2C2C2C", 
                                 foreground="#FFFFFF")
            self.style.map('Treeview',
                           background=[('selected', '#0078D7')], 
                           foreground=[('selected', '#FFFFFF')])


            self._set_entry_dark(self.master)
            self._set_combobox_dark(self.master)
            self._set_spinbox_dark(self.master)
            try:
                self.font_combo.configure(background="#222222", foreground="#FFFFFF", fieldbackground="#222222")
            except Exception:
                pass
            try:
                self.font_size_spinbox.configure(fieldbackground="#222222", foreground="#FFFFFF", background="#222222", insertbackground="#FFFFFF")
            except Exception:
                pass
            try:
                self.ui_font_combo.configure(background="#222222", foreground="#FFFFFF", fieldbackground="#222222")
                self.ui_font_preview_label.configure(background="#333333", foreground="#FFFFFF")
            except Exception:
                pass
        else: # Light theme
            self.master.configure(bg=self.style.lookup('TFrame', 'background')) 
            self.style.configure(".", background=self.style.lookup('TFrame', 'background'), 
                                      foreground=self.style.lookup('TLabel', 'foreground')) 
            for widget_class in ["TFrame", "TLabel", "TButton", "TEntry", "TLabelFrame", "TCheckbutton", "TCombobox", "TSpinbox", "Treeview"]: # Added Treeview
                self.style.configure(f"{widget_class}")
            
            # Reset the custom style in light mode for both comboboxes
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox', 'StockMarketCombo.TCombobox']: # Added StockMarketCombo
                self.style.configure(style_name, 
                                    fieldbackground="#FFFFFF", # This matches TSpinbox fieldbackground
                                    background="#FFFFFF", 
                                    foreground="#000000",
                                    arrowcolor="#000000",
                                    selectbackground="#CCCCCC", 
                                    selectforeground="#000000")
                self.style.map(style_name,
                               fieldbackground=[('readonly', '#FFFFFF')],
                               selectbackground=[('readonly', '#CCCCCC')],
                               background=[('readonly', '#FFFFFF')])
            try:
                self.font_combo.configure(style='FontCombo.TCombobox')
                self.ui_font_combo.configure(style='UIFontCombo.TCombobox')
                self.stock_market_combo.configure(style='StockMarketCombo.TCombobox') # Apply the style
            except Exception:
                pass

            self.style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#000000", insertbackground="#000000")
            self.style.configure("TCombobox", 
                                 fieldbackground="#FFFFFF", 
                                 foreground="#000000", 
                                 selectbackground=self.style.lookup('TCombobox', 'selectbackground'),
                                 selectforeground=self.style.lookup('TCombobox', 'selectforeground'),
                                 background=self.style.lookup('TCombobox', 'background'))
            self.style.configure("TSpinbox", 
                                 fieldbackground="#FFFFFF", 
                                 foreground="#000000", 
                                 insertbackground="#000000",
                                 background=self.style.lookup('TSpinbox', 'background'),
                                 arrowcolor=self.style.lookup('TSpinbox', 'arrowcolor'))

            self.style.configure('TLabelframe.Label', 
                                 background=self.style.lookup('TLabelFrame', 'background'), 
                                 foreground=self.style.lookup('TLabelFrame', 'foreground'))
            
            self.style.configure("Treeview.Heading", 
                                 background=self.style.lookup('TButton', 'background'), 
                                 foreground=self.style.lookup('TButton', 'foreground'), 
                                 relief="flat") # Or system default
            self.style.map("Treeview.Heading", background=[('active', self.style.lookup('TButton', 'activebackground'))])
            self.style.configure("Treeview", 
                                 background=self.style.lookup('TEntry', 'fieldbackground'), 
                                 fieldbackground=self.style.lookup('TEntry', 'fieldbackground'), 
                                 foreground=self.style.lookup('TEntry', 'foreground'))
            self.style.map('Treeview',
                           background=[('selected', self.style.lookup('Listbox', 'selectbackground'))],
                           foreground=[('selected', self.style.lookup('Listbox', 'selectforeground'))])

            self._set_entry_light(self.master)
            self._set_combobox_light(self.master)
            self._set_spinbox_light(self.master)
            try:
                self.font_combo.configure(background="#FFFFFF", foreground="#000000", fieldbackground="#FFFFFF")
            except Exception:
                pass
            try:
                self.font_size_spinbox.configure(fieldbackground="#FFFFFF", foreground="#000000", background="#FFFFFF", insertbackground="#000000")
            except Exception:
                pass
            try:
                self.ui_font_combo.configure(background="#FFFFFF", foreground="#000000", fieldbackground="#FFFFFF")
                self.ui_font_preview_label.configure(background=self.style.lookup('TFrame', 'background'), foreground="#000000")
            except Exception:
                pass
        self.update_font_preview()
        self.update_ui_font_preview()

    def _set_entry_dark(self, widget):
        # Recursively set all Entry widgets to dark mode
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            try:
                widget.configure(background="#222222", foreground="#FFFFFF", insertbackground="#FFFFFF")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_entry_dark(child)

    def _set_entry_light(self, widget):
        # Recursively set all Entry widgets to light mode (system default)
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            try:
                widget.configure(background="#FFFFFF", foreground="#000000", insertbackground="#000000")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_entry_light(child)

    def _set_combobox_dark(self, widget):
        # Recursively set all Combobox widgets to dark mode
        if isinstance(widget, ttk.Combobox):
            try:
                # fieldbackground for the entry part, background for the widget frame
                widget.configure(fieldbackground="#222222", foreground="#FFFFFF", background="#222222")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_combobox_dark(child)

    def _set_combobox_light(self, widget):
        # Recursively set all Combobox widgets to light mode
        if isinstance(widget, ttk.Combobox):
            try:
                widget.configure(fieldbackground="#FFFFFF", foreground="#000000", background="#FFFFFF")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_combobox_light(child)

    def _set_spinbox_dark(self, widget):
        # Recursively set all Spinbox widgets to dark mode
        if isinstance(widget, ttk.Spinbox):
            try:
                # For ttk.Spinbox, fieldbackground is key for the entry part
                widget.configure(fieldbackground="#222222", foreground="#FFFFFF", background="#222222", insertbackground="#FFFFFF")
            except Exception:
                pass
        elif isinstance(widget, tk.Spinbox): # Standard tk.Spinbox
            try:
                widget.configure(background="#222222", foreground="#FFFFFF", insertbackground="#FFFFFF")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_spinbox_dark(child)

    def _set_spinbox_light(self, widget):
        # Recursively set all Spinbox widgets to light mode
        if isinstance(widget, ttk.Spinbox):
            try:
                widget.configure(fieldbackground="#FFFFFF", foreground="#000000", background="#FFFFFF", insertbackground="#000000")
            except Exception:
                pass
        elif isinstance(widget, tk.Spinbox): # Standard tk.Spinbox
            try:
                widget.configure(background="#FFFFFF", foreground="#000000", insertbackground="#000000")
            except Exception:
                pass
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                self._set_spinbox_light(child)

    def toggle_theme(self):
        self.config["theme"] = self.current_theme.get()
        save_config(self.config)
        # Restart the application to fully apply theme changes
        self.master.destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def browse_profile_pic(self):
        filepath = filedialog.askopenfilename(
            title="Select Profile Picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        if filepath:
            # Always store the absolute path
            self.profile_pic_path_var.set(os.path.abspath(filepath))


    def crop_profile_pic(self):
        current_path = self.profile_pic_path_var.get()
        if not current_path:
            messagebox.showwarning("No Image", "Please select a profile picture first.")
            return
        
        abs_path = current_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(PROJECT_ROOT, abs_path)

        if not os.path.exists(abs_path):
            messagebox.showerror("Error", f"Image not found: {abs_path}")
            return
        
        # Create a cropped filename by adding _crop before the extension
        filename, ext = os.path.splitext(abs_path)
        crop_filename = f"{filename}_crop{ext}"
        
        # Create a temporary cropper window that will let the user crop the image
        cropper = CroppingWindow(self.master, abs_path, crop_filename)
        
        # Only process if the crop was actually saved (not cancelled)
        if hasattr(cropper, 'crop_saved') and cropper.crop_saved and hasattr(cropper, 'image_path') and os.path.exists(cropper.image_path):
            try:
                rel_path = os.path.relpath(cropper.image_path, PROJECT_ROOT)
                if ".." not in rel_path:
                    self.profile_pic_path_crop_var.set(rel_path)
                else:
                    self.profile_pic_path_crop_var.set(cropper.image_path)
                    
                # Update config immediately so the cropped image is used
                self.config["profile_pic_path_crop"] = self.profile_pic_path_crop_var.get()
                save_config(self.config)
                messagebox.showinfo("Success", "Cropped image saved and will be used for the screensaver.")
                
            except ValueError:
                self.profile_pic_path_crop_var.set(cropper.image_path)
                self.config["profile_pic_path_crop"] = self.profile_pic_path_crop_var.get()
                save_config(self.config)
                messagebox.showinfo("Success", "Cropped image saved and will be used for the screensaver.")

    def browse_video(self):
        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv"), ("All files", "*.*")]
        )
        if filepath:
            # Always store the absolute path
            self.video_path_var.set(os.path.abspath(filepath))

    def update_service_status(self):
        """Update service status display"""
        try:
            status = win32serviceutil.QueryServiceStatus("ScreenSaverService")[1]
            if status == win32service.SERVICE_RUNNING:
                self.service_status_label.config(text="Service Status: Running", foreground="green")
            elif status == win32service.SERVICE_STOPPED:
                self.service_status_label.config(text="Service Status: Stopped", foreground="red")
            else:
                self.service_status_label.config(text="Service Status: Unknown", foreground="orange")
        except:
            self.service_status_label.config(text="Service Status: Not Installed", foreground="gray")

    def install_service(self):
        """Install the Windows service"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "screensaver_service.py")
            subprocess.run([sys.executable, script_path, "install"], check=True)
            messagebox.showinfo("Success", "Service installed successfully!")
            self.update_service_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to install service: {e}")

    def start_service(self):
        """Start the Windows service"""
        try:
            win32serviceutil.StartService("ScreenSaverService")
            messagebox.showinfo("Success", "Service started successfully!")
            self.update_service_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start service: {e}")

    def stop_service(self):
        """Stop the Windows service"""
        try:
            win32serviceutil.StopService("ScreenSaverService")
            messagebox.showinfo("Success", "Service stopped successfully!")
            self.update_service_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop service: {e}")

    def uninstall_service(self):
        """Uninstall the Windows service"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "screensaver_service.py")
            subprocess.run([sys.executable, script_path, "remove"], check=True)
            messagebox.showinfo("Success", "Service uninstalled successfully!")
            self.update_service_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to uninstall service: {e}")

    def save_settings(self):
        self.config["profile_pic_path"] = self.profile_pic_path_var.get()
        self.config["profile_pic_path_crop"] = self.profile_pic_path_crop_var.get()
        self.config["video_path"] = self.video_path_var.get()
        self.config["theme"] = self.current_theme.get()
        self.config["clock_font_family"] = self.selected_clock_font_family.get()
        self.config["clock_font_size"] = self.selected_clock_font_size.get()
        self.config["ui_font_family"] = self.selected_ui_font_family.get()
        self.config["ui_font_size"] = self.selected_ui_font_size.get()
        self.config["screensaver_timer_minutes"] = self.screensaver_timer.get()
        self.config["enable_stock_widget"] = self.enable_stock_widget.get()
        self.config["enable_media_widget"] = self.media_widget_var.get() # Use the correct var
        self.config["stock_market"] = self.stock_market.get()
        self.config["enable_weather_widget"] = self.weather_widget_var.get()
        self.config["weather_pincode"] = self.weather_pincode_var.get()
        self.config["weather_country"] = self.weather_country_var.get()
        self.config["run_as_admin"] = self.admin_mode_var.get()
        
        if save_config(self.config):
            messagebox.showinfo("Success", "Settings saved successfully.")
        else:
            messagebox.showerror("Error", "Failed to save settings.")

    def update_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_clock_font_family.get()
        try:        self.font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            logger.error(f"Error updating font preview: {e}")
            self.font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback    def update_ui_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_ui_font_family.get()
        try:
            self.ui_font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            logger.error(f"Error updating font preview: {e}")
            self.ui_font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback

    def _combo_nav(self, combo, direction):
        """Navigate combobox values with up/down arrow keys."""
        values = combo['values']
        if not values:
            return "break" # No values to navigate
        try:
            idx = values.index(combo.get())
        except ValueError:
            # If current value not in list, or list is empty, decide a starting point
            idx = 0 if direction == 1 else len(values) -1 
        new_idx = (idx + direction) % len(values)
        combo.current(new_idx) # Use current() to set by index
        combo.event_generate("<<ComboboxSelected>>")
        return "break" # Prevent default behavior

    def _combo_typeahead(self, combo, event):
        """Jump to value in combobox starting with typed character(s), with cycling."""
        
        if event.keysym in ('Tab', 'Return', 'Escape', 'BackSpace', 'Up', 'Down', 'Left', 'Right'):
            if combo in self.combo_typeahead_state:
                self.combo_typeahead_state[combo] = {'buffer': '', 'last_time': 0, 'last_selected_idx_for_buffer': -1}
            return 

        if not event.char or not event.char.isprintable():
            if combo in self.combo_typeahead_state: # Reset buffer on other non-printable
                self.combo_typeahead_state[combo]['buffer'] = ""
                self.combo_typeahead_state[combo]['last_selected_idx_for_buffer'] = -1
            return "break"

        if combo not in self.combo_typeahead_state:
            self.combo_typeahead_state[combo] = {'buffer': '', 'last_time': 0, 'last_selected_idx_for_buffer': -1}
        
        state = self.combo_typeahead_state[combo]
        current_time = time.time()
        typed_char = event.char.lower()

        previous_buffer = state['buffer']
        
        if current_time - state['last_time'] > 1.2: # Timeout
            state['buffer'] = typed_char
            state['last_selected_idx_for_buffer'] = -1
        else: # Within timeout
            if len(typed_char) == 1 and state['buffer'] == typed_char:
                # Same single character pressed again - buffer remains, for cycling.
                # last_selected_idx_for_buffer is preserved to find the next item.
                pass
            elif len(typed_char) == 1 and len(state['buffer']) == 1 and state['buffer'] != typed_char:
                # Different single character typed (e.g., was 'a', now 'b')
                state['buffer'] = typed_char
                state['last_selected_idx_for_buffer'] = -1
            else:
                # Appending to buffer or starting a new multi-char sequence
                state['buffer'] += typed_char
                # If buffer fundamentally changed (not just a cycle attempt on single char)
                # reset last_selected_idx so search for new buffer starts from beginning of matches.
                if not previous_buffer or not state['buffer'].startswith(previous_buffer) or len(previous_buffer) != len(state['buffer']) -1 :
                     state['last_selected_idx_for_buffer'] = -1


        state['last_time'] = current_time
        target_buffer = state['buffer']
        values = combo['values']
        
        possible_matches_indices = [idx for idx, val in enumerate(values) if val.lower().startswith(target_buffer)]

        if not possible_matches_indices:
            # No match for the current buffer.
            # Optionally, revert buffer or clear selection. For now, do nothing to selection.
            # Reset last_selected_idx if current buffer is new and failed.
            if target_buffer != previous_buffer : # if buffer changed and failed
                 state['last_selected_idx_for_buffer'] = -1
            # state['buffer'] = "" # Or revert to previous_buffer if desired
            return "break"

        new_selection_idx = -1

        if state['last_selected_idx_for_buffer'] != -1 and \
           state['last_selected_idx_for_buffer'] in possible_matches_indices:
            # Current buffer still matches the prefix of the last selected item,
            # or the buffer is a single char and we are cycling.
            try:
                current_match_list_idx = possible_matches_indices.index(state['last_selected_idx_for_buffer'])
                next_match_list_idx = (current_match_list_idx + 1) % len(possible_matches_indices)
                new_selection_idx = possible_matches_indices[next_match_list_idx]
            except ValueError: # Should not happen if last_selected_idx_for_buffer is in possible_matches_indices
                new_selection_idx = possible_matches_indices[0]
        else:
            # First match for this buffer, or previous selection no longer relevant.
            new_selection_idx = possible_matches_indices[0]

        if new_selection_idx != -1:
            if combo.current() != new_selection_idx: # Avoid redundant updates if already selected
                 combo.current(new_selection_idx)
                 combo.event_generate("<<ComboboxSelected>>")
            state['last_selected_idx_for_buffer'] = new_selection_idx
        
        return "break"

class AddUserDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add New User")
        self.parent = parent
        self.result = None

        self.geometry("300x120") # Adjusted size
        self.resizable(False, False)
        self.transient(parent) # Keep on top of parent
        self.grab_set() # Modal

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.username_entry = ttk.Entry(main_frame, width=30)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(main_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.password_entry = ttk.Entry(main_frame, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # Removed Confirm Password field
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10) # Adjusted row
        
        ttk.Button(button_frame, text="Add User", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
        self.username_entry.focus_set()
        self.bind("<Return>", lambda e: self.on_add())
        self.bind("<Escape>", lambda e: self.on_cancel())

    def on_add(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        # Removed confirm_password

        if not username or not password:
            messagebox.showerror("Input Error", "Username and password cannot be empty.", parent=self)
            return
        # Removed password match check
        
        self.result = (username, password)
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, username):
        super().__init__(parent)
        self.title(f"Change Password for {username}")
        self.parent = parent
        self.username = username
        self.result = None

        self.geometry("350x150") # Adjusted size
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Changing password for: {username}").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(main_frame, text="Old Password:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.old_password_entry = ttk.Entry(main_frame, show="*", width=30)
        self.old_password_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(main_frame, text="New Password:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.new_password_entry = ttk.Entry(main_frame, show="*", width=30)
        self.new_password_entry.grid(row=2, column=1, padx=5, pady=5)

        # Removed Confirm New Password field
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10) # Adjusted row
        
        ttk.Button(button_frame, text="Change Password", command=self.on_change).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        self.old_password_entry.focus_set()
        self.bind("<Return>", lambda e: self.on_change())
        self.bind("<Escape>", lambda e: self.on_cancel())

    def on_change(self):
        old_password = self.old_password_entry.get()
        new_password = self.new_password_entry.get()
        # Removed confirm_new_password

        if not old_password or not new_password: # Old password is required by current change_password logic
            messagebox.showerror("Input Error", "All password fields are required.", parent=self)
            return
        # Removed new password match check
        
        self.result = (old_password, new_password)
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

def main():
    # When running the script directly, adjust sys.path to find the package
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the script's directory to sys.path so relative imports work
    # This might not be strictly necessary if PasswordConfig is correctly found via PYTHONPATH or package structure
    # but good for robustness if gui.py is sometimes run directly.
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
  
    root = tk.Tk()
    app = ScreenSaverApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
