import subprocess
import os
import sys

# --- CONFIGURATION ---
TASK_NAME = "MyPhotoEngineAdminTask"
BATCH_FILE_NAME = "start_photoengine.bat"

def get_app_dir():
    """
    Returns the directory where the main application (PhotoEngine.py/.exe) resides.
    Handles both PyInstaller and normal script execution.
    """
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        # Running from source
        return os.path.dirname(os.path.abspath(__file__))

def get_batch_file_path():
    return os.path.join(get_app_dir(), BATCH_FILE_NAME)

def get_photoengine_exec():
    """
    Returns the path to PhotoEngine.exe (PyInstaller) or PhotoEngine.py (source).
    """
    app_dir = get_app_dir()
    if getattr(sys, 'frozen', False):
        return os.path.join(app_dir, "PhotoEngine.exe")
    else:
        return os.path.join(app_dir, "PhotoEngine.py")

def create_batch_file():
    """Creates the batch file if it doesn't exist."""
    batch_file_path = get_batch_file_path()
    photoengine_exec = get_photoengine_exec()
    # Use .exe or .py accordingly
    if photoengine_exec.endswith(".exe"):
        launch_cmd = f'start "" "{photoengine_exec}" --min'
    else:
        # Use python to launch the script
        launch_cmd = f'start "" python "{photoengine_exec}" --min'
    batch_file_content = f"""
@echo off
cd /d "%~dp0"
rem Start the application minimized
{launch_cmd}
"""
    if not os.path.exists(batch_file_path):
        print(f"Creating batch file: {batch_file_path}")
        with open(batch_file_path, "w") as f:
            f.write(batch_file_content)

def is_admin():
    """Checks if the script is running with administrative privileges."""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def setup_admin_task():
    """
    Creates a scheduled task that can run the batch file with the highest privileges.
    This function MUST be run from a terminal with Administrator rights.
    """
    print("--- Attempting to create Scheduled Task ---")
    if not is_admin():
        print("Error: This setup function must be run as an Administrator.")
        print("Please re-run this script from an elevated Command Prompt or PowerShell.")
        sys.exit(1)

    batch_file_path = get_batch_file_path()
    command = [
        'schtasks', '/create',
        '/tn', TASK_NAME,
        '/tr', f'"{batch_file_path}"',
        '/sc', 'ONLOGON',
        '/rl', 'HIGHEST',
        '/f'
    ]

    try:
        print(f"Executing: {' '.join(command)}")
        subprocess.run(' '.join(command), check=True, capture_output=True, text=True)
        print(f"SUCCESS: Scheduled Task '{TASK_NAME}' created successfully.")
        print("You can now run this script with the 'run' argument from any user account.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create scheduled task '{TASK_NAME}'.")
        print(f"Return Code: {e.returncode}")
        print(f"Output: {e.stdout}")
        print(f"Error Output: {e.stderr}")
        sys.exit(1)

def run_as_admin():
    """
    Runs the pre-configured scheduled task.
    This does NOT require administrator privileges.
    """
    print(f"--- Triggering Scheduled Task '{TASK_NAME}' to run as admin ---")
    command = ['schtasks', '/run', '/tn', TASK_NAME]
    try:
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"SUCCESS: Task '{TASK_NAME}' has been triggered.")
        print("Your application (PhotoEngine) should now be starting.")
    except Exception as e:
        print(f"ERROR: Failed to run scheduled task '{TASK_NAME}'.")
        print("Have you run the 'setup' command from an admin terminal first?")
        print(f"Details: {e}")
        sys.exit(1)

def remove_admin_task():
    """
    Removes the scheduled task and deletes the batch file.
    This function MUST be run from a terminal with Administrator rights.
    """
    print(f"--- Removing Scheduled Task '{TASK_NAME}' and batch file ---")
    if not is_admin():
        print("Error: This remove function must be run as an Administrator.")
        print("Please re-run this script from an elevated Command Prompt or PowerShell.")
        sys.exit(1)
    command = ['schtasks', '/delete', '/tn', TASK_NAME, '/f']
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"SUCCESS: Scheduled Task '{TASK_NAME}' deleted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not delete scheduled task '{TASK_NAME}'. It may not exist.")
        print(f"Return Code: {e.returncode}")
        print(f"Output: {e.stdout}")
        print(f"Error Output: {e.stderr}")
    batch_file_path = get_batch_file_path()
    try:
        if os.path.exists(batch_file_path):
            os.remove(batch_file_path)
            print(f"SUCCESS: Batch file '{batch_file_path}' deleted.")
        else:
            print(f"Batch file '{batch_file_path}' does not exist.")
    except Exception as e:
        print(f"WARNING: Could not delete batch file '{batch_file_path}'. Details: {e}")

def handle_service_args(args=None):
    """
    Handles setup/run/remove commands for service registration.
    Can be called from PhotoEngine.py as: handle_service_args(sys.argv[1:])
    """
    if args is None:
        args = sys.argv[1:]
    if len(args) == 1:
        cmd = args[0].lower()
        if cmd == 'setup':
            create_batch_file()
            setup_admin_task()
            return True
        elif cmd == 'run':
            run_as_admin()
            return True
        elif cmd == 'remove':
            remove_admin_task()
            return True
    return False

def get_service_reg_usage():
    """
    Returns a string describing how to use the service registration via PhotoEngine.
    """
    exe = os.path.basename(get_photoengine_exec())
    return (
        "Usage:\n"
        f"1. To set up the task (run ONCE as Administrator):\n"
        f"   {exe} setup\n"
        "\n2. To run the program without a UAC prompt (run anytime):\n"
        f"   {exe} run\n"
        "\n3. To remove the scheduled task and batch file (run as Administrator):\n"
        f"   {exe} remove"
    )

# No direct CLI handling here; call handle_service_args() from PhotoEngine.py