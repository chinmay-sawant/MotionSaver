import subprocess
import os
import sys
import ctypes

# Assuming central_logger is in a sibling directory or configured in PYTHONPATH
# from screensaver_app.central_logger import get_logger
# For standalone execution, we can create a dummy logger:
# Ensure parent directory is in sys.path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
from screensaver_app.central_logger import get_logger

logger = get_logger("ServiceReg")

class ServiceRegistrar:
    TASK_NAME = "PhotoEngineAdminTask"
    BATCH_FILE_NAME = "service_script_photoengine.bat"

    def __init__(self):
        self.app_dir = self.get_app_dir()
        self.batch_file_path = os.path.join(self.app_dir, self.BATCH_FILE_NAME)
        self.photoengine_exec = self.get_photoengine_exec()

    @staticmethod
    def get_app_dir():
        """
        Returns the directory where the main application (PhotoEngine.py/.exe) resides.
        Handles both PyInstaller and normal script execution.
        """
        if getattr(sys, 'frozen', False):
            # The application is frozen (packaged by PyInstaller)
            return os.path.dirname(sys.executable)
        else:
            # The application is running as a normal Python script
            return os.path.dirname(os.path.abspath(__file__))

    def get_photoengine_exec(self):
        """
        Returns the path to PhotoEngine.exe (PyInstaller) or PhotoEngine.py (source).
        """
        if getattr(sys, 'frozen', False):
            return os.path.join(self.app_dir, "PhotoEngine.exe")
        else:
            # To be more robust, find the python executable to run the script
            return os.path.join(self.app_dir, "PhotoEngine.py")

    def create_batch_file(self):
        """Creates the batch file if it doesn't exist."""
        # Use sys.executable to ensure we use the same python interpreter in the batch file
        # that is running this script, which is important in environments with multiple pythons.
        if self.photoengine_exec.endswith(".exe"):
            launch_cmd = f'"{self.photoengine_exec}" --min --no-elevate'
        else:
            launch_cmd = f'"{sys.executable}" "{self.photoengine_exec}" --min --no-elevate'
            
        batch_file_content = f"""
@echo off
rem Change directory to the location of this script
cd /d "%~dp0"
rem Start the application minimized using the correct executable
{launch_cmd}
"""
        # Use strip() to remove leading/trailing whitespace from the multiline string
        batch_file_content = '\n'.join([line.strip() for line in batch_file_content.strip().split('\n')])

        # Only write the file if content is different or file does not exist
        # to avoid unnecessary disk writes.
        should_write = True
        if os.path.exists(self.batch_file_path):
            with open(self.batch_file_path, "r") as f:
                if f.read() == batch_file_content:
                    should_write = False
                    
        if should_write:
            logger.info(f"Creating or updating batch file: {self.batch_file_path}")
            with open(self.batch_file_path, "w") as f:
                f.write(batch_file_content)
        else:
            logger.info(f"Batch file '{self.batch_file_path}' is already up to date.")


    @staticmethod
    def is_admin():
        """Checks if the script is running with administrative privileges."""
        try:
            # This works on Unix-like systems (Linux, macOS)
            return os.getuid() == 0
        except AttributeError:
            # This is the check for Windows
            return ctypes.windll.shell32.IsUserAnAdmin() != 0

    def setup_admin_task(self):
        """
        Creates a scheduled task that runs the batch file with highest privileges
        whenever any user unlocks the workstation.
        This function MUST be run from a terminal with Administrator rights.
        """
        logger.info("--- Attempting to create Scheduled Task ---")
        if not self.is_admin():
            logger.error("Error: This setup function must be run as an Administrator.")
            logger.error("Please re-run this script from an elevated Command Prompt or PowerShell.")
            sys.exit(1)

        # Command to create a task that triggers on workstation unlock.
        # /sc ONEVENT: Sets the trigger type to a system event.
        # /ec: Specifies the Event Channel.
        # /mo: Specifies the Event Query (XPath) to filter for the unlock event.
        # Event ID 25 in this channel corresponds to "Session Reconnected", which fires on unlock.
        command = [
            'schtasks', '/create',
            '/tn', self.TASK_NAME,
            '/tr', f'cmd /c start "" /min "{self.batch_file_path}"',
            '/sc', 'ONEVENT',
            '/ec', 'Security',
            '/mo', '*[System[(EventID=4624)]]',
            '/rl', 'HIGHEST',
            '/f'
        ]

        try:
            logger.info(f"Executing: {' '.join(command)}")
            # Pass command as a list for robustness (handles spaces in paths correctly)
            result = subprocess.run(command, check=True, capture_output=True, text=True, shell=False)
            logger.info(f"SUCCESS: Scheduled Task '{self.TASK_NAME}' created successfully.")
            logger.info("The task will now run whenever the computer is unlocked.")
            logger.info(f"Output: {result.stdout.strip()}")
        except FileNotFoundError:
            logger.error("ERROR: 'schtasks.exe' not found. Is this a Windows system?")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            logger.error(f"ERROR: Failed to create scheduled task '{self.TASK_NAME}'.")
            logger.error(f"Return Code: {e.returncode}")
            logger.error(f"Output: {e.stdout.strip()}")
            logger.error(f"Error Output: {e.stderr.strip()}")
            sys.exit(1)

    def run_as_admin(self):
        """
        Runs the pre-configured scheduled task immediately.
        This does NOT require administrator privileges.
        """
        logger.info(f"--- Triggering Scheduled Task '{self.TASK_NAME}' to run as admin ---")
        command = ['schtasks', '/run', '/tn', self.TASK_NAME]
        try:
            # Popen is non-blocking, which is what we want here.
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"SUCCESS: Task '{self.TASK_NAME}' has been triggered.")
            logger.info("Your application (PhotoEngine) should now be starting.")
        except Exception as e:
            logger.error(f"ERROR: Failed to run scheduled task '{self.TASK_NAME}'.")
            logger.error("Have you run the 'setup' command from an admin terminal first?")
            logger.error(f"Details: {e}")
            sys.exit(1)

    def remove_admin_task(self):
        """
        Removes the scheduled task and deletes the batch file.
        This function MUST be run from a terminal with Administrator rights.
        """
        logger.info(f"--- Removing Scheduled Task '{self.TASK_NAME}' and batch file ---")
        if not self.is_admin():
            logger.error("Error: This remove function must be run as an Administrator.")
            logger.error("Please re-run this script from an elevated Command Prompt or PowerShell.")
            sys.exit(1)
            
        command = ['schtasks', '/delete', '/tn', self.TASK_NAME, '/f']
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"SUCCESS: Scheduled Task '{self.TASK_NAME}' deleted successfully.")
        except subprocess.CalledProcessError as e:
            # This is not a critical error if the task doesn't exist. Log as a warning.
            logger.warning(f"Could not delete scheduled task '{self.TASK_NAME}'. It may not exist.")
            logger.warning(f"Details: {e.stderr.strip()}")
            
        try:
            if os.path.exists(self.batch_file_path):
                os.remove(self.batch_file_path)
                logger.info(f"SUCCESS: Batch file '{self.batch_file_path}' deleted.")
            else:
                logger.info(f"Batch file '{self.batch_file_path}' did not exist, nothing to remove.")
        except Exception as e:
            logger.warning(f"Could not delete batch file '{self.batch_file_path}'. Details: {e}")

    @staticmethod
    def handle_service_args(args=None):
        """
        Handles setup/run/remove commands for service registration.
        Can be called from a main script as: ServiceRegistrar.handle_service_args()
        """
        if args is None:
            args = sys.argv[1:]
            
        if not args or len(args) > 1:
            return False

        cmd = args[0].lower()
        registrar = ServiceRegistrar()
        
        if cmd == 'setup':
            registrar.create_batch_file()
            registrar.setup_admin_task()
            return True
        elif cmd == 'run':
            registrar.run_as_admin()
            return True
        elif cmd == 'remove':
            registrar.remove_admin_task()
            return True
            
        return False

    def get_service_reg_usage(self):
        """
        Returns a string describing how to use the service registration via PhotoEngine.
        """
        exe = os.path.basename(sys.executable if not getattr(sys, 'frozen', False) else sys.executable)
        script_name = os.path.basename(self.photoengine_exec)
        run_command = f"{exe} {script_name}" if not getattr(sys, 'frozen', False) else exe

        return (
            "Service Registration Usage:\n\n"
            f"1. To set up the task (run ONCE as Administrator):\n"
            f"   {run_command} setup\n"
            "   (This creates a task that starts the app on workstation unlock)\n\n"
            f"2. To run the program immediately without a UAC prompt (run anytime):\n"
            f"   {run_command} run\n\n"
            f"3. To remove the scheduled task and batch file (run as Administrator):\n"
            f"   {run_command} remove"
        )


if __name__ == '__main__':
    # Example of how to integrate this into a main script
    registrar = ServiceRegistrar()
    
    # handle_service_args will return True if it handled a command like 'setup', 'run', or 'remove'
    if ServiceRegistrar.handle_service_args():
        # A service command was processed, so we can exit the script.
        sys.exit(0)
    
    # If no service command was given, print the usage instructions.
    print(registrar.get_service_reg_usage())
    print("\nNo valid command provided. Proceeding with normal application logic (if any)...")
    # ... your main application logic would go here ...