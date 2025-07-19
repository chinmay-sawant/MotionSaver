import subprocess
import os
import sys
from screensaver_app.central_logger import get_logger
logger = get_logger('PhotoEngine')

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
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def get_photoengine_exec(self):
        """
        Returns the path to PhotoEngine.exe (PyInstaller) or PhotoEngine.py (source).
        """
        if getattr(sys, 'frozen', False):
            return os.path.join(self.app_dir, "PhotoEngine.exe")
        else:
            return os.path.join(self.app_dir, "PhotoEngine.py")

    def create_batch_file(self):
        """Creates the batch file if it doesn't exist."""
        if self.photoengine_exec.endswith(".exe"):
            launch_cmd = f'start "" "{self.photoengine_exec}" --min'
        else:
            launch_cmd = f'start "" python "{self.photoengine_exec}" --min'
        batch_file_content = f"""
        @echo off
        cd /d "%~dp0"
        rem Start the application minimized
        {launch_cmd}
        """
        
        if not os.path.exists(self.batch_file_path):
            logger.info(f"Creating batch file: {self.batch_file_path}")
            with open(self.batch_file_path, "w") as f:
                f.write(batch_file_content)

    @staticmethod
    def is_admin():
        """Checks if the script is running with administrative privileges."""
        try:
            return os.getuid() == 0
        except AttributeError:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0

    def setup_admin_task(self):
        """
        Creates a scheduled task that can run the batch file with the highest privileges.
        This function MUST be run from a terminal with Administrator rights.
        """
        logger.info("--- Attempting to create Scheduled Task ---")
        if not self.is_admin():
            logger.info("Error: This setup function must be run as an Administrator.")
            logger.info("Please re-run this script from an elevated Command Prompt or PowerShell.")
            sys.exit(1)

        command = [
            'schtasks', '/create',
            '/tn', self.TASK_NAME,
            '/tr', f'"{self.batch_file_path}"',
            '/sc', 'ONLOGON',
            '/rl', 'HIGHEST',
            '/f'
        ]

        try:
            logger.info(f"Executing: {' '.join(command)}")
            subprocess.run(' '.join(command), check=True, capture_output=True, text=True)
            logger.info(f"SUCCESS: Scheduled Task '{self.TASK_NAME}' created successfully.")
            logger.info("You can now run this script with the 'run' argument from any user account.")
        except subprocess.CalledProcessError as e:
            logger.info(f"ERROR: Failed to create scheduled task '{self.TASK_NAME}'.")
            logger.info(f"Return Code: {e.returncode}")
            logger.info(f"Output: {e.stdout}")
            logger.info(f"Error Output: {e.stderr}")
            sys.exit(1)

    def run_as_admin(self):
        """
        Runs the pre-configured scheduled task.
        This does NOT require administrator privileges.
        """
        logger.info(f"--- Triggering Scheduled Task '{self.TASK_NAME}' to run as admin ---")
        command = ['schtasks', '/run', '/tn', self.TASK_NAME]
        try:
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"SUCCESS: Task '{self.TASK_NAME}' has been triggered.")
            logger.info("Your application (PhotoEngine) should now be starting.")
        except Exception as e:
            logger.info(f"ERROR: Failed to run scheduled task '{self.TASK_NAME}'.")
            logger.info("Have you run the 'setup' command from an admin terminal first?")
            logger.info(f"Details: {e}")
            sys.exit(1)

    def remove_admin_task(self):
        """
        Removes the scheduled task and deletes the batch file.
        This function MUST be run from a terminal with Administrator rights.
        """
        logger.info(f"--- Removing Scheduled Task '{self.TASK_NAME}' and batch file ---")
        if not self.is_admin():
            logger.info("Error: This remove function must be run as an Administrator.")
            logger.info("Please re-run this script from an elevated Command Prompt or PowerShell.")
            sys.exit(1)
        command = ['schtasks', '/delete', '/tn', self.TASK_NAME, '/f']
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"SUCCESS: Scheduled Task '{self.TASK_NAME}' deleted successfully.")
        except subprocess.CalledProcessError as e:
            logger.info(f"WARNING: Could not delete scheduled task '{self.TASK_NAME}'. It may not exist.")
            logger.info(f"Return Code: {e.returncode}")
            logger.info(f"Output: {e.stdout}")
            logger.info(f"Error Output: {e.stderr}")
        try:
            if os.path.exists(self.batch_file_path):
                os.remove(self.batch_file_path)
                logger.info(f"SUCCESS: Batch file '{self.batch_file_path}' deleted.")
            else:
                logger.info(f"Batch file '{self.batch_file_path}' does not exist.")
        except Exception as e:
            logger.info(f"WARNING: Could not delete batch file '{self.batch_file_path}'. Details: {e}")

    @staticmethod
    def handle_service_args(args=None):
        """
        Handles setup/run/remove commands for service registration.
        Can be called from PhotoEngine.py as: ServiceRegistrar.handle_service_args(sys.argv[1:])
        """
        registrar = ServiceRegistrar()
        if args is None:
            args = sys.argv[1:]
        if len(args) == 1:
            cmd = args[0].lower()
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
        exe = os.path.basename(self.photoengine_exec)
        return (
            "Usage:\n"
            f"1. To set up the task (run ONCE as Administrator):\n"
            f"   {exe} setup\n"
            "\n2. To run the program without a UAC prompt (run anytime):\n"
            f"   {exe} run\n"
            "\n3. To remove the scheduled task and batch file (run as Administrator):\n"
            f"   {exe} remove"
        )