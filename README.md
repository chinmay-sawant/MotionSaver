### Repository Traffic Stats

![GitHub Clones](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/clones_badge.svg)&nbsp;&nbsp;![GitHub Views](https://github.com/chinmay-sawant/MotionSaver/blob/master/.github/badges/views_badge.svg)

# MotionSaver: Your Dynamic Video Screensaver 🚀

Transform your dull desktop into a lively and dynamic space! MotionSaver brings your screen to life with video wallpapers when you're away, combining the elegance of macOS live wallpapers with powerful customization for Windows.


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

1.  **Clone the Repository**: 
    ```bash
    git clone https://github.com/chinmay-sawant/MotionSaver.git
    cd MotionSaver
    ```
2.  **Install Dependencies**: 
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure**: Run the settings GUI to configure your video and preferences:
    ```bash
    python PhotoEngine.py --mode gui
    ```
4.  **Start Background Service**: Use the provided batch file to start listening for the screensaver shortcut:
    ```bash
    MotionSaver.bat
    ```
5.  **Activate**: Press `Win + S` to launch the screensaver anytime!

For detailed instructions, see the **[INSTALLATION.md](INSTALLATION.md)** file.

## Usage 👨‍💻

Run the application with different modes from your command prompt or terminal:

-   **Settings GUI**: `python PhotoEngine.py --mode gui`
-   **Screensaver Mode**: `python PhotoEngine.py --mode saver`
-   **System Tray Mode**: `python PhotoEngine.py --mode tray` (or use `MotionSaver.bat`)
-   **Admin Mode (for service management)**: `python PhotoEngine.py --mode admin` (Requires running as Administrator)

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


## Troubleshooting Common Issues 🛠️

### `pip` Not Found

If you see an error like `'pip' is not recognized as an internal or external command`:

- Make sure Python is installed. You can check by running `python --version` in your terminal.
- If Python is installed but `pip` is missing, try:
    - On Windows: Run `python -m ensurepip --upgrade` or `python -m pip install --upgrade pip`.
    - Add Python and the `Scripts` folder to your system `PATH` environment variable.
- Restart your terminal after making changes.

### `ModuleNotFoundError`

If you get an error such as `ModuleNotFoundError: No module named 'xyz'`:

- Ensure all dependencies are installed:  
  ```bash
  pip install -r requirements.txt
  ```
- If the error persists, check that you are using the correct Python environment (especially if you use virtual environments).
- You can install missing modules individually:  
  ```bash
  pip install module_name
  ```
- If you have multiple versions of Python, try using `python -m pip install ...` to ensure you are installing to the right interpreter.

If you continue to have issues, please open an [issue on GitHub](https://github.com/chinmay-sawant/MotionSaver/issues) with details.