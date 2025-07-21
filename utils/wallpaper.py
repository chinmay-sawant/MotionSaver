import logging  
import os 
import sys
logger = logging.getLogger("utils.Wallpaper")

def set_windows_wallpaper(image_path):
    """Set the Windows desktop wallpaper to the given image."""
    import platform
    if platform.system() == "Windows":
        try:
            import ctypes
            # Ensure image_path is a string, not a PIL Image object
            if hasattr(image_path, 'save'):  # Check if it's a PIL Image
                logger.error("Cannot set wallpaper: received PIL Image object instead of file path")
                return False
            
            # Convert to string and ensure it's a proper file path
            image_path_str = str(image_path)
            
            SPI_SETDESKWALLPAPER = 20
            # Use ctypes.c_wchar_p to properly convert string to LPCWSTR
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 
                0, 
                ctypes.c_wchar_p(image_path_str), 
                3
            )
            logger.info(f"Setting wallpaper to: {image_path_str}")
            if not result:
                logger.error("Failed to set wallpaper using SystemParametersInfoW.")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to set wallpaper: {e}")
            logger.error("Image Path was: " + str(image_path))
            return False
    return False




def capture_image_from_player(player):
    """
    Captures a snapshot from the given VLC player instance and sets it as the Windows wallpaper.
    Returns True if successful, False otherwise.
    """
    # Determine project root for snapshot path
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.abspath(os.path.dirname(__file__))
    snapshot_path = os.path.join(project_root, "vlc_snapshot_temp.png")

    logger.info(f"Attempting to take snapshot to: {snapshot_path}")
    player.video_take_snapshot(0, snapshot_path, 0, 0)
    logger.info("Snapshot command issued. Waiting for file to be written...")

    if os.path.exists(snapshot_path):
        try:
            success = set_windows_wallpaper(snapshot_path)
            if success:
                logger.info("Successfully set snapshot as wallpaper")
            else:
                logger.error("Failed to set snapshot as wallpaper")
            return success
        except Exception as e:
            logger.error(f"Error setting snapshot as wallpaper: {e}")
            return False
    else:
        logger.warning("Snapshot file was not found after taking snapshot. There might be an issue with VLC or permissions.")
        return False