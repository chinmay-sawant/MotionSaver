import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
from PIL import Image, ImageTk, ImageDraw 
import os
import json
import sys # Import sys

# Assuming PasswordConfig.py is in the same directory (package)
# This will work when gui.py is imported as part of the package
# For direct execution, sys.path needs adjustment (see if __name__ == '__main__')
try:
    from screensaver_app.PasswordConfig import load_config, save_config, change_password
except ImportError:
    # Fallback for direct script execution (no parent package)
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'screensaver_app')))
    from screensaver_app.PasswordConfig import load_config, save_config, change_password

# Define paths relative to this file's location if needed, or use absolute paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
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
        
        self.config = load_config()
        self.current_theme = tk.StringVar(value=self.config.get("theme", "light"))
        self.selected_clock_font_family = tk.StringVar(value=self.config.get("clock_font_family", "Segoe UI Emoji"))
        self.selected_clock_font_size = tk.IntVar(value=self.config.get("clock_font_size", 64))
        self.selected_ui_font_family = tk.StringVar(value=self.config.get("ui_font_family", "Arial"))
        self.selected_ui_font_size = tk.IntVar(value=self.config.get("ui_font_size", 18))

        self.setup_styles()
       

        # --- Main Frame ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Profile Picture ---
        pic_frame = ttk.LabelFrame(main_frame, text="Profile Picture", padding="10")
        pic_frame.pack(fill=tk.X, pady=5)

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
        
        # --- Video Path ---
        video_frame = ttk.LabelFrame(main_frame, text="Screen Saver Video", padding="10")
        video_frame.pack(fill=tk.X, pady=5)

        self.video_path_var = tk.StringVar(value=self.config.get("video_path", "video.mp4"))
        ttk.Label(video_frame, text="Path:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.video_path_entry = ttk.Entry(video_frame, textvariable=self.video_path_var, width=40)
        self.video_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(video_frame, text="Browse...", command=self.browse_video).grid(row=0, column=2, padx=5, pady=5)

        # --- Clock Font Settings ---
        font_frame = ttk.LabelFrame(main_frame, text="Clock Appearance", padding="10")
        font_frame.pack(fill=tk.X, pady=5)

        ttk.Label(font_frame, text="Font Family:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_families = sorted(list(tkfont.families(root=self.master))) # Pass root to families()
        self.font_combo = ttk.Combobox(font_frame, textvariable=self.selected_clock_font_family, values=self.font_families, width=37, state="readonly")
        self.font_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # Create a custom style just for this combobox to ensure dark mode works
        self.style.configure('FontCombo.TCombobox', background="#222222", foreground="#FFFFFF", fieldbackground="#222222", selectbackground="#222222")
        self.font_combo.configure(style='FontCombo.TCombobox')
        
        current_font_in_list = self.selected_clock_font_family.get()
        if current_font_in_list in self.font_families:
            self.font_combo.set(current_font_in_list)
        elif self.font_families: 
            self.font_combo.current(0) 
            self.selected_clock_font_family.set(self.font_combo.get())
        else: # No fonts found
            self.selected_clock_font_family.set("Default") # Placeholder if no fonts
        
        # Add font preview label
        self.font_preview_label = ttk.Label(font_frame, text="Preview Text", font=(self.selected_clock_font_family.get(), 12))
        self.font_preview_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        
        # Bind combobox selection to update preview
        self.font_combo.bind("<<ComboboxSelected>>", self.update_font_preview)

        ttk.Label(font_frame, text="Font Size:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.font_size_spinbox = ttk.Spinbox(font_frame, from_=10, to=200, increment=2, textvariable=self.selected_clock_font_size, width=5)
        self.font_size_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        font_frame.columnconfigure(1, weight=1)
        
        # --- UI Font Settings ---
        ui_font_frame = ttk.LabelFrame(main_frame, text="UI Appearance", padding="10")
        ui_font_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ui_font_frame, text="Font Family:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ui_font_families = sorted(list(tkfont.families(root=self.master))) # Pass root to families()
        self.ui_font_combo = ttk.Combobox(ui_font_frame, textvariable=self.selected_ui_font_family, values=self.ui_font_families, width=37, state="readonly")
        self.ui_font_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # Create a custom style just for this combobox to ensure dark mode works
        self.style.configure('UIFontCombo.TCombobox', background="#222222", foreground="#FFFFFF", fieldbackground="#222222", selectbackground="#222222")
        self.ui_font_combo.configure(style='UIFontCombo.TCombobox')
        
        current_ui_font_in_list = self.selected_ui_font_family.get()
        if current_ui_font_in_list in self.ui_font_families:
            self.ui_font_combo.set(current_ui_font_in_list)
        elif self.ui_font_families: 
            self.ui_font_combo.current(0) 
            self.selected_ui_font_family.set(self.ui_font_combo.get())
        else: # No fonts found
            self.selected_ui_font_family.set("Default") # Placeholder if no fonts
        
        # Add font preview label
        self.ui_font_preview_label = ttk.Label(ui_font_frame, text="Preview Text", font=(self.selected_ui_font_family.get(), 12))
        self.ui_font_preview_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        
        # Bind combobox selection to update preview
        self.ui_font_combo.bind("<<ComboboxSelected>>", self.update_ui_font_preview)

        ttk.Label(ui_font_frame, text="Font Size:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.ui_font_size_spinbox = ttk.Spinbox(ui_font_frame, from_=10, to=200, increment=2, textvariable=self.selected_ui_font_size, width=5)
        self.ui_font_size_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        ui_font_frame.columnconfigure(1, weight=1)
        
        # --- Theme Toggle ---
        theme_frame = ttk.LabelFrame(main_frame, text="Appearance", padding="10")
        theme_frame.pack(fill=tk.X, pady=5)
        self.theme_toggle_button = ttk.Checkbutton(
            theme_frame, text="Dark Mode", variable=self.current_theme,
            onvalue="dark", offvalue="light", command=self.toggle_theme
        )
        self.theme_toggle_button.pack(anchor=tk.W, padx=5, pady=5)
        
        # --- Save Button ---
        save_button = ttk.Button(main_frame, text="Save Settings", command=self.save_settings)
        save_button.pack(pady=20)

        # Configure grid column weights for resizing
        pic_frame.columnconfigure(1, weight=1)
        video_frame.columnconfigure(1, weight=1)
        
        master.minsize(450, 400)
        self.apply_theme()

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
            for widget_class in ["TFrame", "TLabel", "TButton", "TLabelFrame", "TCheckbutton"]:
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
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox']:
                self.style.configure(style_name, 
                                    fieldbackground="#222222",
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
            except Exception:
                pass

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
            for widget_class in ["TFrame", "TLabel", "TButton", "TEntry", "TLabelFrame", "TCheckbutton", "TCombobox", "TSpinbox"]:
                self.style.configure(f"{widget_class}")
            
            # Reset the custom style in light mode for both comboboxes
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox']:
                self.style.configure(style_name, 
                                    fieldbackground="#FFFFFF",
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
                                 foreground=self.style.lookup('TLabelFrame.Label', 'foreground'))
            
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
            # Store relative path if possible, or absolute if on different drive
            try:
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                if ".." not in rel_path: # Check if it's within project or its subdirs
                    self.profile_pic_path_var.set(rel_path)
                else: # Different drive or far outside project
                    self.profile_pic_path_var.set(filepath)
            except ValueError: # Paths are on different drives (Windows)
                 self.profile_pic_path_var.set(filepath)


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
            try:
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                if ".." not in rel_path:
                    self.video_path_var.set(rel_path)
                else:
                    self.video_path_var.set(filepath)
            except ValueError:
                 self.video_path_var.set(filepath)

    def save_settings(self):
        self.config["profile_pic_path"] = self.profile_pic_path_var.get()
        self.config["profile_pic_path_crop"] = self.profile_pic_path_crop_var.get()
        self.config["video_path"] = self.video_path_var.get()
        self.config["theme"] = self.current_theme.get()
        self.config["clock_font_family"] = self.selected_clock_font_family.get()
        self.config["clock_font_size"] = self.selected_clock_font_size.get()
        self.config["ui_font_family"] = self.selected_ui_font_family.get()
        self.config["ui_font_size"] = self.selected_ui_font_size.get()
        
        if save_config(self.config):
            messagebox.showinfo("Success", "Settings saved successfully.")
        else:
            messagebox.showerror("Error", "Failed to save settings.")

    def update_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_clock_font_family.get()
        try:
            self.font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            print(f"Error updating font preview: {e}")
            self.font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback

    def update_ui_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_ui_font_family.get()
        try:
            self.ui_font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            print(f"Error updating font preview: {e}")
            self.ui_font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback

    def apply_theme(self):
        theme = self.current_theme.get()
        if theme == "dark":
            self.master.configure(bg="#333333")
            self.style.configure(".", background="#333333", foreground="#FFFFFF") # Global
            for widget_class in ["TFrame", "TLabel", "TButton", "TLabelFrame", "TCheckbutton"]:
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
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox']:
                self.style.configure(style_name, 
                                    fieldbackground="#222222",
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
            except Exception:
                pass

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
            for widget_class in ["TFrame", "TLabel", "TButton", "TEntry", "TLabelFrame", "TCheckbutton", "TCombobox", "TSpinbox"]:
                self.style.configure(f"{widget_class}")
            
            # Reset the custom style in light mode for both comboboxes
            for style_name in ['FontCombo.TCombobox', 'UIFontCombo.TCombobox']:
                self.style.configure(style_name, 
                                    fieldbackground="#FFFFFF",
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
                                 foreground=self.style.lookup('TLabelFrame.Label', 'foreground'))
            
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
            # Store relative path if possible, or absolute if on different drive
            try:
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                if ".." not in rel_path: # Check if it's within project or its subdirs
                    self.profile_pic_path_var.set(rel_path)
                else: # Different drive or far outside project
                    self.profile_pic_path_var.set(filepath)
            except ValueError: # Paths are on different drives (Windows)
                 self.profile_pic_path_var.set(filepath)


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
            try:
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                if ".." not in rel_path:
                    self.video_path_var.set(rel_path)
                else:
                    self.video_path_var.set(filepath)
            except ValueError:
                 self.video_path_var.set(filepath)

    def save_settings(self):
        self.config["profile_pic_path"] = self.profile_pic_path_var.get()
        self.config["profile_pic_path_crop"] = self.profile_pic_path_crop_var.get()
        self.config["video_path"] = self.video_path_var.get()
        self.config["theme"] = self.current_theme.get()
        self.config["clock_font_family"] = self.selected_clock_font_family.get()
        self.config["clock_font_size"] = self.selected_clock_font_size.get()
        self.config["ui_font_family"] = self.selected_ui_font_family.get()
        self.config["ui_font_size"] = self.selected_ui_font_size.get()
        
        if save_config(self.config):
            messagebox.showinfo("Success", "Settings saved successfully.")
        else:
            messagebox.showerror("Error", "Failed to save settings.")

    def update_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_clock_font_family.get()
        try:
            self.font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            print(f"Error updating font preview: {e}")
            self.font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback

    def update_ui_font_preview(self, event=None):
        """Updates the font preview label with the selected font."""
        selected_font = self.selected_ui_font_family.get()
        try:
            self.ui_font_preview_label.configure(font=(selected_font, 12))
        except Exception as e:
            print(f"Error updating font preview: {e}")
            self.ui_font_preview_label.configure(font=("TkDefaultFont", 12)) # Fallback

if __name__ == '__main__':
    # When running the script directly, adjust sys.path to find the package
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the script's directory to sys.path so relative imports work
    sys.path.insert(0, script_dir)
  
    root = tk.Tk()
    app = ScreenSaverApp(root)
    root.mainloop()
