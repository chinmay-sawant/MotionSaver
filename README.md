### Repository Badges

![Total Clones](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/clones_badge.svg)
![Release V1](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/release_V1_badge.svg)
![Release V2](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/release_V2_badge.svg)
![Release V3](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/release_V3_badge.svg)
![Total Downloads](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/total_downloads_badge.svg)
![Total Views](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/views_badge.svg)

# MotionSaver: Your Dynamic Video Screensaver/Lockscreen 🚀

Transform your dull desktop into a lively and dynamic space! MotionSaver brings your screen to life with video wallpapers when you're away, combining the elegance of macOS live wallpapers with powerful customization for Windows.

## Installation & Usage ⚡

For detailed installation steps, refer to the  
[Installation Guide](https://github.com/chinmay-sawant/MotionSaver/blob/master/Installation/Installation.md).

To learn how to use MotionSaver after installation, see the [Usage](#usage-) section below.
---

### Upcoming Updates 🆕
- 🔑 **Key blocking will only be enabled after pressing Win + S** (for better usability).
- 🖥️ **Register the batch file as a Windows service** so MotionSaver starts automatically in the background when Windows boots.
- ⏲️ **Automatic Activation After Idle:** The screensaver will automatically activate if your computer is idle for more than 2 minutes. This feature is configurable in the settings GUI.

## Support & Contribute ⭐

If you like this application, please consider [starring the GitHub repository ⭐](https://github.com/chinmay-sawant/MotionSaver) to show your support!

- **🐞 Found an issue?**  
    Please [log it under Issues](https://github.com/chinmay-sawant/MotionSaver/issues) so it can be tracked and resolved.

- **👩‍💻 Want to contribute?**  
    If you're a developer, feel free to assign issues to yourself—just leave a comment 📝 indicating when you expect to complete it. Contributions of all kinds are welcome!

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
- **Dynamic Video Backgrounds**: High-performance video playback using OpenCV with GPU acceleration.
- **Multi-format Support**: Plays MP4, AVI, MOV, and more.
- **Performance Optimized**: Minimal CPU usage with automatic GPU detection and dedicated graphics card preference.
- **Smart GPU Selection**: Automatically detects and prefers dedicated graphics cards over integrated ones for optimal performance.

### 🖥️ Display & UI
- **Multi-monitor Support**: Main content on your primary monitor while others black out.
- **Customizable Clock**: Adjust font, size, color, and position.
- **User Profile Display**: Show your profile picture and username.
- **Transparent Overlays**: Clean, non-intrusive UI.
- **GPU-Accelerated Rendering**: Leverages hardware acceleration for smooth video playback.

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
- **GPU Selection**: Choose preferred graphics card for video rendering in the settings.

## Usage 👨‍💻


Run the application with different modes from your command prompt or terminal:

-   **Settings GUI**: Run `Gui.bat` as administrator
-   **Screensaver Mode**: Use `MotionSaver.bat` to start the screensaver service
-   **System Tray Mode**: Use `MotionSaver.bat` to run in the background

No Python commands are required for normal usage.

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

## What Works & What Doesn't 🛠️

### ✅ Working Features
- **Screensaver Activation:** The main feature—activating the screensaver—is fully functional. MotionSaver listens for `Win + S` in the background when you run `MotionSaver.bat`, allowing you to quickly launch the screensaver at any time.
- **Background Listening:** The app reliably detects the `Win + S` shortcut for screensaver activation when running in tray mode.

### ⚠️ Known Limitations
- **Low-Level Key Hooks:** Some system key hooks are not fully effective due to Windows restrictions. For example, combinations like `Alt + Win + Tab` can be released or bypassed after pressing the right `Alt` key once.
- **Shortcut Bypass:** Certain Windows shortcuts (e.g., `Alt+Tab`, `Win+D`) may still exit or minimize the screensaver, as noted in the security warning above.

**Tip:** For the best experience, start the background service using `MotionSaver.bat` and use `Win + S` to activate the screensaver. Be aware of the current limitations with system shortcuts.
