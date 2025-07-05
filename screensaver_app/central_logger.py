"""
Central Logging Module for PhotoEngine Screensaver Application

This module provides a centralized logging configuration that can be used
across all modules in the application. It ensures consistent logging format,
level control, and output handling.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

class CentralLogger:
    """Central logging configuration for the PhotoEngine application."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CentralLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            CentralLogger._initialized = True
    

    def _setup_logging(self):
        """Setup centralized logging configuration."""
        # Try to load logs_path from config if available, using unified config search
        logs_path = None
        try:
            import json
            from utils.config_utils import find_user_config_path
            config_path = find_user_config_path()
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logs_path = config.get('logs_path', None)
        except Exception:
            logs_path = None

        # Determine logs directory
        if logs_path and isinstance(logs_path, str) and logs_path.strip():
            self.logs_dir = os.path.abspath(logs_path)
        else:
            # Use executable location if frozen, else script location
            if getattr(sys, 'frozen', False):
                self.app_dir = os.path.dirname(sys.executable)
            else:
                self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.logs_dir = os.path.join(self.app_dir, 'logs')

        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir, exist_ok=True)

        # Define log file paths
        self.main_log_path = os.path.join(self.logs_dir, 'photoengine.log')
        self.error_log_path = os.path.join(self.logs_dir, 'photoengine_errors.log')
        self.service_log_path = os.path.join(self.logs_dir, 'service.log')
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Main log file handler (rotating)
        main_handler = RotatingFileHandler(
            self.main_log_path, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(main_handler)
        
        # Error log file handler (errors and critical only)
        error_handler = RotatingFileHandler(
            self.error_log_path,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
        
        # Console handler (only if not running as service)
        if not self._is_service_context():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(simple_formatter)
            root_logger.addHandler(console_handler)
        
        # Service-specific handler
        service_handler = RotatingFileHandler(
            self.service_log_path,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        service_handler.setLevel(logging.DEBUG)
        service_handler.setFormatter(detailed_formatter)
        
        # Add service handler to service logger
        service_logger = logging.getLogger('PhotoEngine.Service')
        service_logger.addHandler(service_handler)
        service_logger.propagate = False  # Don't propagate to root logger
        
        # Log initial setup
        logger = logging.getLogger('PhotoEngine.Central')
        logger.info("=== PhotoEngine Logging System Initialized ===")
        logger.info(f"Main log: {self.main_log_path}")
        logger.info(f"Error log: {self.error_log_path}")
        logger.info(f"Service log: {self.service_log_path}")
        logger.info(f"Console logging: {'Disabled (Service)' if self._is_service_context() else 'Enabled'}")
    
    def _is_service_context(self):
        """Determine if running in a service context."""
        # Check for service-specific indicators
        return (
            '--min' in sys.argv or 
            'service' in sys.argv[0].lower() or
            os.environ.get('RUNNING_AS_SERVICE', '').lower() == 'true'
        )
    
    def get_logger(self, name):
        """Get a logger with the specified name."""
        return logging.getLogger(f'PhotoEngine.{name}')
    
    def set_level(self, level):
        """Set the global logging level."""
        logging.getLogger().setLevel(level)
    
    def add_file_handler(self, name, filepath, level=logging.DEBUG):
        """Add a custom file handler for specific components."""
        logger = logging.getLogger(f'PhotoEngine.{name}')
        handler = RotatingFileHandler(
            filepath,
            maxBytes=5*1024*1024,   # 5MB
            backupCount=2,
            encoding='utf-8'
        )
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

# Global instance
_central_logger = None

def get_logger(name='Main'):
    """
    Get a logger instance for the specified component.
    
    Args:
        name (str): Component name (e.g., 'GUI', 'Service', 'KeyBlocker', etc.)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    global _central_logger
    if _central_logger is None:
        _central_logger = CentralLogger()
    return _central_logger.get_logger(name)

def setup_component_logger(component_name, additional_file=None):
    """
    Setup a logger for a specific component with optional additional file logging.
    
    Args:
        component_name (str): Name of the component
        additional_file (str, optional): Path to additional log file for this component
    
    Returns:
        logging.Logger: Configured logger instance
    """
    global _central_logger
    if _central_logger is None:
        _central_logger = CentralLogger()
    
    logger = _central_logger.get_logger(component_name)
    
    if additional_file:
        _central_logger.add_file_handler(component_name, additional_file)
    
    return logger

def log_startup(component_name, version=None):
    """Log component startup information."""
    logger = get_logger(component_name)
    logger.info(f"=== {component_name} Starting ===")
    if version:
        logger.info(f"Version: {version}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Working Directory: {os.getcwd()}")
    logger.info(f"Arguments: {sys.argv}")

def log_shutdown(component_name):
    """Log component shutdown information."""
    logger = get_logger(component_name)
    logger.info(f"=== {component_name} Shutting Down ===")

def log_exception(logger_name, exception, context=""):
    """Log an exception with full traceback."""
    logger = get_logger(logger_name)
    import traceback
    logger.error(f"Exception in {context}: {str(exception)}")
    logger.error(f"Traceback:\n{traceback.format_exc()}")

# Convenience function for backward compatibility
def setup_logging():
    """Initialize the central logging system (for backward compatibility)."""
    global _central_logger
    if _central_logger is None:
        _central_logger = CentralLogger()
    return get_logger('Main')
