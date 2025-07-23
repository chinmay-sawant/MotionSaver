import sys
import os
import time
import signal
import ctypes
import threading

# --- New Import ---
import vlc

# --- PyQt5 and Win32 Imports ---
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt

import win32gui
import win32con
import cv2

# Ensure parent directory is in sys.path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('LiveWallpaperQt_VLC')


try:
    from screensaver_app.PasswordConfig import load_config, save_config
except ImportError:
    logger.info("Warning: Could not import 'load_config' or 'save_config'. Using default settings.")
    def load_config():
        return {'video_path': 'video.mp4'}
    def save_config(config):
        logger.info("Warning: Could not save config. This is a fallback.")

# --- Core Logic (Refactored for VLC) ---

class VlcPlayer:
    """
    Manages VLC playback, including looping, seeking to the last position,
    and saving the timestamp periodically.
    """
    SAVE_INTERVAL_SEC = 5.0

    def __init__(self, video_path, config):
        self.config = config
        self.video_path = video_path
        self.last_save_time = 0


        # Create a VLC instance with options for better performance and no extra windows.
        vlc_options = [
            '--no-xlib',
            '--no-video-title-show',
            '--avcodec-hw=any',  # Enable hardware decoding
            '--no-osd',           # Disable On-Screen Display (OSD)
            '--no-snapshot-preview'  # Disable the snapshot preview thumbnail
        ]
        self.instance = vlc.Instance(vlc_options)
        self.media_player = self.instance.media_player_new()

    def start_playback(self, hwnd: int, width: int, height: int):
        """
        Starts video playback on the given window handle (HWND).

        Args:
            hwnd: The integer window handle to draw the video on.
            width: The width of the video display area.
            height: The height of the video display area.
        """
        if not self.media_player:
            logger.error("VLC MediaPlayer not initialized.")
            return

        media = self.instance.media_new(self.video_path)
        
        self.media_player.set_media(media)

        # Tell VLC to draw on our QWidget
        self.media_player.set_hwnd(hwnd)
        # Configure video scaling to fill entire screen (removes black bars)
        # Set aspect ratio to match screen dimensions to stretch video
        screen_aspect = f"{width}:{height}"
        self.media_player.video_set_aspect_ratio(screen_aspect.encode('utf-8'))

        # Set video to stretch to fill the window completely
        self.media_player.video_set_scale(0)  # 0 = fit to window, stretching if necessary
        self.media_player.audio_set_mute(True)
            
      # Enable video looping
        media_list = self.instance.media_list_new([self.video_path])
        media_list_player = self.instance.media_list_player_new()
        media_list_player.set_media_list(media_list)
        media_list_player.set_media_player(self.media_player)
        media_list_player.set_playback_mode(vlc.PlaybackMode.loop)
        self.media_list_player = media_list_player  # Store reference
        self.media_list_player.play()
        # Resume from the last saved timestamp

    
        width, height = self.media_player.video_get_size()
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        logger.info(f"Video loaded: {self.video_path}")
        logger.info(f"Video Size: {width}x{height} pixels")
        logger.info(f"Video FPS: {fps} frames per second")

        if width <= 1920 and height <= 1080 and fps <= 30:
            event_manager = self.media_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._save_timestamp_callback)

            start_timestamp_sec = self.config.get('last_video_timestamp', 0)
            if start_timestamp_sec > 0:
                logger.info(f"Resuming video from {start_timestamp_sec:.2f} seconds.")
                # VLC set_time expects milliseconds
                self.media_player.set_time(int(start_timestamp_sec * 1000))
        
        # if the video is larger than 1080p, we don't set a start time
        # also we will set the starting frame as the wallpaper
        else:
            from utils.wallpaper import capture_image_from_player
            if not capture_image_from_player(self.media_player):
                logger.error("Failed to set wallpaper using VLC media player.")
        logger.info("VLC playback started.")

    def _save_timestamp_callback(self, event):
        """Callback triggered by VLC when the playback time changes."""
        current_time = time.time()
        if current_time - self.last_save_time > self.SAVE_INTERVAL_SEC:
            # get_time returns milliseconds
            timestamp_ms = self.media_player.get_time()
            if timestamp_ms > 0:
                timestamp_sec = timestamp_ms / 1000.0
                self.config['last_video_timestamp'] = timestamp_sec
                save_config(self.config)
                self.last_save_time = current_time

    def stop_playback(self):
        """Stops playback and saves the final timestamp."""
        if self.media_player and self.media_player.is_playing():
            # Save final position before stopping
            timestamp_ms = self.media_player.get_time()
            if timestamp_ms > 0:
                self.config['last_video_timestamp'] = timestamp_ms / 1000.0
                save_config(self.config)
                logger.info(f"Saved final video timestamp: {self.config['last_video_timestamp']:.2f}s")

            self.media_player.stop()
        
        if self.media_player:
            self.media_player.release()
            self.media_player = None
            logger.info("VLC playback stopped and resources released.")


