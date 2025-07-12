import sys
import os
import cv2
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
import win32gui
import win32con
import win32api
import win32process
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.PasswordConfig import load_config

class WallpaperWindow(QWidget):
    frame_ready = pyqtSignal(object)

    def __init__(self, video_path, fps, screen):
        super().__init__()
        geo = screen.geometry()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        self.label = QLabel(self)
        self.label.setGeometry(0, 0, geo.width(), geo.height())
        self.label.setScaledContents(True)
        self.cap = cv2.VideoCapture(video_path)
        self.fps = fps
        self.running = True
        self.frame_ready.connect(self.display_frame)

        # Attach to desktop background for this monitor
        self.attach_to_desktop(geo)

        # Start frame reading thread
        self.thread = threading.Thread(target=self.frame_reader, daemon=True)
        self.thread.start()

    def attach_to_desktop(self, geo):
        progman = win32gui.FindWindow("Progman", None)
        win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
        workerw = None
        # Find the correct WorkerW (the one without SHELLDLL_DefView child)
        def enum_windows_callback(hwnd, lParam):
            nonlocal workerw
            if win32gui.GetClassName(hwnd) == "WorkerW":
                child = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                if child == 0:
                    workerw = hwnd
        win32gui.EnumWindows(enum_windows_callback, None)
        hwnd = self.winId().__int__()
        if workerw:
            win32gui.SetParent(hwnd, workerw)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, geo.x(), geo.y(), geo.width(), geo.height(), win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
        else:
            # Fallback to Progman
            win32gui.SetParent(hwnd, progman)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, geo.x(), geo.y(), geo.width(), geo.height(), win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)

    def frame_reader(self):
        interval = 1.0 / self.fps
        while self.running:
            start = cv2.getTickCount()
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            if ret:
                self.frame_ready.emit(frame)
            elapsed = (cv2.getTickCount() - start) / cv2.getTickFrequency()
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                cv2.waitKey(int(sleep_time * 1000))

    def display_frame(self, frame):
        # No downscaling, use original frame size
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qt_img))

    def showEvent(self, event):
        self.label.setGeometry(self.rect())
        super().showEvent(event)

if __name__ == "__main__":
    config = load_config()
    video_path = config.get('video_path', 'video.mp4')
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        sys.exit(1)
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if not video_fps or video_fps < 1:
        video_fps = 30
    cap.release()
    app = QApplication(sys.argv)
    screens = app.screens()
    windows = []
    for screen in screens:
        win = WallpaperWindow(video_path, video_fps, screen)
        win.showFullScreen()
        windows.append(win)
    sys.exit(app.exec_())
