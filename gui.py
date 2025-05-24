import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import cv2
from PIL import Image, ImageTk
from video_player import VideoClockScreenSaver
from themes import light_theme, dark_theme

class ScreenSaverApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Video Screen Saver")
        self.master.geometry("900x600")
        self.master.minsize(800, 500)
        
        # Initialize theme
        self.current_theme = "dark"
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.videos_dir = os.path.join(os.path.dirname(__file__), "videos")
        
        # Create videos directory if it doesn't exist
        if not os.path.exists(self.videos_dir):
            os.makedirs(self.videos_dir)
        
        # Load configuration
        self.config = self.load_config()
        
        # Apply theme
        self.apply_theme()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create top panel with title and theme toggle
        self.top_panel = ttk.Frame(self.main_frame)
        self.top_panel.pack(fill=tk.X, pady=10)
        
        ttk.Label(self.top_panel, text="Video Screen Saver", font=("Arial", 16, "bold")).pack(side=tk.LEFT, padx=10)
        
        # Theme toggle button
        self.theme_icon = "☀️" if self.current_theme == "dark" else "🌙"
        self.theme_btn = ttk.Button(self.top_panel, text=f"{self.theme_icon} Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT, padx=10)
        
        # Create left panel for video list
        self.left_panel = ttk.LabelFrame(self.main_frame, text="Available Videos")
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create video list with scrollbar
        self.video_list_frame = ttk.Frame(self.left_panel)
        self.video_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.video_scrollbar = ttk.Scrollbar(self.video_list_frame)
        self.video_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_list = tk.Listbox(self.video_list_frame, 
                                     yscrollcommand=self.video_scrollbar.set,
                                     selectmode=tk.SINGLE,
                                     bg=self.theme["listbox_bg"],
                                     fg=self.theme["listbox_fg"])
        self.video_list.pack(fill=tk.BOTH, expand=True)
        self.video_scrollbar.config(command=self.video_list.yview)
        
        # Bind list selection event
        self.video_list.bind("<<ListboxSelect>>", self.on_video_select)
        
        # Button panel under the list
        self.list_buttons = ttk.Frame(self.left_panel)
        self.list_buttons.pack(fill=tk.X, pady=5)
        
        ttk.Button(self.list_buttons, text="Add Video", command=self.add_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.list_buttons, text="Remove", command=self.remove_video).pack(side=tk.LEFT, padx=5)
        
        # Create right panel for preview and settings
        self.right_panel = ttk.Frame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Preview panel
        self.preview_panel = ttk.LabelFrame(self.right_panel, text="Preview")
        self.preview_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.preview_label = ttk.Label(self.preview_panel, background="black")
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Action buttons
        self.action_panel = ttk.Frame(self.right_panel)
        self.action_panel.pack(fill=tk.X, pady=10)
        
        ttk.Button(self.action_panel, text="Start Screen Saver", command=self.start_screensaver).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.action_panel, text="Apply Settings", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        
        # Load videos list
        self.refresh_video_list()
        
        # Current selected video
        self.selected_video = None
        if self.config.get("last_video"):
            if os.path.exists(self.config["last_video"]):
                self.selected_video = self.config["last_video"]
                # Select in the list
                for i, video in enumerate(self.get_available_videos()):
                    if video == os.path.basename(self.selected_video):
                        self.video_list.selection_set(i)
                        self.video_list.see(i)
                        break
                self.update_preview()

    def load_config(self):
        """Load configuration from file"""
        default_config = {
            "theme": "dark",
            "last_video": None
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Update theme from config
                    self.current_theme = config.get("theme", "dark")
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return default_config

    def save_config(self):
        """Save configuration to file"""
        self.config["theme"] = self.current_theme
        if self.selected_video:
            self.config["last_video"] = self.selected_video
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def apply_theme(self):
        """Apply the current theme to the application"""
        self.theme = dark_theme if self.current_theme == "dark" else light_theme
        style = ttk.Style(self.master)
        
        # Configure ttk style with theme colors
        style.configure("TFrame", background=self.theme["bg"])
        style.configure("TLabel", background=self.theme["bg"], foreground=self.theme["fg"])
        style.configure("TButton", background=self.theme["button_bg"], foreground=self.theme["button_fg"])
        style.configure("TLabelframe", background=self.theme["bg"], foreground=self.theme["fg"])
        style.configure("TLabelframe.Label", background=self.theme["bg"], foreground=self.theme["fg"])
        
        # Update root window background
        self.master.configure(background=self.theme["bg"])
        
        if hasattr(self, 'video_list'):
            self.video_list.configure(bg=self.theme["listbox_bg"], fg=self.theme["listbox_fg"])

    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme()
        
        # Update theme button text
        self.theme_icon = "☀️" if self.current_theme == "dark" else "🌙"
        self.theme_btn.configure(text=f"{self.theme_icon} Toggle Theme")
        
        # Save the theme preference
        self.config["theme"] = self.current_theme

    def get_available_videos(self):
        """Get list of available video files"""
        video_files = []
        for file in os.listdir(self.videos_dir):
            if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv')):
                video_files.append(file)
        return video_files

    def refresh_video_list(self):
        """Refresh the video list display"""
        self.video_list.delete(0, tk.END)
        for video in self.get_available_videos():
            self.video_list.insert(tk.END, video)

    def add_video(self):
        """Add a new video file"""
        filetypes = (
            ('Video files', '*.mp4 *.avi *.mkv *.mov *.wmv'),
            ('All files', '*.*')
        )
        
        video_path = filedialog.askopenfilename(
            title='Select a video file',
            filetypes=filetypes
        )
        
        if video_path:
            # Copy or link the file to videos directory
            filename = os.path.basename(video_path)
            destination = os.path.join(self.videos_dir, filename)
            
            try:
                # For simplicity, we'll just create a symbolic link
                if os.path.exists(destination):
                    if messagebox.askyesno("File exists", "File already exists. Replace it?"):
                        os.remove(destination)
                    else:
                        return
                
                # Copy the file to our videos directory
                import shutil
                shutil.copy2(video_path, destination)
                
                self.refresh_video_list()
                
                # Select the newly added video
                for i, video in enumerate(self.get_available_videos()):
                    if video == filename:
                        self.video_list.selection_set(i)
                        self.video_list.see(i)
                        self.selected_video = destination
                        self.update_preview()
                        break
                        
                messagebox.showinfo("Success", "Video added successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add video: {e}")

    def remove_video(self):
        """Remove the selected video file"""
        selected_indices = self.video_list.curselection()
        if not selected_indices:
            messagebox.showinfo("Info", "No video selected")
            return
            
        video_name = self.video_list.get(selected_indices[0])
        video_path = os.path.join(self.videos_dir, video_name)
        
        if messagebox.askyesno("Confirm", f"Remove video '{video_name}'?"):
            try:
                os.remove(video_path)
                self.refresh_video_list()
                self.selected_video = None
                self.update_preview()
                messagebox.showinfo("Success", "Video removed successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove video: {e}")

    def on_video_select(self, event):
        """Handle video selection from list"""
        selected_indices = self.video_list.curselection()
        if not selected_indices:
            return
            
        video_name = self.video_list.get(selected_indices[0])
        self.selected_video = os.path.join(self.videos_dir, video_name)
        self.update_preview()

    def update_preview(self):
        """Update the preview panel with the selected video"""
        if not self.selected_video or not os.path.exists(self.selected_video):
            # Clear preview
            self.preview_label.config(image='')
            return
            
        # Load first frame of the video for preview
        cap = cv2.VideoCapture(self.selected_video)
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Resize frame to fit preview panel
            max_width = 400
            max_height = 225  # 16:9 aspect ratio for 400px width
            
            h, w = frame.shape[:2]
            if w > max_width or h > max_height:
                scale = min(max_width / w, max_height / h)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            
            # Convert to PhotoImage for display
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img_tk = ImageTk.PhotoImage(img)
            
            self.preview_label.config(image=img_tk)
            self.preview_label.image = img_tk  # Keep a reference

    def start_screensaver(self):
        """Start the screen saver in fullscreen mode"""
        if not self.selected_video or not os.path.exists(self.selected_video):
            messagebox.showinfo("Info", "Please select a video first")
            return
            
        # Save current configuration
        self.save_config()
        
        # Create a new toplevel window for the screen saver
        top = tk.Toplevel(self.master)
        screensaver = VideoClockScreenSaver(top, self.selected_video)
        
        # Bind escape key to close
        top.bind("<Escape>", lambda e: (screensaver.close(), top.destroy()))
