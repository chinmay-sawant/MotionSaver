
import os 
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
import atexit
import sys


logger = get_logger("app_utils")


# We create the lock file in the system's temporary directory.
# This is a good, standard location.
# The file name should be unique to your application.
if getattr(sys, 'frozen', False):
    # If running as a PyInstaller bundle, use the executable's directory
    base_path = os.path.dirname(sys.executable)
else:
    # If running as a script, use the script's directory
    base_path = os.path.dirname(os.path.abspath(__file__))

LOCK_FILE_PATH = os.path.join(base_path, 'PhotoEngine.app.lock')

# We need to keep a reference to the file handle.
_lock_file_handle = None

def acquire_lock():
    """
    Tries to acquire a lock by creating a lock file.
    Returns True if the lock was acquired, False otherwise.
    """
    global _lock_file_handle
    try:
        _lock_file_handle = open(LOCK_FILE_PATH, 'x')
        _lock_file_handle.write(str(os.getpid()))
        atexit.register(release_lock)
        logger.info(f"Lock acquired. Lock file created at '{LOCK_FILE_PATH}'.")
        return True
    except FileExistsError:
        logger.warning(f"Lock file '{LOCK_FILE_PATH}' already exists. Another instance may be running.")
        return False

def release_lock():
    """
    Releases the lock by closing and deleting the lock file.
    This function is registered with atexit to be called on shutdown.
    """
    global _lock_file_handle
    if _lock_file_handle:
        _lock_file_handle.close()
        try:
            os.remove(LOCK_FILE_PATH)
            logger.info("Lock file released and removed.")
        except OSError as e:
            logger.error(f"Error removing lock file: {e}")

# --- YOUR APPLICATION'S MAIN LOGIC ---
