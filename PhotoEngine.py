import tkinter as tk
import argparse
import os
# Update imports to use the new package structure
from screensaver_app.video_player import VideoClockScreenSaver 
from screensaver_app.PasswordConfig import verify_password_dialog_macos

def start_screensaver(video_path_override=None): # Modified to accept an optional override
    """Launch the full-screen screen saver directly"""
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    
    # This transparent key is for the MacOSStyleLogin Toplevel
    TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL = '#123456' 
    # The root window itself doesn't strictly need to be transparent now,
    # as the video player draws directly on it.
    # However, the Toplevel for password input will use this.
    # For the Toplevel to be transparent against the OS, the root needs this.
    root.attributes('-transparentcolor', TRANSPARENT_KEY_FOR_LOGIN_TOPLEVEL)
    root.configure(bg='black') # Video player's background

    # Pass the override to VideoClockScreenSaver. If None, VideoClockScreenSaver will use config.
    app = VideoClockScreenSaver(root, video_path_override) 
    
    def on_escape(event):
        # verify_password_dialog_macos now returns True/False instead of a username
        success = verify_password_dialog_macos(root)
        if success: # If login successful
            app.close()
            root.destroy()
        else:
            # Check if root window still exists before trying to set focus
            if root.winfo_exists():
                root.focus_set() 
            print("Login cancelled or failed.")
    
    # Allow clicking on the main screensaver window (where profile is drawn)
    # to also trigger password. This requires VideoClockScreenSaver to handle clicks.
    # For now, only Escape triggers.
    root.bind("<Escape>", on_escape)
    # Example: if VideoClockScreenSaver's label could be clicked:
    # app.label.bind("<Button-1>", on_escape) # This would need careful implementation

    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='Video Clock Screen Saver')
    # The default for --video here is just for the help message and if used as an override.
    # If --video is not provided, VideoClockScreenSaver will use its internal logic (config or its own default).
    parser.add_argument('--video', default=None, help='Path to video file (overrides config)')
    args = parser.parse_args()
    
    start_screensaver(args.video)

if __name__ == "__main__":
    main()
