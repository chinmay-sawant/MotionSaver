import os
import sys
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "User" # Default for creating a new config if none exists
import hashlib
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('config_utils')
import json 

def find_user_config_path():
    """
    Locate userconfig.json by searching up from the executable/script location.
    Supports both frozen (PyInstaller) and non-frozen modes.
    Returns the absolute path to userconfig.json, or a default path if not found.
    """
    # Determine the starting directory
    if getattr(sys, 'frozen', False):
        start_dir = os.path.dirname(sys.executable)
    else:
        start_dir = os.path.dirname(os.path.abspath(__file__))

    # Search up to root for config/userconfig.json
    current_dir = start_dir
    while True:
        config_path = os.path.join(current_dir, 'config', 'userconfig.json')
        if os.path.exists(config_path):
            return config_path
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    # Default to start_dir/config/userconfig.json
    return os.path.join(start_dir, 'config', 'userconfig.json')


def load_config():
    """Load configuration from userconfig.json"""
    config_path = find_user_config_path()
    
    # Enhanced default configuration with GPU settings
    default_config = {
        "users": [
            {"username": DEFAULT_USERNAME, "password_hash": hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()}
        ],
        "default_user_for_display": DEFAULT_USERNAME,
        "profile_pic_path": "",
        "profile_pic_path_crop": "",  # Add crop path with empty default
        "video_path": "video.mp4",
        "theme": "light",
        "clock_font_family": "Segoe UI Emoji",
        "clock_font_size": 64,
        "ui_font_family": "Arial",
        "ui_font_size": 18,
        "preferred_gpu": "auto",
        "gpu_acceleration": True,
        "video_backend": "auto"
    }
    
    if not os.path.exists(config_path):
        save_config(default_config)
        return default_config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # Ensure essential keys exist with defaults
            if "users" not in config or not isinstance(config["users"], list) or not config["users"]:
                config["users"] = [{"username": DEFAULT_USERNAME, "password_hash": hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()}]
            if "default_user_for_display" not in config:
                config["default_user_for_display"] = config["users"][0].get("username", DEFAULT_USERNAME)
            if "profile_pic_path" not in config: config["profile_pic_path"] = ""
            if "profile_pic_path_crop" not in config: config["profile_pic_path_crop"] = config.get("profile_pic_path", "")
            if "video_path" not in config: config["video_path"] = "video.mp4"
            if "theme" not in config: config["theme"] = "light"
            if "clock_font_family" not in config: config["clock_font_family"] = "Segoe UI Emoji"
            if "clock_font_size" not in config: config["clock_font_size"] = 64
            if "ui_font_family" not in config: config["ui_font_family"] = "Arial"
            if "ui_font_size" not in config: config["ui_font_size"] = 18
            # New GPU-related keys
            if "preferred_gpu" not in config: config["preferred_gpu"] = "auto"
            if "gpu_acceleration" not in config: config["gpu_acceleration"] = True
            if "video_backend" not in config: config["video_backend"] = "auto"
            return config    
    except Exception as e:
        logger.error(f"Error loading user config: {e}, returning hardcoded defaults.")
        return default_config # Hardcoded fallback

def save_config(config_data):
    """Save entire configuration data to userconfig.json (using unified search logic)"""
    config_path = find_user_config_path()
    config_dir = os.path.dirname(config_path)
    try:
        # Ensure the config directory exists
        os.makedirs(config_dir, exist_ok=True)
        # Attempt to write to the file
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        # Verify by trying to read it back (optional, but good for diagnostics)
        try:
            with open(config_path, 'r') as f:
                json.load(f)
        except Exception as e_readback:
            logger.critical(f"CRITICAL ERROR: Config saved to {config_path}, but failed to read back immediately: {e_readback}")
            logger.critical(f"This could indicate a problem with file corruption or very intermittent write issues.")
        return True
    except IOError as e_io:
        logger.error(f"IOError saving user config to {config_path}: {e_io}")
        logger.error(f"Please check file permissions and path.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving user config to {config_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

