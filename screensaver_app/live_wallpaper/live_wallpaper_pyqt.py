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
import signal
from screensaver_app.central_logger import get_logger
logger = get_logger('LiveWallpaperQt')
# --- Configuration and Path Setup ---

# Ensure the project root is in the path for custom module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# This import might fail if the structure is different.
# A fallback is provided for easy testing.
try:
    from screensaver_app.PasswordConfig import load_config, save_config
    from PyQt5.QtWidgets import QApplication
    
except ImportError:
    logger.info("Warning: Could not import 'load_config' or 'save_config'. Using default settings.")
    def load_config():
        """Fallback function if the original config loader is not found."""
        return {'video_path': 'video.mp4'}

    def save_config(config):
        """Fallback function if the original config saver is not found."""
        logger.info("Warning: Could not save config. This is a fallback.")

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
            logger.info(f"Error: Could not open video file {self.video_path}")
            return

        # Load last timestamp from config and seek the video position
        start_timestamp_sec = self.config.get('last_video_timestamp', 0)
        if start_timestamp_sec > 0:
            logger.info(f"Resuming video from {start_timestamp_sec:.2f} seconds.")
            self.cap.set(cv2.CAP_PROP_POS_MSEC, start_timestamp_sec * 1000)

        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def stop_reading(self):
        """Stops the reading loop and releases the video capture resources. Also stores the last video timestamp in seconds."""
        self.running = False
        # Store the current video timestamp in seconds before releasing
        if hasattr(self, 'cap') and self.cap.isOpened():
            timestamp_sec = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            self.config['last_video_timestamp'] = timestamp_sec
            self.config['enable_livewallpaper'] = False  # Disable live wallpaper on stop
            save_config(self.config)
            logger.info(f"Saved last video timestamp: {timestamp_sec} seconds.")
        if hasattr(self, 'thread'):
            self.thread.join()
        if hasattr(self, 'cap'):
            self.cap.release()
            logger.info("Video capture released.")
        self.revertToOgWallpaper()

    def revertToOgWallpaper(self):
        """Reverts the wallpaper for all monitors to the original wallpaper."""
        try:
            import ctypes
            from PyQt5.QtWidgets import QApplication
            SPI_SETDESKWALLPAPER = 20
            app = QApplication.instance()
            screens = app.screens() if app else []
            # This logic will refresh the wallpaper for all screens
            for idx, screen in enumerate(screens):
                # If you have the original wallpaper path per screen, use it here
                # For now, just refresh the wallpaper (reapplies current wallpaper)
                ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, None, 3)
                logger.info(f"Reverted wallpaper for screen {idx}.")
        except Exception as e:
            logger.info(f"Failed to revert wallpaper: {e}")

    def _read_loop(self):
        """The main loop that reads frames and periodically saves the timestamp."""
        # Cap FPS to reduce GPU usage
        interval = 1.0 / min(self.fps, 24)  # Cap at 24 FPS
        while self.running:
            start_time = time.perf_counter()

            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            self.frame_ready.emit(frame)

            # Periodically save the current video timestamp in seconds
            current_time = time.time()
            if current_time - self.last_save_time > self.SAVE_INTERVAL:
                timestamp_sec = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                self.config['last_video_timestamp'] = timestamp_sec
                save_config(self.config)
                self.last_save_time = current_time

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # If processing is too fast, yield to OS
                time.sleep(0.005)


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
        self.label.setScaledContents(False)
        # Detect NVIDIA GPU
        try:
            # Check if cv2 has cuda module and device count
            if hasattr(cv2, "cuda") and hasattr(cv2.cuda, "getCudaEnabledDeviceCount"):
                self.has_cuda = cv2.cuda.getCudaEnabledDeviceCount() > 0
                if self.has_cuda:
                    logger.info("NVIDIA GPU detected. Using CUDA for frame processing.")
                else:
                    logger.info("No NVIDIA GPU detected. Using CPU for frame processing.")
            else:
                self.has_cuda = False
                logger.info("OpenCV CUDA module not found. Using CPU for frame processing.")
        except Exception as e:
            self.has_cuda = False
            logger.info(f"CUDA detection failed: {e}")

    def setScreenGeometry(self, geometry):
        """Updates the screen geometry and resizes the label accordingly."""
        self.screen_geometry = geometry
        self.setGeometry(self.screen_geometry)
        self.label.setGeometry(self.rect())
        self.label.setScaledContents(False)

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
            logger.info("Warning: Could not find WorkerW. Attaching to Progman as a fallback.")
            win32gui.SetParent(hwnd, progman)

        geo = self.screen_geometry
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, geo.x(), geo.y(), geo.width(), geo.height(), win32con.SWP_NOACTIVATE)
        super().showEvent(event)

    def display_frame(self, frame):
        """
        Receives a raw frame and efficiently scales it to fill the monitor
        without distortion before displaying.
        """
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
        
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR

        if self.has_cuda:
            # Use CUDA for resizing and color conversion
            try:
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                gpu_resized = cv2.cuda.resize(gpu_frame, (new_w, new_h), interpolation=interpolation)
                crop_x = (new_w - target_w) // 2
                crop_y = (new_h - target_h) // 2
                gpu_cropped = gpu_resized.rowRange(crop_y, crop_y + target_h).colRange(crop_x, crop_x + target_w)
                gpu_rgb = cv2.cuda.cvtColor(gpu_cropped, cv2.COLOR_BGR2RGB)
                final_frame = gpu_rgb.download()
            except Exception as e:
                logger.info(f"CUDA frame processing failed: {e}")
                # Fallback to CPU
                resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=interpolation)
                crop_x = (new_w - target_w) // 2
                crop_y = (new_h - target_h) // 2
                final_frame = resized_frame[crop_y:crop_y + target_h, crop_x:crop_x + target_w]
                final_frame = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
        else:
            resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=interpolation)
            crop_x = (new_w - target_w) // 2
            crop_y = (new_h - target_h) // 2
            final_frame = resized_frame[crop_y:crop_y + target_h, crop_x:crop_x + target_w]
            final_frame = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)

        h, w, ch = final_frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(final_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        self.label.setPixmap(QPixmap.fromImage(qt_img))

    def resizeEvent(self, event):
        """Ensures the label resizes with the window."""
        self.label.setGeometry(self.rect())
        super().resizeEvent(event)


# --- Application Entry Point ---

class LiveWallpaperController:
    app = None
    frame_reader = None
    windows = []

    @staticmethod
    def start_live_wallpaper(video_path):
        logger.info("Entered start_live_wallpaper function.")
        try:
            logger.info("Starting live wallpaper...")
            config = load_config()
            config['video_path'] = video_path
            if not os.path.exists(video_path):
                logger.error(f"Error: Video file not found at '{video_path}'")
                return

            LiveWallpaperController.app = QApplication.instance() or QApplication(sys.argv)

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Error: Failed to open video file with OpenCV: '{video_path}'")
                return
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if not video_fps or video_fps < 1:
                logger.warning("FPS not detected or invalid. Defaulting to 30 FPS.")
                video_fps = 30
            cap.release()

            logger.info(f"Video FPS set to: {video_fps}")
            LiveWallpaperController.frame_reader = FrameReader(video_path, video_fps, config)
            LiveWallpaperController.windows = []

            primary_screen = LiveWallpaperController.app.primaryScreen()
            if not primary_screen:
                logger.error("Error: Could not determine the primary screen.")
                return

            logger.info("Found primary screen. Creating wallpaper window...")
            win = WallpaperWindow(primary_screen)

            monitor_count = QApplication.screens().__len__()
            logger.info(f"Detected {monitor_count} monitors.")
            if monitor_count > 1:
                calculate_x = 0
                calculate_width = 0
                calculate_height = 0
                geo = None
                for idx, screen in enumerate(QApplication.screens()):
                    tempgeo = screen.geometry()
                    is_primary = (screen == primary_screen)
                    logger.info(f"Screen {idx}: geometry={tempgeo}, is_primary={is_primary}")
                    if is_primary:
                        calculate_width = tempgeo.width()
                        calculate_height = tempgeo.height()
                        geo = tempgeo
                    else:
                        if tempgeo.x() < 0:
                            calculate_x += tempgeo.width()
                logger.info(f"Calculated x for next screen: {calculate_x}, Calculate width: {calculate_width}, Calculate height: {calculate_height}")
                geo.setX(calculate_x)
                geo.setWidth(calculate_width)
                win.setScreenGeometry(geo)
                logger.info(f"Primary screen geometry: x={primary_screen.geometry().x()}, y={primary_screen.geometry().y()}, width={primary_screen.geometry().width()}, height={primary_screen.geometry().height()}")
                logger.warning(f"Warning: More than 1 monitor detected ({monitor_count}). This app only uses the primary screen.")

            LiveWallpaperController.frame_reader.frame_ready.connect(win.display_frame)
            win.show()
            LiveWallpaperController.windows.append(win)

            logger.info("Starting frame reader thread.")
            LiveWallpaperController.frame_reader.start_reading()
            LiveWallpaperController.app.aboutToQuit.connect(LiveWallpaperController.frame_reader.stop_reading)

            def handle_sigint(signum, frame):
                logger.info("SIGINT received. Stopping frame reader and exiting...")
                LiveWallpaperController.stop_live_wallpaper()

            import threading
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, handle_sigint)
                logger.info("SIGINT handler set.")
            else:
                logger.info("SIGINT handler not set: not in main thread.")
            logger.info("Entering Qt event loop.")
            LiveWallpaperController.app.exec_()
        except Exception as e:
            logger.error(f"Exception in start_live_wallpaper: {e}", exc_info=True)

    @staticmethod
    def stop_live_wallpaper():
        logger.info("Entered stop_live_wallpaper function.")
        try:
            if LiveWallpaperController.frame_reader:
                logger.info("Stopping frame reader.")
                LiveWallpaperController.frame_reader.stop_reading()
                LiveWallpaperController.frame_reader = None
            if LiveWallpaperController.app:
                logger.info("Quitting QApplication.")
                LiveWallpaperController.app.quit()
                LiveWallpaperController.app = None
            LiveWallpaperController.windows = []
        except Exception as e:
            logger.error(f"Exception in stop_live_wallpaper: {e}", exc_info=True)