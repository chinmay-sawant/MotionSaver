# MotionSaver Installation Guide

This guide provides comprehensive installation instructions for the MotionSaver application across different scenarios and platforms.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Method 1: Basic Installation](#method-1-basic-installation)
- [Method 2: Development Setup](#method-2-development-setup)
- [Method 3: Windows Service Installation](#method-3-windows-service-installation)
- [Method 4: Portable Installation](#method-4-portable-installation)
- [Method 5: Advanced/Enterprise Setup](#method-5-advancedenterprise-setup)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Prerequisites

### System Requirements
- **Operating System**: Windows 10/11 (primary support), Windows 7/8.1 (limited testing)
- **Python**: Version 3.8 or higher
- **RAM**: Minimum 4GB, recommended 8GB+
- **Storage**: 500MB free space (plus space for video files)
- **Graphics**: DirectX 11 compatible graphics card
- **Permissions**: Standard user (Admin required for service installation and enhanced security features)

### Python Dependencies
The following Python packages are required (automatically installed via requirements.txt):

**Core Dependencies:**
- `opencv-python>=4.5.0` - Video processing engine
- `Pillow>=9.0.0` - Image manipulation
- `tk>=0.1.0` - GUI framework (usually included with Python)
- `numpy>=1.20.0` - Numerical operations
- `screeninfo>=0.8` - Multi-monitor support

**Media & Graphics:**
- `pygame>=2.0.0` - Audio and media controls
- `mutagen>=1.45.0` - Audio metadata extraction
- `matplotlib>=3.5.0` - Advanced UI elements (optional)

**Windows Integration:**
- `winsdk>=1.0.0b9` - Windows Media Session API
- `pywin32>=300` - Windows API integration
- `pypiwin32>=223` - Additional Windows APIs
- `pystray>=0.19.0` - System tray functionality

---

## Method 1: Basic Installation

**Best for:** First-time users, testing, or simple setups

### Step 1: Install Python
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, **check "Add Python to PATH"**
3. Verify installation:
   ```cmd
   python --version
   pip --version
   ```

### Step 2: Download MotionSaver
```bash
# Option A: Git Clone (recommended)
git clone https://github.com/chinmay-sawant/MotionSaver.git
cd MotionSaver

# Option B: Download ZIP
# Download from GitHub and extract to desired folder
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: First Run
```bash
# Open settings GUI
python PhotoEngine.py --mode gui

# Or run screensaver directly
python PhotoEngine.py --mode saver
```

### Step 5: Basic Configuration
1. In the GUI, set your video file path
2. Configure user profile (optional)
3. Test the screensaver: `python PhotoEngine.py --mode saver`

---

## Method 2: Development Setup

**Best for:** Developers, contributors, or users who want isolated environments

### Step 1: Create Virtual Environment
```bash
# Navigate to project directory
cd MotionSaver

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows Command Prompt:
venv\Scripts\activate

# Windows PowerShell:
venv\Scripts\Activate.ps1

# Git Bash/Linux-style terminals:
source venv/Scripts/activate
```

### Step 2: Install Dependencies in Virtual Environment
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install additional development tools (optional)
pip install pytest black flake8
```

### Step 3: Development Configuration
```bash
# Set development environment variable (optional)
set MOTIONSAVER_DEV=1

# Run with debugging
python PhotoEngine.py --mode gui --debug
```

### Step 4: IDE Setup (Optional)
- **VS Code**: Install Python extension, configure interpreter to virtual environment
- **PyCharm**: Configure project interpreter to virtual environment
- **Other IDEs**: Point to `venv/Scripts/python.exe`

---

## Method 3: Windows Service Installation

**Best for:** Always-on kiosk systems, enterprise deployments, or automatic startup

### Prerequisites
- **Administrator privileges required**
- Complete basic installation first

### Step 1: Enable Admin Mode
```bash
# Run with admin privileges
python PhotoEngine.py --mode admin
```

### Step 2: Install Service via GUI
1. Open Settings GUI as Administrator
2. Navigate to "System Settings" section
3. Check "Enable Admin Mode"
4. Use service management buttons:
   - **Install Service**: Registers MotionSaver as Windows service
   - **Start Service**: Begins background operation
   - **Stop Service**: Halts service
   - **Uninstall Service**: Removes service registration

### Step 3: Manual Service Installation
```bash
# Install service manually
python screensaver_service.py install

# Start service
python screensaver_service.py start

# Check service status
sc query ScreenSaverService
```

### Step 4: Service Configuration
- Service runs under LocalSystem account by default
- Configuration file: `config/userconfig.json`
- Logs: Windows Event Viewer → Applications and Services

### Service Management Commands
```cmd
# Install
sc create ScreenSaverService binPath= "path\to\python.exe path\to\screensaver_service.py"

# Start
sc start ScreenSaverService

# Stop
sc stop ScreenSaverService

# Delete
sc delete ScreenSaverService
```

---

## Method 4: Portable Installation

**Best for:** USB deployment, temporary installations, or systems without admin rights

### Step 1: Portable Python Setup
1. Download Python portable from [python.org](https://www.python.org/downloads/windows/) or use WinPython
2. Extract to your portable drive/folder
3. Add portable Python to PATH temporarily

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
