import os
import sys

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
