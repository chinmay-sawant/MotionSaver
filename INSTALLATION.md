# MotionSaver Installation Guide 🛠️

This guide provides instructions for installing and running the MotionSaver application.

## 🚨 Security Pre-check

Before you install, please read the security warning in the [README.md](README.md). This application is for **personal home use only** and should not be used in security-critical environments.

## Table of Contents
- [Installation for Users (Recommended)](#installation-for-users-recommended)
  - [Method 1: From Source Code](#method-1-from-source-code)
- [Installation for Developers](#installation-for-developers)
  - [Method 2: Development Setup](#method-2-development-setup)
- [Advanced Setup](#advanced-setup)
  - [Running as a Windows Service](#running-as-a-windows-service)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Installation for Users (Recommended)

This is the easiest way to get started with MotionSaver using the provided batch file.

### Prerequisites
- **Operating System**: Windows 10 or Windows 11.
- **Git**: [Download & Install Git](https://git-scm.com/downloads).
- **Python**: Version 3.8 or higher. [Download & Install Python](https://www.python.org/downloads/) (ensure you check "Add Python to PATH").
- **Permissions**: Standard user permissions are sufficient for normal use. Administrator rights are needed to install it as a service.

### Method 1: From Source Code

#### Step 1: Clone the Repository
```bash
git clone https://github.com/chinmay-sawant/MotionSaver.git
cd MotionSaver
```

#### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 3: Initial Configuration
```bash
# Run the settings GUI to configure the application
python PhotoEngine.py --mode gui
```

1.  In the settings window, go to the **"General Settings"** tab.
2.  Click **"Select Video"** to choose a video file for your screensaver background.
3.  Go to the **"Users"** tab to add a user and set a password for unlocking the screensaver.
4.  Explore the **"Widgets"** and **"Appearance"** tabs to customize your experience.
5.  Click **"Save & Close"**.

#### Step 4: Start Background Service
Use the provided batch file to start MotionSaver in the background:
```bash
# Double-click MotionSaver.bat or run from command line
MotionSaver.bat
```

This will start the application in tray mode, listening for the `Win + S` shortcut to activate the screensaver.

#### Step 5: Launch the Screensaver
You can start the screensaver in several ways:
- Press `Win + S` while the background service is running.
- From the system tray icon, right-click and select "Start Screensaver".
- Run from the command line: `python PhotoEngine.py --mode saver`.

---

## Installation for Developers

This method is for users who want to modify the source code or contribute to the project.

### Prerequisites
- **Git**: [Download & Install Git](https://git-scm.com/downloads).
- **Python**: Version 3.8 or higher. [Download & Install Python](https://www.python.org/downloads/) (ensure you check "Add Python to PATH").

### Method 2: Development Setup

#### Step 1: Clone the Repository
```bash
git clone https://github.com/chinmay-sawant/MotionSaver.git
cd MotionSaver
```

#### Step 2: Create a Virtual Environment (Recommended)
```bash
# Create the virtual environment
python -m venv venv

# Activate it
# On Windows Command Prompt
venv\Scripts\activate
# On PowerShell
venv\Scripts\Activate.ps1
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 4: Run the Application
```bash
# Run the settings GUI
python PhotoEngine.py --mode gui

# Run the screensaver
python PhotoEngine.py --mode saver

# Run in background (tray mode)
python PhotoEngine.py --mode tray
```

---

## Advanced Setup

### Running as a Windows Service

This allows MotionSaver to run automatically in the background. **Administrator privileges are required.**

1.  **Run in Admin Mode**: Right-click your Command Prompt or PowerShell and select "Run as administrator". Navigate to the MotionSaver directory.
2.  **Launch Admin GUI**:
    ```bash
    python PhotoEngine.py --mode admin
    ```
3.  **Use the GUI**: In the settings window, a "Service Management" section will be visible.
    -   **Install Service**: Registers MotionSaver as a Windows service.
    -   **Start Service**: Starts the service.
    -   **Stop Service**: Stops the service.
    -   **Uninstall Service**: Removes the service from your system.

---

## Configuration

-   All settings are stored in a `userconfig.json` file located in a `config` sub-folder, which is created automatically in the same directory as the source code.
-   You can configure everything through the GUI (`python PhotoEngine.py --mode gui`).

---

## Troubleshooting

#### Screensaver Doesn't Start
-   Ensure you have selected a valid video file in the settings.
-   Check if your video format is supported (MP4 is recommended).
-   Ensure all dependencies in `requirements.txt` are installed correctly.
-   Make sure the background service is running (`MotionSaver.bat` or `python PhotoEngine.py --mode tray`).

#### Widgets Not Working
-   **Weather/Stock**: These widgets require an active internet connection. Check your firewall settings to ensure Python is not blocked.
-   **Media Widget**: This relies on Windows Media Session. It may not work on older versions of Windows or "N" editions without the Media Feature Pack installed.

#### Permission Errors
-   If you see permission errors when trying to install the service, make sure you are running the command or the GUI as an Administrator.

#### Background Service Not Working
-   Ensure Python is added to your system PATH.
-   Check if the batch file is being blocked by antivirus software.
-   Try running `python PhotoEngine.py --mode tray` directly from command line to see error messages.

---

## Uninstallation

#### Standard Uninstallation:
1.  **Stop the Service (if installed)**: Run `python PhotoEngine.py --mode admin` as an Administrator and click "Stop Service", then "Uninstall Service".
2.  **Stop the Background Service**: Close the MotionSaver.bat process or exit from the system tray.
3.  **Delete the Files**: Delete the entire `MotionSaver` directory.

#### If you used a Virtual Environment:
1.  **Uninstall the Service (if installed)**: Run `python PhotoEngine.py --mode admin` as an Administrator and use the GUI to stop and uninstall the service.
2.  **Deactivate Virtual Environment**:
    ```bash
    deactivate
    ```
3.  **Delete the Project Folder**: Simply delete the entire `MotionSaver` directory.

---

## Getting Help

### Resources
- **GitHub Issues**: [Report bugs or request features](https://github.com/chinmay-sawant/MotionSaver/issues)
- **Documentation**: Check README.md for feature overview
- **Configuration**: Review example config files

### Support Information
When reporting issues, please include:
- Python version (`python --version`)
- Operating System version
- Error messages (full stack trace)
- Configuration file (remove sensitive data)
- Steps to reproduce the issue

### Community
- **GitHub Discussions**: Share usage tips and configurations
- **Contributions Welcome**: Fork, improve, and submit pull requests

---

**Created by**: [Chinmay Sawant](https://github.com/chinmay-sawant)  
**Project**: MotionSaver - Dynamic Video Screensaver  
**License**: [Check repository for license information]
### Step 2: Self-contained Installation
```bash
# Create portable directory structure
mkdir MotionSaver-Portable
cd MotionSaver-Portable

# Copy application files
# Copy entire MotionSaver directory here

# Install dependencies locally
pip install --target ./lib -r requirements.txt
```

### Step 3: Create Launch Scripts
Create `run_screensaver.bat`:
```batch
@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\lib;%PYTHONPATH%
python PhotoEngine.py --mode saver
```

Create `run_settings.bat`:
```batch
@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\lib;%PYTHONPATH%
python PhotoEngine.py --mode gui
```

### Step 4: Portable Configuration
- All settings stored in `config/userconfig.json` within app directory
- Video files can be placed in `videos/` subdirectory
- Relative paths recommended for portability

---

## Method 5: Advanced/Enterprise Setup

**Best for:** Large deployments, corporate environments, or advanced configurations

### Step 1: Centralized Configuration
1. Create shared configuration template:
```json
{
  "video_path": "\\\\server\\share\\videos\\corporate_video.mp4",
  "enable_weather_widget": false,
  "enable_stock_widget": false,
  "enable_media_widget": false,
  "run_as_admin": true,
  "default_user_for_display": "Corporate",
  "users": [
    {
      "username": "Corporate",
      "password_hash": "your_hash_here",
      "profile_pic_path": "\\\\server\\share\\icons\\logo.png"
    }
  ]
}
```

### Step 2: Group Policy Deployment
1. Create MSI package or use deployment tools
2. Configure via Group Policy for domain computers
3. Set registry keys for default configuration

### Step 3: Enhanced Security Configuration
```bash
# Run with maximum security
python PhotoEngine.py --mode admin --enhanced-security

# Enable all blocking features
python enhanced_key_blocker.py
```

### Step 4: Monitoring and Logging
1. Configure Windows Event Logging
2. Set up monitoring for service health
3. Create maintenance scripts for updates

### Enterprise Features
- **Centralized video management**
- **Domain user integration**
- **Group Policy configuration**
- **Remote monitoring capabilities**
- **Automated deployment scripts**

---

## Configuration

### Initial Configuration
After installation, configure the application:

1. **Video Source**: Point to your video file
2. **User Profile**: Set up user account(s)
3. **Display Settings**: Configure clock, themes, fonts
4. **Widgets**: Enable/disable weather, stocks, media player
5. **Security**: Set password protection level

### Configuration File Location
- Default: `config/userconfig.json`
- Service mode: Same location, accessed by service account
- Portable: Relative to application directory

### Important Settings
```json
{
  "video_path": "C:\\Videos\\screensaver.mp4",
  "enable_weather_widget": true,
  "weather_pincode": "400068",
  "weather_country": "IN",
  "enable_stock_widget": false,
  "stock_market": "NASDAQ",
  "enable_media_widget": true,
  "font_family": "Arial",
  "font_size": 48,
  "theme": "dark",
  "run_as_admin": false
}
```

---

## Platform-Specific Notes

### Windows 10/11
- Full feature support
- Windows SDK integration for media controls
- Service installation available
- Enhanced security features supported

### Windows 7/8.1
- Basic functionality supported
- Limited Windows SDK features
- Manual service configuration may be required
- Some modern APIs not available

### Alternative Platforms
While primarily designed for Windows, basic functionality may work on:
- **Linux**: Limited support, no service integration
- **macOS**: Basic video playback only, no Windows-specific features

---

## Troubleshooting

### Common Issues

#### Python/Pip Issues
```bash
# Update pip
python -m pip install --upgrade pip

# Reinstall requirements
pip uninstall -r requirements.txt
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.8+
```

#### Video Playback Issues
- **Codec problems**: Install K-Lite Codec Pack or VLC codec package
- **Performance issues**: Reduce video resolution/bitrate
- **Format support**: Convert to MP4 with H.264 codec

#### Permission Issues
```bash
# Run as administrator
python PhotoEngine.py --mode admin

# Check UAC settings
# Ensure UAC is not set to "Never notify"
```

#### Service Installation Problems
```cmd
# Check Windows services
services.msc

# Verify admin privileges
whoami /priv

# Manual service removal
sc delete ScreenSaverService
```

#### Widget Issues
- **Weather not loading**: Check internet connection and pincode
- **Stock data missing**: Verify market selection and internet access
- **Media widget not detecting**: Ensure Windows Media Feature Pack is installed

### Advanced Troubleshooting

#### Debug Mode
```bash
# Enable debug output
python PhotoEngine.py --mode saver --debug

# Check logs
# Review console output for error messages
```

#### Network Issues
```bash
# Test weather API
python -c "from widgets.weather_api import get_weather_data; print(get_weather_data())"

# Test stock API
python -c "from widgets.stock_widget import StockWidget; w = StockWidget(None); print(w.fetch_stock_data(['AAPL']))"
```

#### Registry Issues (Admin required)
```cmd
# Reset task manager (if blocked)
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" /v DisableTaskMgr /f

# Reset Windows hotkeys
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer" /v NoWinKeys /f
```

---

## Uninstallation

### Standard Uninstallation
1. **Stop any running instances**
2. **Remove Windows service** (if installed):
   ```bash
   python screensaver_service.py remove
   # Or via GUI: Stop Service → Uninstall Service
   ```
3. **Delete application directory**
4. **Remove configuration** (optional):
   - Delete `config/userconfig.json`
   - Clear any temporary files

### Complete Removal
```bash
# Remove Python packages (if dedicated installation)
pip uninstall -r requirements.txt

# Remove registry entries (if any security features were used)
# Run as administrator:
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" /v DisableTaskMgr /f
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer" /v NoWinKeys /f

# Remove service
sc delete ScreenSaverService
```

### Clean Virtual Environment Removal
```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment directory
rmdir /s venv
```

---

## Getting Help

### Resources
- **GitHub Issues**: [Report bugs or request features](https://github.com/chinmay-sawant/MotionSaver/issues)
- **Documentation**: Check README.md for feature overview
- **Configuration**: Review example config files

### Support Information
When reporting issues, please include:
- Python version (`python --version`)
- Operating System version
- Error messages (full stack trace)
- Configuration file (remove sensitive data)
- Steps to reproduce the issue

### Community
- **GitHub Discussions**: Share usage tips and configurations
- **Contributions Welcome**: Fork, improve, and submit pull requests

---

**Created by**: [Chinmay Sawant](https://github.com/chinmay-sawant)  
**Project**: MotionSaver - Dynamic Video Screensaver  
**License**: [Check repository for license information]
