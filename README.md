# Motion Saver Project

## From Dream to Reality: My AI-Accelerated Development Journey

### The Spark of Inspiration (2020-2021)

This journey began years ago when my Counter-Strike friend gifted me Wallpaper Engine back in 2020-21. I was absolutely mesmerized by how it brought desktops to life with dynamic, interactive wallpapers. I remember thinking, *"I need to create something like this someday"* - but at that time, I lacked both the experience and the right tools to make it happen.

Later, while using macOS, I was further inspired by its elegant live wallpapers and how seamlessly they integrated with the system. This reignited my desire to create a more engaging screen saver experience for Windows, which often felt dull in comparison. The idea stayed with me, waiting for the right moment and tools to come together.

### The AI Revolution: When Dreams Met Reality

Everything changed when I gained access to GitHub Copilot and advanced AI models. What I had dreamed about for years suddenly became achievable. This project represents a fascinating experiment in AI-assisted development - a testament to how modern AI tools can turn ambitious ideas into reality in record time.

**The Numbers That Still Amaze Me:**
- **Core Application (90%)**: Completed in just **10 hours** over the weekend of May 24th-25th, 2025
- **Security Implementation**: Additional **10 hours** of problem-solving and refinement
- **Total Development Time**: What would have taken me months or years was accomplished in **20 hours**

This is what I call "vibe coding" - when AI assistance flows so naturally that complex features emerge almost effortlessly, saving countless hours of traditional development struggle.

### My AI Development Arsenal

**GitHub Copilot Usage Pattern:**
- **Edit Mode (80%)**: Real-time code suggestions and intelligent autocomplete
- **Agent Mode (20%)**: Complex problem-solving and architecture decisions

**The AI Model Sequence I Relied On:**
1. **Claude Sonnet 4 / 3.5 Thinking / 3.5**: Primary logic implementation and complex problem solving
2. **Gemini 2.5 Pro Preview**: Core architecture design and algorithm development
3. **GPT 4.1**: Code refinement and optimization
4. **Gemini 2.0 Flash**: Code explanation and concept clarification

### The Security Challenge: A Deep Dive

The most challenging part wasn't the core screensaver functionality - that flowed beautifully with AI assistance. The real struggle came with implementing robust security features to prevent users from bypassing the screensaver.

**The Problem:**
I needed to block keyboard shortcuts (Alt+Tab, Ctrl+Alt+Del, Windows key, etc.) when the screensaver was active, essentially creating a kiosk-like experience. This required low-level Windows hooks - territory I had zero experience with.

**The Struggle:**
- Low-level Windows hooks proved difficult for AI models to generate correctly
- Code generation was inconsistent across all models, even Claude 4 Sonnet
- Traditional approaches weren't working reliably
- Kiosk mode wasn't suitable for my requirements

**The Breakthrough:**
Through extensive conversations with Gemini 2.5 Flash, I discovered a crucial insight: Alt+Tab (Task Switcher) is technically unblockable at the application level. However, the solution was elegantly simple - instead of fighting the system, work with it by calling `LockWorkStation()` (Windows API) when Ctrl+Alt+Del is detected.

This approach transformed the security implementation from a complex, unreliable hook system into a clean, Windows-native solution that actually enhances the user experience.

### Development Timeline: Weekend Sprint to Full Application

**Weekend Sprint (May 24th-25th, 2025) - 10 Hours:**
- Core video playback engine with OpenCV
- Basic UI elements (clock, user profiles)
- Password protection system
- Multi-monitor support
- Initial widget framework
- Weather and stock market widgets
- Media player integration
- Configuration GUI

**Security Deep-Dive - 10 Hours:**
- Enhanced key blocking research and implementation
- Windows API integration for `LockWorkStation()`
- Registry-based security controls
- Hook-based input interception
- Ctrl+Alt+Del detection and handling

**Total Achievement:** A fully-featured screensaver application some basic security, real-time widgets, and professional UI - all completed in just **20 hours** thanks to AI assistance.

### Personal Note

I created this application primarily for my personal use, born out of years of wanting something like Wallpaper Engine for screensavers. Feel free to use it if you find it useful! This project perfectly demonstrates how AI tools can democratize software development, allowing anyone with an idea to create sophisticated applications that would have required months or years of traditional development.

