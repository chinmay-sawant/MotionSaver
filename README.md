# MotionSaver: Your Dynamic Video Screensaver 🚀

Transform your dull desktop into a lively and dynamic space! MotionSaver brings your screen to life with video wallpapers when you're away, combining the elegance of macOS live wallpapers with powerful customization for Windows.

## Demo 🎬

Check out MotionSaver in action:

[![MotionSaver Demo](http://img.youtube.com/vi/8JzlZ49vus4/0.jpg)](https://www.youtube.com/watch?v=8JzlZ49vus4)
[![MotionSaver Demo](http://img.youtube.com/vi/3UxKSrSMv0o/0.jpg)](https://www.youtube.com/watch?v=3UxKSrSMv0o)

## 🚨 IMPORTANT SECURITY WARNING 🚨

**This application is intended for personal and home use only.**

Due to the complexity of blocking all Windows system shortcuts, **it is possible to bypass the screensaver using certain key combinations** (e.g., `Alt+Tab`, `Win+D`). This could grant unauthorized access to your desktop.

**⚠️ DO NOT use MotionSaver in public spaces, offices, or any environment where security is a concern.** The project is an ongoing effort, and full lock-screen security is not yet implemented. Use at your own risk.

## Features ✨

### 🎥 Core Video Engine
- **Dynamic Video Backgrounds**: High-performance video playback using OpenCV.
- **Multi-format Support**: Plays MP4, AVI, MOV, and more.
- **Performance Optimized**: Minimal CPU usage for efficient operation.

### 🖥️ Display & UI
- **Multi-monitor Support**: Main content on your primary monitor while others black out.
- **Customizable Clock**: Adjust font, size, color, and position.
- **User Profile Display**: Show your profile picture and username.
- **Transparent Overlays**: Clean, non-intrusive UI.

### 🔒 Security & Access Control
- **Password Protection**: Elegant, macOS-style login prompt.
- **Basic Key Blocking**: Prevents common exit attempts. (Note: Not foolproof, see warning above).

### 📊 Real-time Widgets
- **Weather Widget**: Current conditions and a 2-day forecast.
- **Stock Market Widget**: Real-time prices for NASDAQ, NYSE, NSE, BSE, and Crypto.
- **Media Player Widget**: Control media from Spotify, YouTube, and other apps.

### ⚙️ Configuration & Customization
- **Easy-to-use GUI**: A simple interface to manage all your settings.
- **Widget Management**: Toggle any widget on or off.
- **Video & Profile Management**: Easily select videos and manage user profiles.

## Quick Start ⚡

1.  **Download**: Grab the latest `PhotoEngine.exe` from the [Releases page](https://github.com/chinmay-sawant/MotionSaver/releases).
2.  **Run**: Double-click `PhotoEngine.exe`. No installation needed for basic use!
3.  **Configure**: The settings GUI will open. Set your desired video file, customize widgets, and add a user password.
4.  **Launch**: Run the screensaver directly from the GUI or using the command line.

For detailed instructions, see the **[INSTALLATION.md](INSTALLATION.md)** file.

## Usage 👨‍💻

Run `PhotoEngine.exe` with different modes from your command prompt or terminal:

-   **Settings GUI**: `PhotoEngine.exe --mode gui` (Default action on double-click)
-   **Screensaver Mode**: `PhotoEngine.exe --mode saver`
-   **System Tray Mode**: `PhotoEngine.exe --mode tray`
-   **Admin Mode (for service management)**: `PhotoEngine.exe --mode admin` (Requires running as Administrator)

## Technology Stack 🛠️

-   **Core**: Python, OpenCV, Tkinter, Pillow
-   **Media**: Pygame, Mutagen, WinSDK
-   **Windows Integration**: PyWin32, PyStray, Keyboard
-   **APIs**: Open-Meteo (Weather), Yahoo Finance (Stocks)

## Contributing 🤝

Contributions are welcome! Feel free to fork the repository, make changes, and submit pull requests.

-   Report bugs or suggest features.
-   Contribute code, documentation, or improvements.

This project is maintained by [Chinmay Sawant](https://github.com/chinmay-sawant).

**Found a bug or have a suggestion?**
Please use this form: [Submit an Issue or Suggestion](https://forms.gle/zhVFJnu5G1ySiBuC8)

## About the Project 💡

This project started as a dream inspired by Wallpaper Engine and the beautiful live wallpapers on macOS. For years, it was just an idea. But with the rise of AI development tools like GitHub Copilot, that dream became a reality in a single weekend. This application is a testament to the power of AI-assisted coding, turning what would have taken months into a 20-hour sprint.

I built it for my own personal use, and I'm sharing it in case others find it cool too. Enjoy!

## Community & Feedback

If you have any issues, want to report bugs, or would like to leave feedback, please use the [MotionSaver Subreddit](https://www.reddit.com/r/motionsaver/).