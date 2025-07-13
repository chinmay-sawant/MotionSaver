import sys
import os
import time
import threading
import cv2
import numpy as np

from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

import win32gui
import win32con

# --- Configuration and Path Setup ---

# Ensure the project root is in the path for custom module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# This import might fail if the structure is different.
# A fallback is provided for easy testing.
try:
    from screensaver_app.PasswordConfig import load_config, save_config
except ImportError:
    print("Warning: Could not import 'load_config' or 'save_config'. Using default settings.")
    def load_config():
        """Fallback function if the original config loader is not found."""
        return {'video_path': 'video.mp4'}

    def save_config(config):
        """Fallback function if the original config saver is not found."""
        print("Warning: Could not save config. This is a fallback.")

# --- Core Logic ---

class FrameReader(QObject):
    """
    Reads video frames in a thread, emits them, and handles saving/loading
    the video's timestamp to a config file.
    """
    frame_ready = pyqtSignal(object)
    SAVE_INTERVAL = 5  # Save timestamp every 5 seconds

    def __init__(self, video_path, fps, config):
        super().__init__()
        self.running = False
        self.video_path = video_path
        self.fps = fps
        self.config = config
        self.last_save_time = 0

    def start_reading(self):
        """Initializes the video capture, seeks to the last saved timestamp, and starts the thread."""
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Error: Could not open video file {self.video_path}")
            return

        # Load last timestamp from config and seek the video position
        start_timestamp_ms = self.config.get('last_video_timestamp', 0)
        if start_timestamp_ms > 0:
            print(f"Resuming video from {start_timestamp_ms / 1000:.2f} seconds.")
            self.cap.set(cv2.CAP_PROP_POS_MSEC, start_timestamp_ms)

        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop_reading(self):
        """Stops the reading loop and releases the video capture resources."""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        if hasattr(self, 'cap'):
            self.cap.release()
            print("Video capture released.")

    def _read_loop(self):
        """The main loop that reads frames and periodically saves the timestamp."""
        interval = 1.0 / self.fps
        while self.running:
            start_time = time.perf_counter()

            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            self.frame_ready.emit(frame)

            # Periodically save the current video timestamp
            current_time = time.time()
            if current_time - self.last_save_time > self.SAVE_INTERVAL:
                timestamp_ms = self.cap.get(cv2.CAP_PROP_POS_MSEC)
                self.config['last_video_timestamp'] = timestamp_ms
                save_config(self.config)
                self.last_save_time = current_time

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)


class WallpaperWindow(QWidget):
    """
    A QWidget that acts as a wallpaper for a single monitor. It uses Win32 API
    calls to parent itself to the desktop background, ensuring it stays behind icons.
    """
    def __init__(self, screen):
        super().__init__()
        self.screen_geometry = screen.geometry()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setGeometry(self.screen_geometry)
        self.label = QLabel(self)
        self.label.setGeometry(self.rect())
        self.label.setScaledContents(False) # Important: We do our own scaling.

    def showEvent(self, event):
        """Triggered when the window is shown. Used for Win32 parenting and positioning."""
        progman = win32gui.FindWindow("Progman", None)
        win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)

        workerw_hwnd = 0
        def enum_windows_callback(hwnd, lParam):
            nonlocal workerw_hwnd
            if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                workerw_hwnd = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
            return True
        win32gui.EnumWindows(enum_windows_callback, None)

        hwnd = self.winId().__int__()
        if workerw_hwnd:
            win32gui.SetParent(hwnd, workerw_hwnd)
        else:
            print("Warning: Could not find WorkerW. Attaching to Progman as a fallback.")
            win32gui.SetParent(hwnd, progman)

        geo = self.screen_geometry
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, geo.x(), geo.y(), geo.width(), geo.height(), win32con.SWP_NOACTIVATE)
        super().showEvent(event)

    def display_frame(self, frame):
        """
        Receives a raw frame and efficiently scales it to fill the monitor
        without distortion before displaying.
        """
        # --- CRITICAL FIX: Use the reliable screen geometry, not the widget's size ---
        # Using self.label.size() can be unreliable as it might not be fully
        # updated when the first frame arrives, causing a size mismatch.
        # self.screen_geometry is constant and always correct for this window.
        geo = self.screen_geometry
        target_w, target_h = geo.width(), geo.height()

        if target_w == 0 or target_h == 0: return

        frame_h, frame_w = frame.shape[:2]
        
        # Determine the scale factor required to fill the target, then crop.
        scale_h = target_h / frame_h
        scale_w = target_w / frame_w
        scale = max(scale_h, scale_w)

        # New dimensions after scaling
        new_w, new_h = int(frame_w * scale), int(frame_h * scale)
        
        # Resize using the calculated scale factor
        resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Calculate coordinates for a center crop
        crop_x = (new_w - target_w) // 2
        crop_y = (new_h - target_h) // 2
        
        # Perform the crop to get the final frame, perfectly sized for the monitor.
        final_frame = resized_frame[crop_y:crop_y + target_h, crop_x:crop_x + target_w]

        # Convert the pre-scaled frame to a QPixmap.
        rgb_frame = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Set the pixmap. No further scaling is needed by Qt.
        self.label.setPixmap(QPixmap.fromImage(qt_img))

    def resizeEvent(self, event):
        """Ensures the label resizes with the window."""
        self.label.setGeometry(self.rect())
        super().resizeEvent(event)


# --- Application Entry Point ---

if __name__ == "__main__":
    config = load_config()
    video_path = config.get('video_path', 'video.mp4')
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at '{video_path}'")
        sys.exit(1)

    app = QApplication(sys.argv)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Failed to open video file with OpenCV: '{video_path}'")
        sys.exit(1)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if not video_fps or video_fps < 1: video_fps = 30
    cap.release()

    screens = app.screens()
    if not screens:
        print("Error: No screens detected.")
        sys.exit(1)

    # Pass the config object to the FrameReader for timestamp handling
    frame_reader = FrameReader(video_path, video_fps, config)
    windows = []

    print(f"Detected {len(screens)} screen(s). Creating wallpaper windows...")
    for screen in screens:
        geo = screen.geometry()
        print(f"- Creating window for screen at: ({geo.x()}, {geo.y()}) with size {geo.width()}x{geo.height()}")
        
        win = WallpaperWindow(screen)
        frame_reader.frame_ready.connect(win.display_frame)
        win.show()
        windows.append(win)

    frame_reader.start_reading()
    app.aboutToQuit.connect(frame_reader.stop_reading)
    
    sys.exit(app.exec_())