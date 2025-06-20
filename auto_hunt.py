"""
Auto Hunt System - Screen recognition for automated Pokemon encounters
"""
import cv2
import numpy as np
import time
import threading
import random
import os
from PIL import Image, ImageGrab
import win32gui
import win32con
import win32api
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime
import pytesseract

class AutoHuntEngine:
    """Main engine for automated Pokemon hunting with screen recognition"""
    
    def __init__(self, window_manager, input_manager):
        self.window_manager = window_manager
        self.input_manager = input_manager
        
        # State management
        self.is_hunting = False
        self.is_paused = False
        self.hunt_thread = None
        self.stop_flag = False
        
        # Screen recognition settings
        self.template_threshold = 0.8  # Confidence threshold for template matching
        self.screenshot_interval = 0.5  # How often to check screen (seconds)
        self.ocr_screenshot_interval = 0.5  # How often to take OCR screenshots (seconds)
        
        # Movement settings
        self.movement_duration = 0.5  # How long to hold movement keys
        self.movement_pause = 0.3     # Pause between movements
        
        # Templates for screen recognition (will be loaded from files)
        self.templates = {}
        self.current_direction = 'a'  # Start with 'a', will alternate with 'd'
        
        # Statistics
        self.encounters_found = 0
        self.hunt_start_time = None
        self.total_hunt_time = 0
        
        # Callbacks
        self.status_callback = None
        self.encounter_callback = None
        self.special_encounter_callback = None  # New callback for special encounters
        
        # Screenshot saving
        self.screenshot_counter = 0
        self.current_encounter_screenshots = []  # Track screenshots for current encounter
        self.debug_dir = "debug_screenshots"
        self.ensure_screenshot_directory()
        
        # Setup Tesseract path for OCR
        self._setup_tesseract()
        
        # Pokemon name detection and special encounter system
        self.normal_pokemon_list = [
            'sentret', 'pidgey', 'pidgeotto', 'hoppip', 'meowth', 
            'persian', 'psyduck','furret', 'slowpoke'
        ]
        self.special_encounters_found = 0
        self.shiny_encounters_found = 0
        self.horde_encounters_found = 0
        self.last_detected_pokemon = ""
        self.last_encounter_type = "normal"  # normal, special, shiny, horde
    
    def ensure_screenshot_directory(self):
        """Create screenshots directory if it doesn't exist"""
        import os
        self.screenshot_dir = "debug_screenshots"
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
            print(f"✓ Created debug screenshots directory: {self.screenshot_dir}")
    
    def _setup_tesseract(self):
        """Setup Tesseract OCR path for Windows"""
        import os
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
    
    def save_debug_screenshot(self, screenshot: np.ndarray, prefix: str = "debug") -> str:
        """Save screenshot for debugging purposes"""
        import os
        from datetime import datetime
        
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.screenshot_counter += 1
            filename = f"{prefix}_{timestamp}_{self.screenshot_counter:03d}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            # Convert OpenCV image back to PIL for saving
            screenshot_pil = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
            screenshot_pil.save(filepath)
            
            # Track this screenshot for potential cleanup
            self.current_encounter_screenshots.append(filepath)
            
            print(f"💾 Debug screenshot saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving debug screenshot: {e}")
            return ""
    
    def cleanup_encounter_screenshots(self):
        """Delete all debug screenshots to keep folder clean"""
        import os
        import glob
        
        deleted_count = 0
        
        # Delete all debug screenshots, not just current encounter ones
        patterns = [
            "debug_screenshots/battle_menu_test_*.png",
            "debug_screenshots/template_*.png", 
            "debug_screenshots/pp_hunt_*.png",
            "debug_screenshots/pokemon_names_*.png"
        ]
        
        for pattern in patterns:
            for filepath in glob.glob(pattern):
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        deleted_count += 1
                except Exception as e:
                    print(f"⚠ Could not delete {filepath}: {e}")
        
        # Also delete from current encounter list
        for filepath in self.current_encounter_screenshots:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_count += 1
            except Exception as e:
                print(f"⚠ Could not delete {filepath}: {e}")
        
        if deleted_count > 0:
            print(f"🗑️ Cleaned up {deleted_count} debug screenshots")
        
        # Clear the list for next encounter
        self.current_encounter_screenshots = []
        
    def load_templates(self, template_dir: str = "templates"):
        """Load template images for screen recognition"""
        import os
        
        # Clear existing templates
        self.templates = {}
        
        # Check if template directory exists
        if not os.path.exists(template_dir):
            print(f"❌ Template directory not found: {template_dir}")
            print(f"💡 Create the directory and add your battle menu PNG files")
            return
        
        # Load all PNG files from templates directory
        template_count = 0
        for filename in os.listdir(template_dir):
            if filename.lower().endswith('.png'):
                filepath = os.path.join(template_dir, filename)
                template = cv2.imread(filepath, cv2.IMREAD_COLOR)
                if template is not None:
                    # Use filename without extension as template name
                    template_name = os.path.splitext(filename)[0]
                    template_h, template_w = template.shape[:2]
                    
                    # Check if template size is reasonable for battle menu detection
                    if template_w > 1920 or template_h > 1080:
                        print(f"⚠ Skipping large template: {template_name} ({template_w}x{template_h}) - too large for battle menu")
                        continue
                    elif template_w < 50 or template_h < 20:
                        print(f"⚠ Skipping small template: {template_name} ({template_w}x{template_h}) - too small for battle menu")
                        continue
                    
                    self.templates[template_name] = template
                    template_count += 1
                    print(f"✓ Loaded template: {template_name} ({template_w}x{template_h})")
                else:
                    print(f"❌ Failed to load template: {filename}")
        
        if template_count == 0:
            print(f"⚠ No PNG templates found in {template_dir}")
            print(f"💡 Add your battle menu screenshots as PNG files to this folder")
        else:
            print(f"✅ Loaded {template_count} templates total")
            
        # Set a more reasonable threshold for template matching
        if template_count > 0:
            self.template_threshold = 0.7  # Lower threshold for better matching
    
    def capture_game_screen(self) -> Optional[np.ndarray]:
        """Capture screenshot of the game window center area (for movement detection)"""
        if not self.window_manager.is_game_running():
            return None
        
        try:
            # Get game window rectangle
            game_rect = self.window_manager.game_rect
            if not game_rect:
                return None
            
            # Calculate center area around player (3x3 grid)
            # Player is always centered, so we capture a small area around center
            # game_rect is a tuple: (left, top, right, bottom)
            left, top, right, bottom = game_rect
            window_width = right - left
            window_height = bottom - top
            
            center_x = left + window_width // 2
            center_y = top + window_height // 2
            
            # Define capture area size (adjust based on game tile size)
            # Typical PokeMMO tile is about 32x32 pixels, so 3x3 = ~96x96 pixels
            capture_size = 120  # A bit larger to ensure we catch the full 3x3 area
            half_size = capture_size // 2
            
            # Calculate capture bounds
            left = center_x - half_size
            top = center_y - half_size
            right = center_x + half_size
            bottom = center_y + half_size
            
            # Capture screenshot of center area only
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # Convert PIL image to OpenCV format
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            return screenshot_cv
            
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
    
    def capture_full_game_screen(self) -> Optional[np.ndarray]:
        """Capture screenshot of the entire game window (for battle menu detection)"""
        if not self.window_manager.is_game_running():
            print("❌ Game not running, cannot capture screen")
            return None
        
        try:
            # Get game window handle and rectangle
            game_hwnd = self.window_manager.game_hwnd
            game_rect = self.window_manager.game_rect
            
            if not game_hwnd or not game_rect:
                print("❌ Could not get game window handle or rectangle")
                return None
            
            # game_rect is a tuple: (left, top, right, bottom)
            left, top, right, bottom = game_rect
            
            print(f"🖼️ Capturing game window: ({left}, {top}) to ({right}, {bottom})")
            print(f"   Window size: {right-left}x{bottom-top} pixels")
            
            # Try direct window capture first (better for overlapped windows)
            screenshot = self.capture_window_content(game_hwnd)
            
            if screenshot is not None:
                return screenshot
            
            # Fallback to screen region capture
            print("🔄 Falling back to screen region capture...")
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # Convert PIL image to OpenCV format
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            print(f"✓ Screenshot captured: {screenshot_cv.shape[1]}x{screenshot_cv.shape[0]} pixels")
            return screenshot_cv
            
        except Exception as e:
            print(f"❌ Error capturing full game screen: {e}")
            return None
    
    def capture_full_screen(self) -> Optional[np.ndarray]:
        """Capture primary monitor screen for testing"""
        try:
            print("🖼️ Capturing primary monitor screen...")
            
            # Get primary monitor size
            import win32api
            screen_width = win32api.GetSystemMetrics(0)  # SM_CXSCREEN
            screen_height = win32api.GetSystemMetrics(1)  # SM_CYSCREEN
            
            print(f"   Primary monitor size: {screen_width}x{screen_height}")
            
            # Capture only primary monitor (0, 0, width, height)
            screenshot = ImageGrab.grab(bbox=(0, 0, screen_width, screen_height))
            
            # Convert PIL image to OpenCV format
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            print(f"✓ Primary screen captured: {screenshot_cv.shape[1]}x{screenshot_cv.shape[0]} pixels")
            return screenshot_cv
            
        except Exception as e:
            print(f"❌ Error capturing primary screen: {e}")
            return None
    
    def capture_window_content(self, hwnd) -> Optional[np.ndarray]:
        """Capture specific window content using Windows API"""
        try:
            import win32gui
            import win32ui
            import win32con
            from ctypes import windll
            
            # Get window rectangle
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x1, y1 = rect
            width = x1 - x
            height = y1 - y
            
            print(f"🖼️ Capturing window content: {width}x{height} at ({x}, {y})")
            
            # Get window device context
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # Copy window content
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT
            
            if result:
                # Convert to numpy array
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                
                import numpy as np
                screenshot = np.frombuffer(bmpstr, dtype='uint8')
                screenshot.shape = (height, width, 4)  # BGRA format
                
                # Convert BGRA to BGR
                screenshot = screenshot[:, :, :3]  # Remove alpha channel
                screenshot = screenshot[:, :, ::-1]  # BGR to RGB
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
                
                print(f"✓ Window content captured: {screenshot.shape[1]}x{screenshot.shape[0]} pixels")
                
                # Cleanup
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                
                return screenshot
            else:
                print("❌ PrintWindow failed, falling back to screen capture")
                # Fallback to screen capture of window area
                screenshot = ImageGrab.grab(bbox=(x, y, x1, y1))
                screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                return screenshot_cv
                
        except Exception as e:
            print(f"❌ Error capturing window content: {e}")
            return None
    
    def detect_template(self, screenshot: np.ndarray, template_name: str) -> Tuple[bool, Tuple[int, int]]:
        """Detect if a template is present in the screenshot"""
        if template_name not in self.templates:
            print(f"❌ Template '{template_name}' not loaded")
            return False, (0, 0)
        
        template = self.templates[template_name]
        print(f"🔍 Testing template '{template_name}' ({template.shape[1]}x{template.shape[0]})")
        
        # Check if template is smaller than screenshot (required for template matching)
        screenshot_h, screenshot_w = screenshot.shape[:2]
        template_h, template_w = template.shape[:2]
        
        if template_h > screenshot_h or template_w > screenshot_w:
            print(f"⚠ Template '{template_name}' ({template_w}x{template_h}) is larger than screenshot ({screenshot_w}x{screenshot_h}) - skipping")
            return False, (0, 0)
        
        # Save template for debugging
        self.save_debug_screenshot(template, f"template_{template_name}")
        
        try:
            # Perform template matching
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            print(f"   Template match confidence: {max_val:.3f} (threshold: {self.template_threshold})")
            
            # Check if match confidence is above threshold
            if max_val >= self.template_threshold:
                print(f"✅ Template '{template_name}' matched at ({max_loc[0]}, {max_loc[1]})")
                return True, max_loc
            
            print(f"❌ Template '{template_name}' match too low: {max_val:.3f} < {self.template_threshold}")
            return False, (0, 0)
            
        except Exception as e:
            print(f"❌ Error matching template '{template_name}': {e}")
            return False, (0, 0)
    
    def test_all_templates(self, screenshot: np.ndarray) -> bool:
        """Test all loaded templates against the screenshot"""
        print(f"🧪 Testing all {len(self.templates)} loaded templates...")
        
        any_match = False
        best_match = 0.0
        best_template = ""
        
        for template_name in self.templates.keys():
            matched, location = self.detect_template(screenshot, template_name)
            
            # Get the actual confidence score for debugging
            template = self.templates[template_name]
            try:
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > best_match:
                    best_match = max_val
                    best_template = template_name
                
                if matched:
                    any_match = True
                    print(f"✅ Template '{template_name}' matched! Confidence: {max_val:.3f}")
                else:
                    print(f"❌ Template '{template_name}' confidence too low: {max_val:.3f}")
                    
            except Exception as e:
                print(f"❌ Error testing template '{template_name}': {e}")
        
        if not any_match and best_template:
            print(f"💡 Best match was '{best_template}' with confidence {best_match:.3f}")
            print(f"💡 Consider lowering template threshold if this should match")
        
        return any_match
    
    def detect_battle_menu(self, screenshot: np.ndarray) -> bool:
        """Detect the 4-button battle menu using template matching (primary method)"""
        # Save debug screenshot first (only bottom area to avoid confusion)
        height, width = screenshot.shape[:2]
        bottom_area = screenshot[height//2:, :]  # Bottom half only
        screenshot_path = self.save_debug_screenshot(bottom_area, "battle_menu_test")
        print(f"🔍 Analyzing bottom area screenshot: {screenshot_path}")
        
        # Try template matching first (this is now the primary and most reliable method)
        if self.templates:
            print(f"🧪 Testing {len(self.templates)} loaded templates against bottom area...")
            if self.test_all_templates(bottom_area):
                print("✅ Battle menu detected via template matching!")
                return True
            else:
                print("❌ No template matches found in bottom area")
        else:
            print("⚠ No templates loaded - please load battle menu templates!")
            print("💡 Use 'Load Templates' button or place PNG files in templates/ folder")
            print("📁 Take screenshots of the battle menu and save them as PNG files")
        
        # No other detection methods - templates are required for accurate detection
        print("❌ No battle menu detected - templates are required for accurate detection")
        return False
    
    def detect_battle_menu_quick(self, screenshot: np.ndarray) -> bool:
        """Quick battle menu detection using template matching with loaded templates (bottom area only)"""
        # Focus on bottom area only to avoid confusion
        height, width = screenshot.shape[:2]
        bottom_area = screenshot[height//2:, :]  # Bottom half only
        
        # First try template matching if templates are loaded
        if self.templates:
            # Test all loaded templates against the bottom area
            for template_name, template in self.templates.items():
                try:
                    # Check if template is smaller than bottom area
                    bottom_h, bottom_w = bottom_area.shape[:2]
                    template_h, template_w = template.shape[:2]
                    
                    if template_h > bottom_h or template_w > bottom_w:
                        # Template is too large for bottom area, skip it
                        continue
                    
                    # Perform template matching on bottom area
                    result = cv2.matchTemplate(bottom_area, template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    # Use a lower threshold for quick detection (0.6 instead of 0.8)
                    if max_val >= 0.6:
                        return True
                        
                except Exception:
                    continue
        
        # If no templates loaded, provide helpful message (only occasionally to avoid spam)
        if not self.templates and hasattr(self, 'move_counter') and self.move_counter % 50 == 0:
            print("⚠ No templates loaded for quick detection - please load battle menu templates!")
            
        # If no templates or no matches, assume battle ended
        return False
    
    def detect_battle_menu_patterns_quick(self, screenshot: np.ndarray) -> bool:
        """Quick pattern detection without debug output - focused on center battle menu area"""
        try:
            # Convert to grayscale for pattern analysis
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape
            
            # Focus on center-bottom area where battle menu specifically appears
            # Same area as OCR detection for consistency
            menu_width = width // 2  # Half the screen width
            menu_height = height // 4  # Quarter of screen height
            left = width // 4  # Start at 1/4 from left
            top = height - menu_height - 50  # Bottom area with some margin
            
            # Crop to battle menu area
            battle_area = gray[top:top + menu_height, left:left + menu_width]
            
            # Look for rectangular button patterns with more specific criteria
            edges = cv2.Canny(battle_area, 50, 150)
            
            # Find contours (potential buttons)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Look for 4 specific buttons arranged in 2x2 grid (typical battle menu layout)
            battle_buttons = []
            for contour in contours:
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's roughly rectangular and has battle menu button size
                if len(approx) >= 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    # Battle menu buttons are typically larger and more specific
                    if 80 < w < 200 and 30 < h < 70:
                        battle_buttons.append((x, y, w, h))
            
            # Battle menu should have exactly 4 buttons in a 2x2 layout
            if len(battle_buttons) >= 4:
                # Check if buttons are arranged in a grid pattern
                # Sort by position to check layout
                battle_buttons.sort(key=lambda b: (b[1], b[0]))  # Sort by y, then x
                
                # If we have 4+ buttons in the battle menu area, it's likely a battle menu
                return True
            
            # Not enough buttons or wrong layout
            return False
            
        except Exception:
            pass
        
        return False
    
    def detect_battle_menu_patterns(self, screenshot: np.ndarray) -> bool:
        """Fallback method to detect battle menu using visual patterns"""
        print("🔍 Trying pattern detection as fallback...")
        
        try:
            # Convert to grayscale for pattern analysis
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape
            
            # Focus on bottom half where battle menu appears
            bottom_half = gray[height//2:, :]
            
            # Save grayscale bottom half for debugging
            self.save_debug_screenshot(cv2.cvtColor(bottom_half, cv2.COLOR_GRAY2BGR), "pattern_bottom_gray")
            
            # Look for rectangular button patterns
            # Battle menu buttons are typically rectangular with borders
            edges = cv2.Canny(bottom_half, 50, 150)
            
            # Save edge detection result for debugging
            self.save_debug_screenshot(cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), "pattern_edges")
            
            # Find contours (potential buttons)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            print(f"🔍 Found {len(contours)} contours in bottom half")
            
            # Count rectangular contours that could be buttons
            rectangular_contours = 0
            valid_buttons = []
            
            for i, contour in enumerate(contours):
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's roughly rectangular (4 corners) and has reasonable size
                if len(approx) >= 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    # Battle menu buttons are typically 80-200 pixels wide, 30-60 pixels tall
                    if 50 < w < 250 and 20 < h < 80:
                        rectangular_contours += 1
                        valid_buttons.append((x, y, w, h))
                        print(f"   Button {rectangular_contours}: {w}x{h} at ({x}, {y})")
            
            print(f"🔍 Found {rectangular_contours} potential button shapes")
            
            # If we found 3+ rectangular shapes, likely battle menu
            if rectangular_contours >= 3:
                print(f"✅ Battle menu detected via pattern analysis! Found {rectangular_contours} button-like shapes")
                return True
            
            # Additional check: look for consistent horizontal alignment (menu buttons are aligned)
            if rectangular_contours >= 2:
                print(f"🔍 Found {rectangular_contours} potential buttons, but need at least 3 for confirmation")
                # This could be enhanced to check if buttons are properly aligned
                # For now, we'll be conservative and require at least 3 shapes
            
        except Exception as e:
            print(f"⚠ Error in pattern detection: {e}")
        
        print("❌ Pattern detection failed - no battle menu found")
        return False

    def detect_encounter(self, screenshot: np.ndarray) -> bool:
        """Detect if a Pokemon encounter has occurred - text-based approach (legacy method)"""
        # Method 1: Look for encounter text using OCR (most reliable)
        if self.detect_encounter_text_ocr(screenshot):
            print("✓ Encounter detected via OCR text detection")
            return True
        
        # Method 2: Look for text patterns without OCR (backup)
        if self.detect_text_patterns(screenshot):
            print("✓ Encounter detected via text pattern detection")
            return True
        
        # Method 3: Fallback to brightness detection
        if self.detect_simple_encounter(screenshot):
            print("✓ Encounter detected via brightness change")
            return True
        
        return False
    
    def detect_black_screen_transition(self, screenshot: np.ndarray) -> bool:
        """Detect the black screen that appears before encounters"""
        try:
            # Convert to grayscale for brightness analysis
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Calculate average brightness of the entire screen
            avg_brightness = np.mean(gray)
            
            # Calculate how much of the screen is very dark (black/near-black)
            # Pixels with brightness < 30 are considered very dark
            dark_pixels = np.sum(gray < 30)
            total_pixels = gray.size
            dark_percentage = (dark_pixels / total_pixels) * 100
            
            # Store previous brightness for comparison
            if not hasattr(self, 'previous_brightness'):
                self.previous_brightness = avg_brightness
                self.previous_dark_percentage = dark_percentage
                return False
            
            # Check for sudden drop in brightness (transition to black screen)
            brightness_drop = self.previous_brightness - avg_brightness
            dark_increase = dark_percentage - self.previous_dark_percentage
            
            # Update previous values
            self.previous_brightness = avg_brightness
            self.previous_dark_percentage = dark_percentage
            
            # Encounter detected if:
            # 1. Screen is very dark (avg brightness < 25) AND high percentage of dark pixels (> 80%)
            # 2. OR significant brightness drop from previous frame (> 40) with dark increase (> 30%)
            if (avg_brightness < 25 and dark_percentage > 80) or (brightness_drop > 40 and dark_increase > 30):
                print(f"🌑 Black screen detected! Brightness: {avg_brightness:.1f}, Dark pixels: {dark_percentage:.1f}%")
                print(f"   Brightness drop: {brightness_drop:.1f}, Dark increase: {dark_increase:.1f}%")
                return True
                
        except Exception as e:
            print(f"Error in black screen detection: {e}")
        
        return False
    
    def detect_encounter_text_ocr(self, screenshot: np.ndarray) -> bool:
        """Detect encounter text using OCR"""
        try:
            import pytesseract
            from PIL import Image
            import os
            
            # Try to set Tesseract path for common Windows installations
            possible_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
                r'C:\tesseract\tesseract.exe'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    print(f"✓ Found Tesseract at: {path}")
                    break
            
            # Convert OpenCV image to PIL Image
            screenshot_rgb = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(screenshot_rgb)
            
            # Focus on center area where encounter text appears
            width, height = pil_image.size
            center_x = width // 2
            center_y = height // 2
            
            # Crop to center area (where encounter dialog appears)
            crop_width = int(width * 0.8)  # 80% of screen width
            crop_height = int(height * 0.6)  # 60% of screen height
            
            left = center_x - crop_width // 2
            top = center_y - crop_height // 2
            right = center_x + crop_width // 2
            bottom = center_y + crop_height // 2
            
            # Ensure bounds are valid
            left = max(0, left)
            top = max(0, top)
            right = min(width, right)
            bottom = min(height, bottom)
            
            cropped_image = pil_image.crop((left, top, right, bottom))
            
            # Convert to grayscale and enhance contrast for better OCR
            gray_image = cropped_image.convert('L')
            
            # Use OCR to extract text
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(gray_image, config=custom_config).strip()
            
            # Debug output every 20 frames
            if not hasattr(self, 'ocr_debug_counter'):
                self.ocr_debug_counter = 0
            self.ocr_debug_counter += 1
            
            if self.ocr_debug_counter % 20 == 0:
                print(f"🔍 OCR detected text: '{text[:50]}...' (length: {len(text)})")
            
            # Look for battle menu keywords (from your screenshot)
            battle_keywords = [
                'fight', 'bag', 'pokemon', 'run', 'escape from battle',
                'select your attack', 'switch current pokemon'
            ]
            
            # Look for encounter keywords
            encounter_keywords = [
                'wild', 'appeared', 'battle', 'encounter'
            ]
            
            text_lower = text.lower()
            
            # Check for battle menu (like in your screenshot)
            for keyword in battle_keywords:
                if keyword in text_lower:
                    print(f"🎉 Battle menu detected! Found keyword: '{keyword}' in text: '{text}'")
                    return True
            
            # Check for encounter text
            for keyword in encounter_keywords:
                if keyword in text_lower:
                    print(f"🎉 Encounter text detected! Found keyword: '{keyword}' in text: '{text}'")
                    return True
            
            # Also check for text length - battle screens have substantial text
            if len(text) > 15:  # If we detect significant text
                print(f"📝 Significant text detected: '{text}'")
                # Could be a battle, check for specific words
                if any(word in text_lower for word in ['fight', 'run', 'bag', 'pokemon']):
                    print(f"🎉 Battle confirmed by menu text!")
                    return True
                    
        except ImportError:
            print("⚠ pytesseract not installed - falling back to pattern detection")
        except Exception as e:
            print(f"Error in OCR detection: {e}")
        
        return False
    
    def detect_text_patterns(self, screenshot: np.ndarray) -> bool:
        """Detect text patterns without OCR - look for battle menu structures"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Focus on bottom area where battle menu appears (from your screenshot)
            height, width = gray.shape
            
            # Battle menu is in bottom portion of screen
            menu_region = gray[int(height * 0.6):, :]  # Bottom 40% of screen
            
            # Look for white/light text on dark background
            _, text_mask = cv2.threshold(menu_region, 150, 255, cv2.THRESH_BINARY)
            
            # Count white pixels (text pixels)
            white_pixels = cv2.countNonZero(text_mask)
            total_pixels = menu_region.size
            white_percentage = (white_pixels / total_pixels) * 100
            
            # Look for rectangular menu structures (like FIGHT, BAG, etc.)
            # Find contours that could be menu buttons
            contours, _ = cv2.findContours(text_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Count rectangular-ish contours (menu buttons)
            menu_buttons = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:  # Minimum size for a menu button
                    # Check if contour is roughly rectangular
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h if h > 0 else 0
                    if 0.5 < aspect_ratio < 4:  # Reasonable aspect ratio for buttons
                        menu_buttons += 1
            
            # Look for horizontal text lines (characteristic of menu text)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
            horizontal_lines = cv2.morphologyEx(text_mask, cv2.MORPH_OPEN, horizontal_kernel)
            text_line_pixels = cv2.countNonZero(horizontal_lines)
            
            # Debug output every 15 frames
            if not hasattr(self, 'pattern_debug_counter'):
                self.pattern_debug_counter = 0
            self.pattern_debug_counter += 1
            
            if self.pattern_debug_counter % 15 == 0:
                print(f"🔍 Battle pattern - White: {white_percentage:.1f}%, Buttons: {menu_buttons}, Lines: {text_line_pixels}")
            
            # Battle detected if we have:
            # 1. Significant white text (menu text)
            # 2. Multiple button-like structures (FIGHT, BAG, etc.)
            # 3. Horizontal text lines
            if white_percentage > 5 and menu_buttons >= 2 and text_line_pixels > 100:
                print(f"⚔️ Battle menu pattern detected! White: {white_percentage:.1f}%, Buttons: {menu_buttons}, Lines: {text_line_pixels}")
                return True
                
        except Exception as e:
            print(f"Error in text pattern detection: {e}")
        
        return False
    
    def detect_simple_encounter(self, screenshot: np.ndarray) -> bool:
        """Very simple encounter detection - just look for major changes"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Calculate average brightness
            avg_brightness = np.mean(gray)
            
            # Store previous brightness
            if not hasattr(self, 'prev_brightness'):
                self.prev_brightness = avg_brightness
                self.stable_count = 0
                return False
            
            # Calculate brightness difference
            brightness_diff = abs(avg_brightness - self.prev_brightness)
            
            # Debug output every 10 frames
            if not hasattr(self, 'simple_debug_counter'):
                self.simple_debug_counter = 0
            self.simple_debug_counter += 1
            
            if self.simple_debug_counter % 10 == 0:
                print(f"🔍 Simple detection - Brightness: {avg_brightness:.1f}, Diff: {brightness_diff:.1f}")
            
            # If brightness changes significantly, it might be an encounter
            if brightness_diff > 30:  # Significant brightness change
                print(f"🎉 Major brightness change detected: {brightness_diff:.1f}")
                self.prev_brightness = avg_brightness
                return True
            
            # Update previous brightness gradually for stable scenes
            if brightness_diff < 5:
                self.stable_count += 1
                if self.stable_count > 20:  # After 20 stable frames, update reference
                    self.prev_brightness = avg_brightness
                    self.stable_count = 0
            else:
                self.stable_count = 0
                
        except Exception as e:
            print(f"Error in simple detection: {e}")
        
        return False
    
    def detect_encounter_text(self, screenshot: np.ndarray) -> bool:
        """Detect encounter text like 'A wild [Pokemon] appeared!'"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Look for white text on dark background (typical for encounter text)
            # Create a mask for white/light colored pixels
            white_mask = cv2.inRange(gray, 200, 255)
            
            # Count white pixels (text pixels)
            white_pixels = cv2.countNonZero(white_mask)
            total_pixels = gray.size
            white_percentage = (white_pixels / total_pixels) * 100
            
            # Look for text-like patterns in the bottom area where encounter text appears
            height, width = gray.shape
            bottom_area = gray[int(height * 0.7):, :]  # Bottom 30% of screen
            
            # Apply threshold to get text
            _, thresh = cv2.threshold(bottom_area, 180, 255, cv2.THRESH_BINARY)
            
            # Look for horizontal text lines
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
            text_lines = cv2.countNonZero(horizontal_lines)
            
            # Debug output every 30 frames
            if not hasattr(self, 'text_debug_counter'):
                self.text_debug_counter = 0
            self.text_debug_counter += 1
            
            if self.text_debug_counter % 30 == 0:
                print(f"🔍 Text detection - White: {white_percentage:.1f}%, Text lines: {text_lines}")
            
            # Encounter detected if we have significant white text in bottom area
            if white_percentage > 5 and text_lines > 100:  # Adjust thresholds based on testing
                print(f"📝 Encounter text detected! White: {white_percentage:.1f}%, Lines: {text_lines}")
                return True
                
        except Exception as e:
            print(f"Error in text detection: {e}")
        
        return False
    
    def detect_visual_change(self, screenshot: np.ndarray) -> bool:
        """Detect significant visual changes that indicate encounters (like reference bot)"""
        try:
            # Store reference screenshot for comparison
            if not hasattr(self, 'reference_screenshot'):
                self.reference_screenshot = screenshot.copy()
                self.stable_frames = 0
                return False
            
            # Calculate difference between current and reference
            diff = cv2.absdiff(screenshot, self.reference_screenshot)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            
            # Calculate percentage of changed pixels
            changed_pixels = np.sum(gray_diff > 30)  # Threshold for significant change
            total_pixels = gray_diff.size
            change_percentage = (changed_pixels / total_pixels) * 100
            
            # Debug output every 20 frames
            if not hasattr(self, 'visual_debug_counter'):
                self.visual_debug_counter = 0
            self.visual_debug_counter += 1
            
            if self.visual_debug_counter % 20 == 0:
                print(f"🔍 Visual change: {change_percentage:.1f}%")
            
            # If change is significant, it might be an encounter
            # Your screenshots show a HUGE difference, so this should trigger easily
            if change_percentage > 20:  # More than 20% of screen changed
                print(f"🔍 Significant visual change detected: {change_percentage:.1f}%")
                
                # Reset reference after detecting change
                self.reference_screenshot = screenshot.copy()
                self.stable_frames = 0
                return True
            
            # Update reference screenshot periodically when stable
            self.stable_frames += 1
            if self.stable_frames > 30:  # Update reference every 30 stable frames
                self.reference_screenshot = screenshot.copy()
                self.stable_frames = 0
            
        except Exception as e:
            print(f"Error in visual change detection: {e}")
        
        return False
    
    def detect_center_dialog_debug(self, screenshot: np.ndarray) -> bool:
        """Detect encounter dialog in center of screen with debug output"""
        try:
            # Get image dimensions
            height, width = screenshot.shape[:2]
            
            # Define center area (middle 60% of screen)
            center_x = width // 2
            center_y = height // 2
            dialog_width = int(width * 0.6)
            dialog_height = int(height * 0.4)
            
            # Extract center region
            x1 = center_x - dialog_width // 2
            y1 = center_y - dialog_height // 2
            x2 = center_x + dialog_width // 2
            y2 = center_y + dialog_height // 2
            
            # Ensure bounds are valid
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width, x2)
            y2 = min(height, y2)
            
            center_region = screenshot[y1:y2, x1:x2]
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
            
            # Look for dialog box characteristics:
            # 1. High contrast edges (dialog borders)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # 2. Text-like patterns (horizontal lines)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            text_density = np.sum(horizontal_lines > 0) / horizontal_lines.size
            
            # 3. Check for dialog-like color patterns
            # Dialogs often have consistent background colors
            color_variance = np.var(gray)
            
            # Debug output every 50 frames to avoid spam
            if not hasattr(self, 'debug_counter'):
                self.debug_counter = 0
            self.debug_counter += 1
            if self.debug_counter % 50 == 0:
                print(f"🔍 Dialog check - Edge: {edge_density:.3f}, Text: {text_density:.3f}, Variance: {color_variance:.1f}")
            
            # If we detect dialog characteristics, it's likely an encounter
            # Higher thresholds to avoid false positives from grass patterns
            if edge_density > 0.15 and text_density > 0.03 and color_variance > 500:
                print(f"Dialog detected - Edge density: {edge_density:.3f}, Text density: {text_density:.3f}, Variance: {color_variance:.1f}")
                return True
                
        except Exception as e:
            print(f"Error in center dialog detection: {e}")
        
        return False
    
    def detect_center_dialog(self, screenshot: np.ndarray) -> bool:
        """Detect encounter dialog in center of screen"""
        try:
            # Get image dimensions
            height, width = screenshot.shape[:2]
            
            # Define center area (middle 60% of screen)
            center_x = width // 2
            center_y = height // 2
            dialog_width = int(width * 0.6)
            dialog_height = int(height * 0.4)
            
            # Extract center region
            x1 = center_x - dialog_width // 2
            y1 = center_y - dialog_height // 2
            x2 = center_x + dialog_width // 2
            y2 = center_y + dialog_height // 2
            
            # Ensure bounds are valid
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width, x2)
            y2 = min(height, y2)
            
            center_region = screenshot[y1:y2, x1:x2]
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
            
            # Look for dialog box characteristics:
            # 1. High contrast edges (dialog borders)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # 2. Text-like patterns (horizontal lines)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            text_density = np.sum(horizontal_lines > 0) / horizontal_lines.size
            
            # 3. Check for dialog-like color patterns
            # Dialogs often have consistent background colors
            color_variance = np.var(gray)
            
            # If we detect dialog characteristics, it's likely an encounter
            # Higher thresholds to avoid false positives from grass patterns
            if edge_density > 0.15 and text_density > 0.03 and color_variance > 500:
                print(f"Dialog detected - Edge density: {edge_density:.3f}, Text density: {text_density:.3f}, Variance: {color_variance:.1f}")
                return True
                
        except Exception as e:
            print(f"Error in center dialog detection: {e}")
        
        return False
    
    def detect_pokemon_sprite(self, screenshot: np.ndarray) -> bool:
        """Detect Pokemon sprite appearance in the center area"""
        try:
            # Convert to HSV for better color detection
            hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
            
            # Define color ranges for typical Pokemon sprites
            # Pokemon sprites often have distinct colors different from grass
            
            # Red/Pink range (like the Slowpoke in your image)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            # Blue range
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            
            # Yellow range
            lower_yellow = np.array([20, 50, 50])
            upper_yellow = np.array([30, 255, 255])
            
            # Purple range
            lower_purple = np.array([130, 50, 50])
            upper_purple = np.array([170, 255, 255])
            
            # Create masks for each color range
            mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
            mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
            mask_purple = cv2.inRange(hsv, lower_purple, upper_purple)
            
            # Combine all masks
            pokemon_mask = mask_red1 + mask_red2 + mask_blue + mask_yellow + mask_purple
            
            # Count non-zero pixels (Pokemon sprite pixels)
            pokemon_pixels = cv2.countNonZero(pokemon_mask)
            
            # If we detect a significant number of Pokemon-colored pixels in center area
            # (but not too many, as that would be the entire screen)
            if 50 < pokemon_pixels < 500:  # Adjust thresholds based on testing
                return True
                
        except Exception as e:
            print(f"Error in Pokemon sprite detection: {e}")
        
        return False
    
    def detect_encounter_by_color_change(self, screenshot: np.ndarray) -> bool:
        """Detect encounters by analyzing color distribution changes"""
        try:
            # Store previous screenshot for comparison
            if not hasattr(self, 'previous_screenshot'):
                self.previous_screenshot = screenshot.copy()
                return False
            
            # Calculate color histograms
            current_hist = cv2.calcHist([screenshot], [0, 1, 2], None, [50, 50, 50], [0, 256, 0, 256, 0, 256])
            previous_hist = cv2.calcHist([self.previous_screenshot], [0, 1, 2], None, [50, 50, 50], [0, 256, 0, 256, 0, 256])
            
            # Compare histograms using correlation
            correlation = cv2.compareHist(current_hist, previous_hist, cv2.HISTCMP_CORREL)
            
            # Update previous screenshot
            self.previous_screenshot = screenshot.copy()
            
            # If correlation is low, there's been a significant visual change
            if correlation < 0.7:  # Adjust threshold based on testing
                return True
                
        except Exception as e:
            print(f"Error in color change detection: {e}")
        
        return False
    
    def execute_movement(self, direction: str):
        """Execute a movement in the specified direction"""
        # First ensure we have the game window
        if not self.window_manager.game_hwnd:
            if not self.window_manager.find_game_window():
                print("⚠ PokeMMO window not found, skipping movement")
                return
        
        # Check if game window is still valid
        if not self.window_manager.is_game_running():
            print("⚠ Game not running, skipping movement")
            return
        
        # Map directions to keys
        direction_keys = {
            'w': 'w',  # Up
            's': 's',  # Down  
            'a': 'a',  # Left
            'd': 'd',  # Right
        }
        
        if direction not in direction_keys:
            print(f"⚠ Invalid direction: {direction}")
            return
        
        key = direction_keys[direction]
        
        # No need to focus window - we'll send keys directly to PokeMMO window
        print(f"🎯 Sending key directly to PokeMMO window (Handle: {self.window_manager.game_hwnd})")
        
        # Use the same input method as macros (which works!)
        print(f"🎮 Pressing {key.upper()} key using macro method for {self.movement_duration}s")
        self.input_manager.press_key(key)
        time.sleep(self.movement_duration)
        self.input_manager.release_key(key)
        print(f"🎮 Finished {key.upper()} key press")
    
    def send_key_to_window(self, key: str, duration: float):
        """Send key directly to PokeMMO window using multiple methods"""
        import win32api
        import win32con
        import win32gui
        
        # Map keys to virtual key codes
        key_map = {
            'a': 0x41,  # VK_A
            'd': 0x44,  # VK_D  
            'w': 0x57,  # VK_W
            's': 0x53,  # VK_S
            'e': 0x45   # VK_E
        }
        
        if key not in key_map:
            print(f"❌ Unknown key: {key}")
            return
        
        vk_code = key_map[key]
        
        try:
            # Method 1: Try PostMessage first (more reliable for games)
            print(f"  🎯 Sending {key.upper()} via PostMessage...")
            win32api.PostMessage(self.window_manager.game_hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(duration)
            win32api.PostMessage(self.window_manager.game_hwnd, win32con.WM_KEYUP, vk_code, 0)
            print(f"  ✓ Sent {key.upper()} via PostMessage")
            
        except Exception as e1:
            print(f"  ⚠ PostMessage failed: {e1}")
            
            try:
                # Method 2: Fallback to SendMessage
                print(f"  🎯 Trying SendMessage...")
                win32api.SendMessage(self.window_manager.game_hwnd, win32con.WM_KEYDOWN, vk_code, 0)
                time.sleep(duration)
                win32api.SendMessage(self.window_manager.game_hwnd, win32con.WM_KEYUP, vk_code, 0)
                print(f"  ✓ Sent {key.upper()} via SendMessage")
                
            except Exception as e2:
                print(f"  ⚠ SendMessage failed: {e2}")
                
                try:
                    # Method 3: Focus window and use global keybd_event
                    print(f"  🎯 Trying focus + keybd_event...")
                    win32gui.SetForegroundWindow(self.window_manager.game_hwnd)
                    time.sleep(0.1)
                    
                    win32api.keybd_event(vk_code, 0, 0, 0)  # Key down
                    time.sleep(duration)
                    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up
                    print(f"  ✓ Sent {key.upper()} via keybd_event")
                    
                except Exception as e3:
                    print(f"  ❌ All methods failed: {e3}")
    
    def get_next_movement_direction(self) -> str:
        """Get the next movement direction - alternate between A and D"""
        # Alternate between 'a' and 'd' for left-right movement in grass
        if self.current_direction == 'a':
            self.current_direction = 'd'
        else:
            self.current_direction = 'a'
        
        return self.current_direction
    
    def test_movement(self):
        """Test movement system - press A then D once each"""
        print("🧪 Testing movement system...")
        
        # First, let's debug window detection
        print("🔍 Checking window detection...")
        if not self.window_manager.game_hwnd:
            print("No game window found, attempting to find it...")
            if not self.window_manager.find_game_window():
                print("❌ Could not find PokeMMO window!")
                self.list_all_windows()
                return
        else:
            print(f"✓ Game window found: Handle {self.window_manager.game_hwnd}")
        
        # Test A key
        print("\n🎮 Testing A key...")
        self.execute_movement('a')
        time.sleep(1)
        
        # Test D key  
        print("\n🎮 Testing D key...")
        self.execute_movement('d')
        time.sleep(1)
        
        print("\n✓ Movement test completed")
    
    def list_all_windows(self):
        """List all visible windows for debugging"""
        import win32gui
        
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title.strip():  # Only show windows with titles
                    windows.append((hwnd, window_title))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        print("\n🪟 All visible windows:")
        for hwnd, title in windows[:20]:  # Show first 20 windows
            print(f"  - {title} (Handle: {hwnd})")
        if len(windows) > 20:
            print(f"  ... and {len(windows) - 20} more windows")
        print()
    
    def handle_encounter(self, screenshot: np.ndarray):
        """Handle a detected encounter with improved logic and Pokemon analysis"""
        self.encounters_found += 1
        
        if self.encounter_callback:
            self.encounter_callback('encounter_detected', {
                'count': self.encounters_found,
                'time': time.time() - self.hunt_start_time if self.hunt_start_time else 0
            })
        
        print("🏃 Analyzing encounter and determining action...")
        
        # Wait a moment for the battle interface to appear
        time.sleep(1.5)
        
        # Capture current screenshot for analysis
        current_screenshot = self.capture_full_game_screen()
        if current_screenshot is not None:
            # Save debug screenshot of the battle menu for analysis
            self.save_debug_screenshot(current_screenshot, "battle_menu_analysis")
            
            # Verify battle menu is present using template matching
            battle_menu_detected = self.detect_battle_menu(current_screenshot)
            
            if battle_menu_detected:
                print("✅ Battle menu confirmed via image analysis")
                
                # NEW: Analyze the encounter for Pokemon names and special detection
                should_continue, encounter_type = self.analyze_encounter_for_pokemon(current_screenshot)
                
                if not should_continue:
                    print(f"🛑 {encounter_type.upper()} encounter detected - pausing hunt!")
                    self.pause_hunt()
                    return  # Don't continue with any escape sequence
                
                # Handle different encounter types
                if encounter_type == "horde":
                    print("🎯 Executing horde-specific sequence (D-S-E)")
                    self.execute_horde_sequence()
                    
                    # Wait 3 seconds after horde sequence
                    print("⏳ Waiting 3 seconds after horde sequence...")
                    time.sleep(3.0)
                    
                else:
                    # Normal encounter - use standard E sequence
                    print("🎯 Normal encounter - pressing E exactly 3 times...")
                    for i in range(3):
                        print(f"   Pressing E ({i + 1}/3)")
                        
                        # Use the same input method as macros to press E
                        self.input_manager.press_key('e')
                        time.sleep(0.1)
                        self.input_manager.release_key('e')
                        
                        # Short delay between E presses
                        time.sleep(0.5)
                    
                    print("✅ Finished pressing E 3 times")
                    
                    # Wait exactly 7 seconds before allowing movement again
                    print("⏳ Waiting 7 seconds before resuming movement...")
                    time.sleep(7.0)
                
            else:
                print("⚠ Battle menu not clearly detected, proceeding with standard escape")
                # Fallback to standard sequence if battle menu not detected
                for i in range(3):
                    self.input_manager.press_key('e')
                    time.sleep(0.1)
                    self.input_manager.release_key('e')
                    time.sleep(0.5)
                time.sleep(7.0)
        else:
            print("⚠ Could not capture screenshot, proceeding with standard escape")
            # Fallback sequence
            for i in range(3):
                self.input_manager.press_key('e')
                time.sleep(0.1)
                self.input_manager.release_key('e')
                time.sleep(0.5)
            time.sleep(7.0)
        
        # Reset movement direction to 'a' after encounter
        self.current_direction = 'a'
        print("🔄 Reset movement direction to 'A'")
        
        # Clean up encounter screenshots (ALWAYS delete images after encounter)
        self.cleanup_encounter_screenshots()
        
        print("🚀 Ready to resume hunting!")
    
    def hunt_loop(self):
        """Main hunting loop - New approach: Check for encounters every 10 moves"""
        print("🎯 Auto Hunt started!")
        self.hunt_start_time = time.time()
        loop_count = 0
        
        # Initialize move counter
        if not hasattr(self, 'move_counter'):
            self.move_counter = 0
        
        while self.is_hunting and not self.stop_flag:
            try:
                loop_count += 1
                if loop_count % 50 == 0:  # Debug every 50 loops
                    print(f"🔄 Hunt loop #{loop_count} - is_hunting: {self.is_hunting}, stop_flag: {self.stop_flag}")
                
                # Check if game is still running
                if not self.window_manager.is_game_running():
                    print("❌ Game not running!")
                    if self.status_callback:
                        self.status_callback('error', 'Game not found')
                    break
                
                # Pause if requested
                if self.is_paused:
                    time.sleep(0.5)
                    continue
                
                # Execute movement first
                direction = self.get_next_movement_direction()
                self.execute_movement(direction)
                self.move_counter += 1
                
                # Check for encounters every 10 moves
                if self.move_counter % 10 == 0:
                    print(f"🔍 Checking for encounters after {self.move_counter} moves...")
                    
                    # Wait a moment for any encounter animation to settle
                    time.sleep(1.0)
                    
                    # Capture full game screen for battle menu detection
                    screenshot = self.capture_full_game_screen()
                    if screenshot is not None:
                        if self.detect_battle_menu_fast(screenshot):
                            print("🎉 Battle menu detected - encounter found!")
                            self.handle_encounter(screenshot)
                            
                            # Reset move counter after encounter
                            self.move_counter = 0
                            continue
                        else:
                            print(f"✓ No encounter detected, continuing hunt... ({self.move_counter} total moves)")
                
                # Print movement status every 10 moves
                if self.move_counter % 10 == 0:
                    print(f"🚶 Moving {direction.upper()} - Hunting... ({self.move_counter} moves)")
                
                # Update status
                if self.status_callback:
                    elapsed = time.time() - self.hunt_start_time
                    self.status_callback('hunting', {
                        'encounters': self.encounters_found,
                        'time': elapsed,
                        'direction': direction,
                        'moves': self.move_counter
                    })
                
                # Wait before next move
                time.sleep(self.movement_pause)
                
            except Exception as e:
                print(f"Error in hunt loop: {e}")
                if self.status_callback:
                    self.status_callback('error', str(e))
                break
        
        # Hunt finished
        self.total_hunt_time += time.time() - self.hunt_start_time if self.hunt_start_time else 0
        print(f"🏁 Auto Hunt stopped. Total encounters: {self.encounters_found}, Total moves: {self.move_counter}")
        
        if self.status_callback:
            self.status_callback('hunt_finished', {
                'encounters': self.encounters_found,
                'total_time': self.total_hunt_time,
                'total_moves': self.move_counter
            })
    
    def start_hunt(self) -> bool:
        """Start the auto hunt"""
        if self.is_hunting:
            return False
        
        if not self.window_manager.is_game_running():
            print("❌ Cannot start hunt - game not running")
            return False
        
        # Check if templates are loaded for better detection
        if not self.templates:
            print("⚠ No battle menu templates loaded!")
            print("💡 For best results, load battle menu templates using 'Load Templates' button")
            print("📁 Place PNG screenshots of battle menus in the 'templates' folder")
        else:
            print(f"✅ {len(self.templates)} battle menu templates loaded")
        
        # Reset statistics
        self.encounters_found = 0
        self.stop_flag = False
        self.is_hunting = True
        self.is_paused = False
        
        # Start hunt thread
        self.hunt_thread = threading.Thread(target=self.hunt_loop, daemon=True)
        self.hunt_thread.start()
        
        return True
    
    def stop_hunt(self):
        """Stop the auto hunt"""
        if not self.is_hunting:
            return
        
        self.is_hunting = False
        self.stop_flag = True
        
        # Wait for thread to finish (only if we're not in the hunt thread)
        if self.hunt_thread and threading.current_thread() != self.hunt_thread:
            self.hunt_thread.join(timeout=3.0)
    
    def pause_hunt(self):
        """Pause the auto hunt"""
        self.is_paused = True
    
    def resume_hunt(self):
        """Resume the auto hunt"""
        self.is_paused = False
    
    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def set_encounter_callback(self, callback):
        """Set callback for encounter events"""
        self.encounter_callback = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hunting statistics"""
        current_time = time.time() - self.hunt_start_time if self.hunt_start_time and self.is_hunting else 0
        
        return {
            'encounters_found': self.encounters_found,
            'hunt_time': current_time,
            'total_hunt_time': self.total_hunt_time,
            'is_hunting': self.is_hunting,
            'is_paused': self.is_paused,
            'encounters_per_hour': (self.encounters_found / (current_time / 3600)) if current_time > 0 else 0
        }

    def _enhance_contrast(self, image, factor):
        """Enhance image contrast for better OCR"""
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    
    def _sharpen_image(self, image):
        """Apply sharpening filter to image"""
        from PIL import ImageFilter
        return image.filter(ImageFilter.SHARPEN)
    
    def _denoise_image(self, image):
        """Apply denoising to image"""
        import cv2
        import numpy as np
        # Convert PIL to OpenCV format
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(cv_image)
        # Convert back to PIL
        from PIL import Image
        return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)).convert('L')
    
    def _apply_threshold(self, image, method='binary'):
        """Apply threshold to image for better text contrast"""
        import cv2
        import numpy as np
        cv_image = np.array(image)
        
        if method == 'binary':
            _, thresh = cv2.threshold(cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif method == 'adaptive':
            thresh = cv2.adaptiveThreshold(cv_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        else:
            thresh = cv_image
            
        from PIL import Image
        return Image.fromarray(thresh)
    
    def _morphology_cleanup(self, image):
        """Apply morphological operations to clean up text"""
        import cv2
        import numpy as np
        cv_image = np.array(image)
        
        # Create kernel
        kernel = np.ones((2,2), np.uint8)
        
        # Apply morphological operations
        opening = cv2.morphologyEx(cv_image, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
        
        from PIL import Image
        return Image.fromarray(closing)

    def detect_pokemon_names_top_screen(self, screenshot: np.ndarray, max_retries: int = 3) -> Tuple[List[str], bool, bool]:
        """
        Detect Pokemon names from the top screen area using enhanced OCR with retry logic
        Returns: (pokemon_names, is_horde, contains_shiny)
        """
        try:
            # Use custom detection area if available, otherwise default coordinates
            if hasattr(self, 'custom_detection_area') and self.custom_detection_area:
                x1, y1, x2, y2 = self.custom_detection_area
            else:
                # Default coordinates for Pokemon names area
                x1, y1, x2, y2 = 342, 153, 1553, 228
            
            # Crop the region
            crop_region = screenshot[y1:y2, x1:x2]
            if crop_region.size == 0:
                print("❌ Invalid crop region for Pokemon detection")
                return [], False, False
            
            # Save debug screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            crop_filename = f"pokemon_names_precise_area_{timestamp}.png"
            crop_path = os.path.join(self.debug_dir, crop_filename)
            cv2.imwrite(crop_path, crop_region)
            
            # Try OCR multiple times until we get some meaningful text
            for attempt in range(max_retries):
                # Enhanced preprocessing methods
                preprocessing_methods = [
                    ("High Contrast", lambda img: self._enhance_contrast(img, 2.5)),
                    ("Medium Contrast", lambda img: self._enhance_contrast(img, 1.8)),
                    ("Sharpened", lambda img: self._sharpen_image(img)),
                    ("Threshold Binary", lambda img: self._apply_threshold(img, 'binary')),
                    ("Morphology Cleaned", lambda img: self._morphology_cleanup(img)),
                ]
                
                # OCR configurations
                ocr_configs = [
                    ("PSM 6", {"psm": 6, "oem": 3}),  # Block of text - works best
                    ("PSM 7", {"psm": 7, "oem": 3}),  # Single text line
                    ("PSM 8", {"psm": 8, "oem": 3}),  # Single word
                ]
                
                all_ocr_results = []
                
                # Try each preprocessing method with each OCR config
                for prep_name, prep_func in preprocessing_methods:
                    try:
                        processed_img = prep_func(crop_region.copy())
                        
                        for config_name, config in ocr_configs:
                            try:
                                custom_config = f'--psm {config["psm"]} --oem {config["oem"]} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
                                
                                # Get OCR text
                                ocr_text = pytesseract.image_to_string(processed_img, config=custom_config).strip()
                                
                                if ocr_text and len(ocr_text) > 2:
                                    all_ocr_results.append(ocr_text)
                                        
                            except Exception as e:
                                continue  # Skip failed OCR attempts
                                
                    except Exception as e:
                        continue  # Skip failed preprocessing
                
                # Combine all OCR results
                combined_text = ' '.join(all_ocr_results)
                
                # If we got some text, process it
                if combined_text and len(combined_text.strip()) > 3:
                    # Process the text using the working method
                    pokemon_names = self.extract_pokemon_names_working(combined_text)
                    
                    # Apply special Pokemon filtering only at the end
                    filtered_names, is_horde, contains_shiny = self.apply_special_pokemon_filter(pokemon_names, combined_text)
                    
                    if filtered_names:  # If we found valid Pokemon after filtering
                        print(f"🎯 Pokemon detected on attempt {attempt + 1}")
                        print(f"   Names found: {filtered_names}")
                        print(f"   Is Horde: {is_horde}")
                        print(f"   Contains Shiny: {contains_shiny}")
                        return filtered_names, is_horde, contains_shiny
                
                # If no valid Pokemon found, try again
                if attempt < max_retries - 1:
                    time.sleep(0.1)  # Small delay before retry
            
            # If all retries failed, return empty result
            print(f"❌ No Pokemon detected after {max_retries} attempts")
            return [], False, False
            
        except Exception as e:
            print(f"❌ Error in Pokemon name detection: {e}")
            return [], False, False

    def extract_pokemon_names_working(self, raw_text: str) -> List[str]:
        """Extract Pokemon names using the working method (revert to previous successful approach)"""
        if not raw_text:
            return []
        
        # Clean and normalize text
        cleaned_text = ''.join(c if c.isalpha() or c.isspace() else ' ' for c in raw_text)
        cleaned_text = ' '.join(cleaned_text.split()).lower()
        
        # Count Pokemon occurrences for horde detection
        pokemon_counts = {}
        found_any_normal = False
        
        # Check against each normal Pokemon name and count occurrences
        for normal_pokemon in self.normal_pokemon_list:
            count = self.count_pokemon_occurrences_working(normal_pokemon, cleaned_text)
            if count > 0:
                # For single Pokemon encounters, limit to 1 unless there are clear multiple instances
                if count <= 2:
                    pokemon_counts[normal_pokemon] = 1  # Treat as single Pokemon
                else:
                    # Only count as horde if there are 3+ strong matches (real horde)
                    pokemon_counts[normal_pokemon] = count
                found_any_normal = True
        
        # If no normal Pokemon found, try more aggressive matching
        if not found_any_normal:
            # Try partial matching - look for Pokemon names as substrings
            for normal_pokemon in self.normal_pokemon_list:
                if self.aggressive_pokemon_search_working(normal_pokemon, cleaned_text):
                    pokemon_counts[normal_pokemon] = 1
                    found_any_normal = True
        
        # Convert counts back to list format for compatibility
        detected_pokemon = []
        for pokemon, count in pokemon_counts.items():
            # Add the pokemon name 'count' times to the list for horde detection
            for _ in range(count):
                detected_pokemon.append(pokemon)
        
        return detected_pokemon

    def count_pokemon_occurrences_working(self, pokemon_name: str, text: str) -> int:
        """Count Pokemon occurrences using the working method"""
        if not pokemon_name or not text:
            return 0
        
        pokemon_lower = pokemon_name.lower()
        text_lower = text.lower()
        
        # Method 1: Exact word boundary matching
        import re
        pattern = r'\b' + re.escape(pokemon_lower) + r'\b'
        exact_matches = len(re.findall(pattern, text_lower))
        
        if exact_matches > 0:
            return exact_matches
        
        # Method 2: Substring matching with length validation
        count = 0
        words = text_lower.split()
        
        for word in words:
            # Check if Pokemon name appears in this word
            if pokemon_lower in word:
                # Additional validation: the Pokemon name should be a significant part of the word
                if len(word) > len(pokemon_lower) + 3:
                    # For longer words, the Pokemon name should be at the start or end
                    if word.startswith(pokemon_lower) or word.endswith(pokemon_lower):
                        count += 1
                    else:
                        # Check if it's a close match
                        similarity = self.calculate_string_similarity_working(pokemon_lower, word)
                        if similarity >= 0.8:  # High similarity threshold
                            count += 1
                else:
                    # For shorter words, direct substring match is fine
                    count += 1
        
        return count

    def aggressive_pokemon_search_working(self, pokemon_name: str, text: str) -> bool:
        """More aggressive search for Pokemon names in OCR text"""
        pokemon_lower = pokemon_name.lower()
        text_lower = text.lower()
        
        # Method 1: Check if Pokemon name appears anywhere in text
        if pokemon_lower in text_lower:
            return True
        
        # Method 2: Check if most characters of Pokemon name are present consecutively
        min_length = max(3, len(pokemon_lower) - 2)  # Allow up to 2 character differences
        
        for i in range(len(text_lower) - min_length + 1):
            for j in range(i + min_length, min(i + len(pokemon_lower) + 3, len(text_lower) + 1)):
                substring = text_lower[i:j]
                
                # Calculate similarity
                similarity = self.calculate_string_similarity_working(pokemon_lower, substring)
                if similarity >= 0.7:  # 70% similarity threshold
                    return True
        
        # Method 3: Check if Pokemon name characters appear in order (with gaps allowed)
        pokemon_chars = list(pokemon_lower)
        text_chars = list(text_lower)
        
        matches = 0
        text_index = 0
        
        for char in pokemon_chars:
            while text_index < len(text_chars):
                if text_chars[text_index] == char:
                    matches += 1
                    text_index += 1
                    break
                text_index += 1
        
        match_ratio = matches / len(pokemon_chars)
        if match_ratio >= 0.8:  # 80% of characters must match in order
            return True
        
        return False

    def calculate_string_similarity_working(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using simple character matching"""
        if not str1 or not str2:
            return 0.0
        
        # Count matching characters
        str1_chars = list(str1.lower())
        str2_chars = list(str2.lower())
        
        matches = 0
        for char in str1_chars:
            if char in str2_chars:
                str2_chars.remove(char)  # Remove to avoid double counting
                matches += 1
        
        # Calculate similarity as ratio of matches to average length
        avg_length = (len(str1) + len(str2)) / 2
        similarity = matches / avg_length
        
        return min(similarity, 1.0)  # Cap at 1.0

    def apply_special_pokemon_filter(self, pokemon_names: List[str], raw_text: str) -> Tuple[List[str], bool, bool]:
        """Apply special Pokemon filtering to detected names"""
        if not pokemon_names:
            return [], False, False
        
        # Define legendary Pokemon that can appear
        legendary_pokemon = ['moltres', 'articuno', 'entei', 'zapdos', 'suicune', 'raikou']
        
        # Check for shiny indicators
        contains_shiny = 'shiny' in raw_text.lower()
        
        # Determine if this is a horde encounter
        is_horde = self.detect_horde_encounter_working(pokemon_names)
        
        # Check if we have any special encounters (shiny or legendary)
        has_special = contains_shiny or any(pokemon in legendary_pokemon for pokemon in pokemon_names)
        
        # If it's a special encounter, return as-is
        if has_special:
            return pokemon_names, is_horde, contains_shiny
        
        # For normal encounters, check if all Pokemon are in the normal list
        valid_pokemon = []
        for pokemon in pokemon_names:
            if pokemon in self.normal_pokemon_list:
                valid_pokemon.append(pokemon)
        
        # If we found valid normal Pokemon, return them
        if valid_pokemon:
            is_horde = self.detect_horde_encounter_working(valid_pokemon)
            return valid_pokemon, is_horde, False
        
        # If no valid Pokemon found, return original list (let the old logic handle it)
        return pokemon_names, is_horde, contains_shiny

    def detect_horde_encounter_working(self, pokemon_names: List[str]) -> bool:
        """Detect if this is a horde encounter (2+ Pokemon with same name)"""
        if len(pokemon_names) < 2:
            return False
        
        # Count occurrences of each Pokemon name
        name_counts = {}
        for name in pokemon_names:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        # Check if any Pokemon appears 2+ times
        for name, count in name_counts.items():
            if count >= 2:
                return True
        
        return False

    def analyze_encounter_for_pokemon(self, screenshot: np.ndarray) -> Tuple[bool, str]:
        """
        Analyze encounter for Pokemon names and determine action
        Returns: (should_continue_hunt, encounter_type)
        """
        print("🔍 Analyzing encounter for Pokemon names...")
        
        # Detect Pokemon names from top screen area with retry logic
        pokemon_names, is_horde, contains_shiny = self.detect_pokemon_names_top_screen(screenshot, max_retries=3)
        
        if not pokemon_names:
            print("⚠️ Could not detect Pokemon names - treating as normal encounter")
            return True, "unknown"
        
        print(f"🔍 Checking detected Pokemon: {pokemon_names}")
        print(f"🔍 Against normal list: {self.normal_pokemon_list}")
        
        # Determine encounter type and action
        if is_horde:
            self.horde_encounters_found += 1
            self.last_encounter_type = "horde"
            # Get unique Pokemon names for display
            unique_names = list(set(pokemon_names))
            # Count each unique Pokemon
            name_counts = {}
            for name in pokemon_names:
                name_counts[name] = name_counts.get(name, 0) + 1
            
            horde_description = ", ".join([f"{count}x {name}" for name, count in name_counts.items()])
            self.last_detected_pokemon = f"Horde: {horde_description}"
            print(f"🎯 HORDE ENCOUNTER detected: {horde_description}")
            return True, "horde"  # Continue hunt but with special sequence
        
        # Check for shiny
        if contains_shiny:
            self.shiny_encounters_found += 1
            self.last_encounter_type = "shiny"
            unique_names = list(set(pokemon_names))
            self.last_detected_pokemon = f"Shiny: {', '.join(unique_names)}"
            print(f"✨ SHINY ENCOUNTER detected: {unique_names}")
            self.handle_special_encounter(unique_names, True, screenshot)
            return False, "shiny"  # Pause hunt
        
        # Check if ALL detected Pokemon are in the normal list
        unique_pokemon = list(set(pokemon_names))  # Get unique names only
        all_normal = True
        special_pokemon = []
        
        for name in unique_pokemon:
            name_is_normal = False
            for normal_pokemon in self.normal_pokemon_list:
                if self.is_pokemon_name_match(normal_pokemon, name):
                    name_is_normal = True
                    break
            if not name_is_normal:
                all_normal = False
                special_pokemon.append(name)
        
        if not all_normal:
            # At least one Pokemon is not in normal list - special encounter
            self.special_encounters_found += 1
            self.last_encounter_type = "special"
            self.last_detected_pokemon = f"Special: {', '.join(special_pokemon)}"
            print(f"🎯 SPECIAL ENCOUNTER detected: {special_pokemon}")
            self.handle_special_encounter(special_pokemon, False, screenshot)
            return False, "special"  # Pause hunt
        
        # All Pokemon are normal
        self.last_encounter_type = "normal"
        self.last_detected_pokemon = ', '.join(unique_pokemon)
        print(f"✅ Normal encounter: {unique_pokemon} (all found in normal list)")
        return True, "normal"

    def is_pokemon_name_match(self, pokemon_name: str, detected_name: str) -> bool:
        """Check if a detected name matches a Pokemon name (bidirectional fuzzy matching)"""
        pokemon_lower = pokemon_name.lower()
        detected_lower = detected_name.lower()
        
        # Direct match
        if pokemon_lower == detected_lower:
            return True
        
        # Check if one contains the other
        if pokemon_lower in detected_lower or detected_lower in pokemon_lower:
            return True
        
        # Fuzzy matching for OCR errors
        if self.is_pokemon_name_in_word_fuzzy(pokemon_name, detected_name):
            return True
        
        if self.is_pokemon_name_in_word_fuzzy(detected_name, pokemon_name):
            return True
        
        return False

    def is_pokemon_name_in_word_fuzzy(self, pokemon_name: str, word: str) -> bool:
        """Check if a Pokemon name is contained in a word using fuzzy matching"""
        pokemon_lower = pokemon_name.lower()
        word_lower = word.lower()
        
        # Skip if word is too short
        if len(word_lower) < len(pokemon_lower):
            return False
        
        # Check if most characters of Pokemon name are present in order
        pokemon_chars = list(pokemon_lower)
        word_chars = list(word_lower)
        
        matches = 0
        word_index = 0
        
        for char in pokemon_chars:
            while word_index < len(word_chars):
                if word_chars[word_index] == char:
                    matches += 1
                    word_index += 1
                    break
                word_index += 1
        
        # If most characters match in order, consider it a match
        match_ratio = matches / len(pokemon_chars)
        if match_ratio >= 0.8:  # 80% of characters must match for fuzzy word matching
            return True
        
        return False

    def handle_special_encounter(self, pokemon_names: List[str], is_shiny: bool, screenshot: np.ndarray):
        """Handle detection of special or shiny Pokemon"""
        pokemon_list_str = ', '.join(pokemon_names)
        
        if is_shiny:
            encounter_type = "✨ SHINY"
            message = f"✨ SHINY POKEMON DETECTED: {pokemon_list_str.upper()} ✨"
            print(f"🌟 {message}")
        else:
            encounter_type = "🎯 SPECIAL"
            message = f"🎯 SPECIAL ENCOUNTER: {pokemon_list_str.upper()}"
            print(f"🎯 {message}")
        
        # Save special screenshot
        prefix = f"{'shiny' if is_shiny else 'special'}_{pokemon_list_str.replace(', ', '_')}"
        special_screenshot_path = self.save_debug_screenshot(screenshot, prefix)
        
        # Trigger callback if set
        if self.special_encounter_callback:
            self.special_encounter_callback(encounter_type, {
                'pokemon_names': pokemon_names,
                'is_shiny': is_shiny,
                'screenshot_path': special_screenshot_path,
                'message': message
            })
        
        # Show popup notification
        self.show_special_encounter_popup(pokemon_names, is_shiny, message)

    def show_special_encounter_popup(self, pokemon_names: List[str], is_shiny: bool, message: str):
        """Show popup notification for special encounters"""
        try:
            import tkinter as tk
            from tkinter import messagebox
            import threading
            
            def show_popup():
                root = tk.Tk()
                root.withdraw()
                
                title = "✨ SHINY POKEMON!" if is_shiny else "🎯 SPECIAL ENCOUNTER!"
                pokemon_list_str = ', '.join(pokemon_names)
                
                popup_message = f"{message}\n\n"
                if is_shiny:
                    popup_message += f"🌟 SHINY {pokemon_list_str.upper()} detected!\n"
                    popup_message += "🎉 Extremely rare encounter!\n\n"
                else:
                    popup_message += f"🎯 {pokemon_list_str.upper()} not in normal list!\n"
                    popup_message += "📊 Special encounter detected!\n\n"
                
                popup_message += "⚠️ Hunt has been PAUSED.\n"
                popup_message += "📁 Screenshot saved in debug_screenshots.\n"
                popup_message += "🎮 Check your game!"
                
                messagebox.showinfo(title, popup_message)
                root.destroy()
            
            popup_thread = threading.Thread(target=show_popup, daemon=True)
            popup_thread.start()
            
        except Exception as e:
            print(f"❌ Error showing popup: {e}")

    def set_special_encounter_callback(self, callback):
        """Set callback for special encounter notifications"""
        self.special_encounter_callback = callback

    def update_normal_pokemon_list(self, pokemon_list: List[str]):
        """Update the list of normal Pokemon for current location"""
        self.normal_pokemon_list = [p.lower() for p in pokemon_list]
        print(f"✅ Updated normal Pokemon list: {self.normal_pokemon_list}")

    def get_encounter_statistics(self) -> Dict[str, Any]:
        """Get enhanced statistics including special encounters"""
        base_stats = self.get_statistics()
        base_stats.update({
            'special_encounters': self.special_encounters_found,
            'shiny_encounters': self.shiny_encounters_found,
            'horde_encounters': self.horde_encounters_found,
            'last_detected_pokemon': self.last_detected_pokemon,
            'last_encounter_type': self.last_encounter_type
        })
        return base_stats

    def execute_horde_sequence(self):
        """Execute D-S-E sequence for horde encounters"""
        print("🎮 Executing horde sequence: D → S → E")
        
        # Press D
        print("   Pressing D key")
        self.input_manager.press_key('d')
        time.sleep(0.1)
        self.input_manager.release_key('d')
        time.sleep(0.5)
        
        # Press S
        print("   Pressing S key")
        self.input_manager.press_key('s')
        time.sleep(0.1)
        self.input_manager.release_key('s')
        time.sleep(0.5)
        
        # Press E
        print("   Pressing E key")
        self.input_manager.press_key('e')
        time.sleep(0.1)
        self.input_manager.release_key('e')
        
        print("✅ Horde sequence (D-S-E) completed")

    def detect_battle_menu_fast(self, screenshot: np.ndarray) -> bool:
        """Fast battle menu detection using template matching only (no pokecenter check)"""
        try:
            # Only check battle menu templates, skip pokecenter templates
            battle_templates = [
                'battle_menu',
                'battle_menu_example'
            ]
            
            for template_name in battle_templates:
                if template_name in self.templates:
                    detected, location = self.detect_template(screenshot, template_name)
                    if detected:
                        print(f"✅ Battle menu detected using template: {template_name}")
                        return True
            
            print("❌ No battle menu templates matched")
            return False
            
        except Exception as e:
            print(f"❌ Error in fast battle menu detection: {e}")
            return False

    def test_pokemon_detection_fix(self):
        """Test the improved Pokemon detection to verify fixes"""
        print("🧪 Testing Pokemon detection improvements...")
        
        # Test case from user's console output
        test_text = "ee me iPidgeottoLv"
        print(f"Testing with OCR text: '{test_text}'")
        
        # Test each Pokemon
        test_results = {}
        for pokemon in self.normal_pokemon_list:
            count = self.count_pokemon_occurrences(pokemon, test_text)
            test_results[pokemon] = count
        
        print("\n📊 Test Results:")
        for pokemon, count in test_results.items():
            print(f"   {pokemon}: {count} occurrences")
        
        # Expected: only pidgeotto should be found (1 time), not pidgey
        expected_pidgeotto = 1
        expected_pidgey = 0
        
        actual_pidgeotto = test_results.get('pidgeotto', 0)
        actual_pidgey = test_results.get('pidgey', 0)
        
        print(f"\n🎯 Validation:")
        print(f"   Expected pidgeotto: {expected_pidgeotto}, Got: {actual_pidgeotto} {'✅' if actual_pidgeotto == expected_pidgeotto else '❌'}")
        print(f"   Expected pidgey: {expected_pidgey}, Got: {actual_pidgey} {'✅' if actual_pidgey == expected_pidgey else '❌'}")
        
        success = (actual_pidgeotto == expected_pidgeotto and actual_pidgey == expected_pidgey)
        print(f"\n{'✅ Test PASSED' if success else '❌ Test FAILED'}")
        
        return success

    def test_custom_detection_area(self, screenshot: np.ndarray) -> bool:
        """Test OCR detection on user-selected custom area"""
        if not hasattr(self, 'custom_detection_area'):
            print("❌ No custom detection area has been set")
            return False
        
        try:
            import pytesseract
            from PIL import Image
            import os
            
            # Get custom area coordinates
            left, top, right, bottom = self.custom_detection_area
            
            print(f"🔍 Testing custom detection area: ({left}, {top}) to ({right}, {bottom})")
            print(f"   Area size: {right - left}x{bottom - top} pixels")
            
            # Extract the custom area from screenshot
            custom_region = screenshot[top:bottom, left:right]
            
            # Save debug screenshot of the custom area with a highlighted border
            import cv2
            debug_screenshot = screenshot.copy()
            cv2.rectangle(debug_screenshot, (left, top), (right, bottom), (0, 255, 0), 3)
            self.save_debug_screenshot(debug_screenshot, "custom_area_test_full")
            
            # Save just the selected area
            self.save_debug_screenshot(custom_region, "custom_area_test_region")
            
            # Convert to PIL for OCR
            region_rgb = cv2.cvtColor(custom_region, cv2.COLOR_BGR2RGB)
            pil_region = Image.fromarray(region_rgb)
            
            # Try to set Tesseract path
            possible_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
            
            # Apply multiple OCR approaches
            results = []
            
            # Enhanced contrast version
            gray_image = pil_region.convert('L')
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(gray_image)
            enhanced_image = enhancer.enhance(3.0)
            
            # Approach 1: High contrast with character filtering
            config1 = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
            text1 = pytesseract.image_to_string(enhanced_image, config=config1).strip()
            results.append(("High Contrast", text1))
            
            # Approach 2: Single line mode
            config2 = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
            text2 = pytesseract.image_to_string(enhanced_image, config=config2).strip()
            results.append(("Single Line", text2))
            
            # Approach 3: Raw text without enhancement
            config3 = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
            text3 = pytesseract.image_to_string(pil_region, config=config3).strip()
            results.append(("Raw Image", text3))
            
            print(f"\n📋 OCR Results from Custom Area:")
            for approach, text in results:
                print(f"   {approach}: '{text}'")
            
            # Use the new detection system to analyze the text
            all_detected_text = " ".join([text for _, text in results if text])
            
            if all_detected_text:
                print(f"\n🔍 Combined OCR text: '{all_detected_text}'")
                
                # Use the working detection methods
                pokemon_names = self.extract_pokemon_names_working(all_detected_text)
                
                # Apply special Pokemon filtering
                filtered_names, is_horde, contains_shiny = self.apply_special_pokemon_filter(pokemon_names, all_detected_text)
                
                print(f"\n🎯 New Detection System Results:")
                if filtered_names:
                    print(f"   Pokemon found: {filtered_names}")
                    print(f"   Is Horde: {is_horde}")
                    print(f"   Contains Shiny: {contains_shiny}")
                    
                    if contains_shiny:
                        print("   ✨ SHINY encounter detected!")
                    elif any(p in ['moltres', 'articuno', 'entei', 'zapdos', 'suicune', 'raikou'] for p in filtered_names):
                        print("   🔥 LEGENDARY encounter detected!")
                    elif filtered_names[0] not in self.normal_pokemon_list and filtered_names[0] != "shiny_unknown":
                        print("   🎯 SPECIAL encounter detected!")
                    else:
                        print("   ✅ Normal encounter detected")
                else:
                    print("   ❌ No valid Pokemon detected")
                
                return True
            else:
                print("❌ No text detected in selected area")
                return False
                
        except Exception as e:
            print(f"❌ Error testing custom detection area: {e}")
            return False


class TemplateManager:
    """Manages template images for screen recognition"""
    
    def __init__(self):
        self.template_dir = "templates"
        self.ensure_template_directory()
    
    def ensure_template_directory(self):
        """Create templates directory if it doesn't exist"""
        import os
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir)
            print(f"Created templates directory: {self.template_dir}")
    
    def capture_template(self, name: str, bbox: Tuple[int, int, int, int]) -> bool:
        """Capture a template image from screen coordinates"""
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            filepath = os.path.join(self.template_dir, f"{name}.png")
            screenshot.save(filepath)
            print(f"✓ Template saved: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Failed to save template {name}: {e}")
            return False
    
    def list_templates(self) -> List[str]:
        """List all available templates"""
        import os
        templates = []
        if os.path.exists(self.template_dir):
            for file in os.listdir(self.template_dir):
                if file.endswith('.png'):
                    templates.append(file[:-4])  # Remove .png extension
        return templates 