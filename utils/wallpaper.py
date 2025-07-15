import logging  

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
