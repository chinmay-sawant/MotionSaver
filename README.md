# Video Screen Saver Project

## My Inspiration

I've always been fascinated by how applications like Wallpaper Engine bring desktops to life. I wanted something similar for screen savers – a way to use dynamic videos instead of static images or basic animations. Unfortunately, I couldn't find an existing application that quite matched what I envisioned.

Later, while using macOS, I was inspired by its live wallpapers and the elegant way they integrated with the system. This reignited my desire to create a more engaging screen saver experience for Windows, which often felt a bit dull in comparison.

Luckily, I got access to GitHub Copilot, and that's when this project truly began. With its help, I started coding this application from scratch. I'm proud to say that a significant portion of this application, around 80%, was developed in approximately 10-15 hours. GitHub Copilot was instrumental in this, and I also leveraged powerful AI models like Gemini 2.5 Pro and Claude Sonnet 4 for assistance with core logic, while other models helped with minor bug fixes and refinements.

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

## Installation

### Prerequisites

*   Python 3.x
*   pip (Python package installer)
*   (Windows Specific) Windows SDK components if not already available for media control features. The application will attempt to guide you if `winsdk` is missing.

### Steps

1.  **Clone the repository (or download the source code):**
    ```bash
   git clone https://github.com/chinmay-sawant/MotionSaver.git  
   cd MotionSaver
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    Activate it:
    *   Windows: `.\venv\Scripts\activate`
    *   macOS/Linux: `source venv/bin/activate`

3.  **Install dependencies:**
    A `requirements.txt` file would typically be here. For now, you'll need to install the packages mentioned in the import statements of the Python files. Key packages include:
    *   `tkinter` (usually comes with Python)
    *   `Pillow` (PIL)
    *   `pygame`
    *   `mutagen`
    *   `winsdk` (for Windows media controls)
    *   `pywin32` (for Windows service management and media keys)

    You can install them using pip:
    ```bash
    pip install Pillow pygame mutagen winsdk pywin32
    ```
    *(Note: A comprehensive `requirements.txt` should be generated for easier installation.)*

4.  **Configuration:**
    *   The application uses a `config/userconfig.json` file for settings. It will be created with defaults on the first run of the GUI or screen saver if it doesn't exist.
    *   Place any video files you want to use for the screen saver in an accessible location.
    *   Icons for the GUI (add user, change password, Copilot logo) should be placed in `screensaver_app/icons/`.

5.  **Running the Application:**

    *   **To run the screen saver:**
        ```bash
        python PhotoEngine.py --mode saver
        ```

    *   **To open the settings GUI:**
        ```bash
        python PhotoEngine.py --mode gui
        ```
        Alternatively, you can run the GUI directly:
        ```bash
        python gui.py
        ```

      6.  **(Windows Only - Planned Feature) Installing as a Service:**
         *This feature is under development.* The GUI *will* provide options to install, start, stop, and uninstall the screen saver as a Windows service. This *will* allow it to run automatically. Administrative privileges *will* be required for these operations.

## Usage

*   **Screen Saver Mode:** Once running, the screen saver will display the configured video with an overlay clock and user profile picture. Press `Esc` to bring up the password prompt.
*   **GUI Mode:** Use the settings application to configure video paths, profile pictures, fonts, themes, widget visibility, and manage users.

## Contributing

Contributions are welcome! Feel free to fork the repository, make changes, and submit pull requests.

*   Report any issues or bugs you find.
*   Suggest new features or improvements.
*   Contribute code, documentation, or translations.

This project is maintained by [Chinmay Sawant](https://github.com/chinmay-sawant).
## License

*(License information for the project will be added here. e.g., MIT, GPL, etc.)*
## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