## Demo
[![MotionSaver Demo](http://img.youtube.com/vi/8JzlZ49vus4/0.jpg)](https://www.youtube.com/watch?v=8JzlZ49vus4)
[![MotionSaver Demo](http://img.youtube.com/vi/3UxKSrSMv0o/0.jpg)](https://www.youtube.com/watch?v=3UxKSrSMv0o)
## Features

### 🎥 Core Video Engine
- **Dynamic Video Backgrounds**: High-performance video playback with optimized rendering
- **Multi-format Support**: Compatible with MP4, AVI, MOV, and other common video formats
- **Performance Optimization**: Efficient frame processing with minimal CPU usage

### 🖥️ Display & UI
- **Multi-monitor Support**: Primary content on main monitor, secondary screens blackout
- **Customizable Digital Clock**: Adjustable fonts, sizes, colors, and positioning
- **Dark/Light Theme Support**: Seamless theme switching for better integration
- **User Profile Display**: Customizable profile pictures with cropping support
- **Transparent Overlays**: Clean, non-intrusive UI elements over video backgrounds

### 🔒 Security & Access Control
- **Advanced Key Blocking**: Enhanced security with registry and hook-based key blocking
- **Password Protection**: macOS-style elegant login dialog system
- **User Management**: Multi-user support with individual profiles and permissions
- **Admin Mode**: Elevated privileges for service management and system control
- **Enhanced Key Blocker**: Comprehensive protection against system interruptions

### 🔧 System Integration
- **Windows Service**: Run as background service with automatic startup
- **System Tray Mode**: Minimized operation with tray icon controls
- **Service Management**: Install, start, stop, and uninstall service capabilities
- **Auto-restart**: Intelligent recovery from system interruptions

### 📊 Real-time Widgets
- **Weather Widget**: 
  - Current conditions with weather icons
  - 2-day forecast display
  - Customizable location (pincode/country)
  - Auto-refresh every 30 minutes
  
- **Stock Market Widget**:
  - Real-time stock prices and changes
  - Support for NASDAQ, NYSE, NSE, BSE, and Crypto markets
  - Color-coded gains/losses
  - Automatic market data updates
  
- **Media Player Widget**:
  - Windows Media Session integration
  - Album art thumbnail display
  - Play/pause/next/previous controls
  - Browser media detection (Spotify, YouTube, etc.)
  - Cross-application media control

### ⚙️ Configuration & Customization
- **Comprehensive Settings GUI**: User-friendly configuration interface
- **Font Customization**: Clock and UI font selection with live previews
- **Widget Management**: Enable/disable individual widgets
- **Video Source Selection**: Easy video file selection and management
- **Profile Management**: Add, edit, and remove user profiles
- **Theme Switching**: Quick dark/light mode toggle

## Technology Stack

### 🐍 Core Technologies
- **Python 3.x**: Main development language
- **OpenCV (cv2)**: Video processing and playback engine
- **Tkinter**: Native GUI framework for settings and overlays
- **PIL/Pillow**: Image processing and manipulation

### 🎮 Media & Graphics
- **Pygame**: Audio handling and media controls
- **Mutagen**: Audio metadata extraction
- **NumPy**: Numerical operations for image processing
- **Screeninfo**: Multi-monitor detection and configuration

### 🖥️ Windows Integration
- **PyWin32**: Windows API integration and system services
- **WinSDK**: Windows Media Session API for media control
- **WinReg**: Windows Registry manipulation for security features

### 🔧 System Tools
- **PSUtil**: System process monitoring and resource management
- **Keyboard**: Global key hooking and blocking
- **PyStray**: System tray integration
- **Threading**: Asynchronous operations and background tasks

### 🌐 External APIs & Services
- **Open-Meteo API**: Weather data retrieval
- **Yahoo Finance API**: Stock market data (via web scraping)
- **Requests**: HTTP client for API communications
- **JSON**: Configuration and data storage

### 📦 Package Management
- **Requirements.txt**: Dependency management
- **Virtual Environment**: Isolated Python environment support

### 🏗️ Architecture Patterns
- **Multi-threading**: Non-blocking UI and background processing
- **Widget Architecture**: Modular, independent widget system
- **Service Architecture**: Windows service integration
- **Configuration Management**: JSON-based settings system

## Quick Start

For detailed installation instructions and all available methods, see **[INSTALLATION.md](INSTALLATION.md)**.

### Basic Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/chinmay-sawant/MotionSaver.git
   cd MotionSaver
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   # Settings GUI
   python PhotoEngine.py --mode gui
   
   # Screensaver mode
   python PhotoEngine.py --mode saver
   ```

## Usage

### Running Modes
- **Settings GUI**: `python PhotoEngine.py --mode gui` or `python gui.py`
- **Screensaver Mode**: `python PhotoEngine.py --mode saver`
- **System Tray Mode**: `python PhotoEngine.py --mode tray`
- **Admin Mode**: `python PhotoEngine.py --mode admin` (for service management)

### Key Features Usage
- **Screen Saver**: Press `Esc` to trigger password prompt
- **Widgets**: Configure via Settings GUI (enable/disable individual widgets)
- **Multi-monitor**: Automatic detection, primary content on main monitor
- **Service Mode**: Install via Settings GUI for automatic startup

## Contributing

Contributions are welcome! Feel free to fork the repository, make changes, and submit pull requests.

*   Report any issues or bugs you find.
*   Suggest new features or improvements.
*   Contribute code, documentation, or translations.

This project is maintained by [Chinmay Sawant](https://github.com/chinmay-sawant).
