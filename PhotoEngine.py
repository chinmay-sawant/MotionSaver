import tkinter as tk
import argparse
import os
from video_player import VideoClockScreenSaver # VideoClockScreenSaver now handles default profile
from gui import ScreenSaverApp
from PasswordConfig import verify_password_dialog_macos

def start_screensaver(video_path):
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

    app = VideoClockScreenSaver(root, video_path) # This will display video + default profile
    
    def on_escape(event):
        # verify_password_dialog_macos shows the password-only input Toplevel
        if verify_password_dialog_macos(root): # Pass root as parent for Toplevel
            app.close()
            root.destroy()
        else:
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
    parser.add_argument('--video', default="video.mp4", help='Path to video file')
    parser.add_argument('--gui', action='store_true', help='Launch GUI mode')
    args = parser.parse_args()
    
    if args.gui:
        # Start the GUI application
        root = tk.Tk()
        app = ScreenSaverApp(root)
        root.mainloop()
    else:
        # Start the screensaver directly
        start_screensaver(args.video)

if __name__ == "__main__":
    main()
