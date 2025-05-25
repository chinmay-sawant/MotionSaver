# MotionSaver

A modern, customizable screensaver that displays a video background with an elegant overlay showing the current time, user profile, and username.

## Demo
[![MotionSaver Demo](http://img.youtube.com/vi/8JzlZ49vus4/0.jpg)](https://www.youtube.com/watch?v=8JzlZ49vus4)
[![MotionSaver Demo](http://img.youtube.com/vi/3UxKSrSMv0o/0.jpg)](https://www.youtube.com/watch?v=3UxKSrSMv0o)

## Features

- Video background playback with optimized performance
- Digital clock with customizable font and size
- User profile display with customizable appearance
- Dark mode support
- Multi-monitor support (main content on primary monitor)
- Password protection with macOS-style login dialog
- Extensive configuration options

## Technologies Used

- **Python 3.10+**: Core programming language
- **Tkinter**: GUI framework for the interface
- **OpenCV (cv2)**: Video processing and playback
- **PIL/Pillow**: Image processing and text rendering
- **Threading**: Multi-threaded pipeline for smooth video playback
- **JSON**: Configuration file storage

## Installation

### Prerequisites

- Python 3.10 or higher
- Git (for cloning the repository)

### From GitHub

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/VideoClockScreenSaver.git
   cd VideoClockScreenSaver
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the screensaver:
   ```bash
   python PhotoEngine.py
   ```

5. To run the configuration GUI:
   ```bash
   python gui.py
   ```

## Configuration

The application stores user settings in `config/userconfig.json`.

You can modify these settings using the GUI or by directly editing the configuration file:

- `profile_pic_path`: Path to user profile picture
- `profile_pic_path_crop`: Path to cropped profile picture
- `video_path`: Path to video file for background
- `theme`: UI theme ("dark" or "light")
- `clock_font_family`: Font family for the clock
- `clock_font_size`: Font size for the clock
- `ui_font_family`: Font family for UI elements
- `ui_font_size`: Font size for UI elements
## Project Structure

```
d:\Chinmay_Personal_Projects\ScreenSaver\
├── PhotoEngine.py          # Main entry point for running the screensaver
├── gui.py                  # Configuration GUI
├── requirements.txt        # Project dependencies
├── README.md               # Documentation
├── config/                 # Configuration files
│   └── userconfig.json     # User configuration
├── screensaver_app/        # Core application package
│   ├── __init__.py
│   ├── PasswordConfig.py   # Password configuration and verification
│   └── video_player.py     # Video processing and display
└── assets/                 # Default media assets
    ├── default_video.mp4     # Default background video
    └── default_profile.png   # Default profile image
```