class WallpaperWindow(QWidget):
    """
    A QWidget that acts as a wallpaper. It serves as a drawing surface for VLC.
    """
    def __init__(self, screen):
        super().__init__()
        self.screen_geometry = screen.geometry()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        # The black background helps avoid flashes of the desktop before VLC starts.
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setStyleSheet("background-color: black;")
        # Set initial geometry
        self.setScreenGeometry(self.screen_geometry)

    def setScreenGeometry(self, geometry):
        """Updates the screen geometry."""
        self.screen_geometry = geometry
        self.setGeometry(self.screen_geometry)

    def showEvent(self, event):
        """
        On showing the window, use the Win32 API to parent it to the desktop
        background layer, making it a true wallpaper.
        """
        progman = win32gui.FindWindow("Progman", None)
        # This message is sent to Progman to spawn a WorkerW window if it doesn't exist.
        win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)

        # Find the WorkerW window, which is the layer behind the desktop icons.
        workerw_hwnd = 0
        def enum_windows_callback(hwnd, lParam):
            nonlocal workerw_hwnd
            if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                workerw_hwnd = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
            return True
        win32gui.EnumWindows(enum_windows_callback, None)

        # Get our QWidget's window handle.
        hwnd = self.winId().__int__()

        if workerw_hwnd:
            win32gui.SetParent(hwnd, workerw_hwnd)
        else:
            logger.warning("Could not find WorkerW. Attaching to Progman as a fallback.")
            win32gui.SetParent(hwnd, progman)

        # Position the window.
        geo = self.screen_geometry
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, geo.x(), geo.y(), geo.width(), geo.height(), win32con.SWP_NOACTIVATE)
        super().showEvent(event)


# --- Application Entry Point (Refactored) ---

class LiveWallpaperController:
    app = None
    vlc_player = None
    windows = []

    @staticmethod
    def start_live_wallpaper(video_path):
        logger.info("Entered start_live_wallpaper function.")
        try:
            config = load_config()
            config['video_path'] = video_path
            if not os.path.exists(video_path):
                logger.error(f"Error: Video file not found at '{video_path}'")
                return

            LiveWallpaperController.app = QApplication.instance() or QApplication(sys.argv)
            
            primary_screen = LiveWallpaperController.app.primaryScreen()
            if not primary_screen:
                logger.error("Error: Could not determine the primary screen.")
                return
            
            # --- CHANGE 2: RESTORED MULTI-MONITOR OFFSET LOGIC ---
            # This logic calculates the correct geometry for the wallpaper window,
            # especially to handle cases where a secondary monitor is positioned
            # to the left of the primary monitor.
            
            win = WallpaperWindow(primary_screen)

            monitor_count = len(QApplication.screens())
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

            LiveWallpaperController.windows.append(win)

            # The window MUST be shown before we can get its winId() and pass it to VLC.
            win.show()

            # Create the VLC player and start playback on our window
            LiveWallpaperController.vlc_player = VlcPlayer(video_path, config)
            hwnd = win.winId().__int__()
            LiveWallpaperController.vlc_player.start_playback(hwnd,win.width(),win.height())

            LiveWallpaperController.app.aboutToQuit.connect(LiveWallpaperController.stop_live_wallpaper)

            # Set up signal handler for Ctrl+C
            def handle_sigint(signum, frame):
                logger.info("SIGINT received. Stopping live wallpaper...")
                LiveWallpaperController.stop_live_wallpaper()

            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, handle_sigint)

            logger.info("Entering Qt event loop.")
            LiveWallpaperController.app.exec_()

        except Exception as e:
            logger.error(f"Exception in start_live_wallpaper: {e}", exc_info=True)

    @staticmethod
    def stop_live_wallpaper():
        logger.info("Entered stop_live_wallpaper function.")
        try:
            if LiveWallpaperController.vlc_player:
                logger.info("Stopping VLC player.")
                LiveWallpaperController.vlc_player.stop_playback()
                LiveWallpaperController.vlc_player = None
            
            # Close the wallpaper window(s)
            for win in LiveWallpaperController.windows:
                win.close()
            LiveWallpaperController.windows = []

            LiveWallpaperController.revertToOgWallpaper()
            
            if LiveWallpaperController.app:
                logger.info("Quitting QApplication.")
                LiveWallpaperController.app.quit()
        except Exception as e:
            logger.error(f"Exception in stop_live_wallpaper: {e}", exc_info=True)
            
    @staticmethod
    def revertToOgWallpaper():
        """Reverts the wallpaper to the original by telling Windows to refresh it."""
        try:
            SPI_SETDESKWALLPAPER = 20
            # Passing an empty string or None to SystemParametersInfoW forces a refresh
            # of the current configured wallpaper from the registry.
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, "", 3)
            logger.info(f"Reverted wallpaper to system default.")
        except Exception as e:
            logger.warning(f"Failed to revert wallpaper: {e}")

# Example of how to run this, if this file were executed directly
if __name__ == '__main__':
    # You would need a video file named 'video.mp4' in the same directory
    video_file = 'video.mp4' 
    if not os.path.exists(video_file):
        logger.error(f"Test video '{video_file}' not found. Please create it or change the path.")
    else:
        # This will run the wallpaper until you press Ctrl+C in the console
        LiveWallpaperController.start_live_wallpaper(video_file)