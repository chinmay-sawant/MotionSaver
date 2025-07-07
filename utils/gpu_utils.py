import platform
import subprocess
import logging
import os

logger = logging.getLogger('GPUUtils')

class GPUManager:
    """Manages GPU detection and selection for optimal video performance"""
    
    def __init__(self):
        self.available_gpus = []
        self.preferred_gpu = None
        self.detect_gpus()
    
    def detect_gpus(self):
        """Detect available GPUs and classify them by type"""
        self.available_gpus = []
        
        if platform.system() == "Windows":
            self._detect_windows_gpus()
        elif platform.system() == "Linux":
            self._detect_linux_gpus()
        elif platform.system() == "Darwin":  # macOS
            self._detect_macos_gpus()
        
        self._select_preferred_gpu()
        logger.info(f"Detected {len(self.available_gpus)} GPUs. Preferred: {self.preferred_gpu}")
    
    def _detect_windows_gpus(self):
        """Detect GPUs on Windows using wmic"""
        try:
            # Use wmic to get GPU information
            result = subprocess.run([
                'wmic', 'path', 'win32_VideoController', 'get', 
                'name,AdapterRAM,DriverVersion', '/format:csv'
            ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 4:
                        name = parts[2].strip()
                        ram = parts[1].strip()
                        
                        if name and name.lower() != "name":
                            gpu_info = {
                                'name': name,
                                'memory': ram,
                                'type': self._classify_gpu_type(name),
                                'platform': 'windows'
                            }
                            self.available_gpus.append(gpu_info)
        except Exception as e:
            logger.warning(f"Failed to detect Windows GPUs: {e}")
            self._add_fallback_gpu()
    
    def _detect_linux_gpus(self):
        """Detect GPUs on Linux using lspci"""
        try:
            result = subprocess.run(['lspci', '-nn'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'VGA compatible controller' in line or '3D controller' in line:
                    # Extract GPU name
                    parts = line.split(': ')
                    if len(parts) > 1:
                        name = parts[1].split(' [')[0].strip()
                        gpu_info = {
                            'name': name,
                            'memory': 'Unknown',
                            'type': self._classify_gpu_type(name),
                            'platform': 'linux'
                        }
                        self.available_gpus.append(gpu_info)
        except Exception as e:
            logger.warning(f"Failed to detect Linux GPUs: {e}")
            self._add_fallback_gpu()
    
    def _detect_macos_gpus(self):
        """Detect GPUs on macOS using system_profiler"""
        try:
            result = subprocess.run([
                'system_profiler', 'SPDisplaysDataType', '-json'
            ], capture_output=True, text=True)
            
            import json
            data = json.loads(result.stdout)
            
            displays = data.get('SPDisplaysDataType', [])
            for display in displays:
                name = display.get('sppci_model', 'Unknown GPU')
                vram = display.get('spdisplays_vram', 'Unknown')
                
                gpu_info = {
                    'name': name,
                    'memory': vram,
                    'type': self._classify_gpu_type(name),
                    'platform': 'macos'
                }
                self.available_gpus.append(gpu_info)
        except Exception as e:
            logger.warning(f"Failed to detect macOS GPUs: {e}")
            self._add_fallback_gpu()
    
    def _classify_gpu_type(self, gpu_name):
        """Classify GPU as dedicated, integrated, or unknown"""
        gpu_name_lower = gpu_name.lower()
        
        # Dedicated GPU indicators
        dedicated_indicators = [
            'nvidia', 'geforce', 'gtx', 'rtx', 'quadro', 'tesla',
            'amd', 'radeon', 'rx ', 'vega', 'fury', 'firepro',
            'intel arc', 'xe graphics'
        ]
        
        # Integrated GPU indicators
        integrated_indicators = [
            'intel hd', 'intel iris', 'intel uhd', 'intel graphics',
            'amd apu', 'vega graphics', 'radeon graphics',
            'apple m1', 'apple m2', 'integrated'
        ]
        
        # Check for dedicated first (higher priority)
        for indicator in dedicated_indicators:
            if indicator in gpu_name_lower:
                return 'dedicated'
        
        # Check for integrated
        for indicator in integrated_indicators:
            if indicator in gpu_name_lower:
                return 'integrated'
        
        return 'unknown'
    
    def _add_fallback_gpu(self):
        """Add a fallback GPU entry when detection fails"""
        self.available_gpus.append({
            'name': 'Default GPU',
            'memory': 'Unknown',
            'type': 'unknown',
            'platform': platform.system().lower()
        })
    
    def _select_preferred_gpu(self):
        """Select the preferred GPU based on priority: dedicated > unknown > integrated"""
        if not self.available_gpus:
            self.preferred_gpu = None
            return
        
        # Priority order: dedicated > unknown > integrated
        dedicated_gpus = [gpu for gpu in self.available_gpus if gpu['type'] == 'dedicated']
        unknown_gpus = [gpu for gpu in self.available_gpus if gpu['type'] == 'unknown']
        integrated_gpus = [gpu for gpu in self.available_gpus if gpu['type'] == 'integrated']
        
        if dedicated_gpus:
            self.preferred_gpu = dedicated_gpus[0]
            logger.info(f"Selected dedicated GPU: {self.preferred_gpu['name']}")
        elif unknown_gpus:
            self.preferred_gpu = unknown_gpus[0]
            logger.info(f"Selected unknown GPU: {self.preferred_gpu['name']}")
        elif integrated_gpus:
            self.preferred_gpu = integrated_gpus[0]
            logger.info(f"Selected integrated GPU: {self.preferred_gpu['name']}")
        else:
            self.preferred_gpu = self.available_gpus[0]
    
    def get_opencv_backend(self):
        """Get the best OpenCV backend for the selected GPU"""
        if not self.preferred_gpu:
            return None
        
        gpu_type = self.preferred_gpu['type']
        gpu_name = self.preferred_gpu['name'].lower()
        
        # Try to use GPU acceleration if available
        try:
            import cv2
            
            # NVIDIA GPUs - prefer CUDA
            if 'nvidia' in gpu_name or 'geforce' in gpu_name:
                if hasattr(cv2, 'CAP_FFMPEG'):
                    return cv2.CAP_FFMPEG
            
            # AMD GPUs - prefer DirectShow on Windows
            elif 'amd' in gpu_name or 'radeon' in gpu_name:
                if platform.system() == "Windows" and hasattr(cv2, 'CAP_DSHOW'):
                    return cv2.CAP_DSHOW
            
            # Default to system optimal
            return cv2.CAP_ANY
            
        except ImportError:
            return None
    
    def get_available_gpus(self):
        """Return the list of available GPUs"""
        return self.available_gpus

    def get_gpu_info(self):
        """Get formatted GPU information"""
        return {
            'available_gpus': self.available_gpus,
            'preferred_gpu': self.preferred_gpu,
            'total_count': len(self.available_gpus)
        }
    
    def set_environment_variables(self):
        """Set environment variables to prefer dedicated GPU"""
        if not self.preferred_gpu:
            return
        
        gpu_name = self.preferred_gpu['name'].lower()
        
        # NVIDIA GPU optimizations
        if 'nvidia' in gpu_name:
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first NVIDIA GPU
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'hwaccel;auto'
        
        # AMD GPU optimizations
        elif 'amd' in gpu_name or 'radeon' in gpu_name:
            os.environ['OPENCV_VIDEOIO_PRIORITY_DSHOW'] = '1'
        
        # General optimizations
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '1'  # Windows Media Foundation
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'hwaccel;auto'

# Global GPU manager instance
gpu_manager = GPUManager()

def get_gpu_manager():
    """Get the global GPU manager instance"""
    return gpu_manager

def get_preferred_opencv_backend():
    """Get the preferred OpenCV backend for video processing"""
    return gpu_manager.get_opencv_backend()

def setup_gpu_environment():
    """Setup environment for optimal GPU usage"""
    gpu_manager.set_environment_variables()
