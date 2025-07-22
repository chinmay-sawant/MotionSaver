
import os 
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
import atexit
import sys
import signal


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
    is_another_instance_running()
    """
    Tries to acquire a lock by creating a lock file.
    Returns True if the lock was acquired, False otherwise.
    """
    try:
        _lock_file_handle = open(LOCK_FILE_PATH, 'x')
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush() # Ensure it's written immediately
        atexit.register(release_lock)
        logger.info(f"Lock acquired with PID {os.getpid()}: {LOCK_FILE_PATH}")
        return True
    except FileExistsError:
        logger.warning(f"Lock file '{LOCK_FILE_PATH}' already exists. Another instance may be running.")
        return False

def is_another_instance_running():
    """
    Checks if another instance is running by reading the PID from the lock file
    and checking if that process exists.
    Returns True if another instance is running, False otherwise.
    """
    if not os.path.exists(LOCK_FILE_PATH):
        return False
    try:
        global _lock_file_handle
        if _lock_file_handle is None:
            _lock_file_handle = open(LOCK_FILE_PATH, 'r+')
        try:
            _lock_file_handle.seek(0)
            pid_str = _lock_file_handle.read().strip()
            if not pid_str.isdigit():
                return False  # Invalid PID in lock file
            pid = int(pid_str)
            if pid == os.getpid():
                return False  # Current process holds the lock
            else:
                _lock_file_handle.close()
                _lock_file_handle = None
                os.remove(LOCK_FILE_PATH)  # Remove stale lock file
                return True
        except Exception:
            return False
    except Exception as e:
        release_lock()
        logger.error(f"Error checking lock file: {e}")
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

def handle_exit_signal(signum, frame):
    logger.info(f"Received signal {signum}. Releasing lock and exiting.")
    release_lock()
    sys.exit(0)

            