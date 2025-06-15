"""
Sweet Scent Automation System
Automates Sweet Scent encounters with PP management and macro integration
"""
import threading
import time
import os
import json
import cv2
import numpy as np
from PIL import Image, ImageGrab
from typing import Dict, Any, Optional, Callable


class SweetScentEngine:
    """Engine for automating Sweet Scent encounters with PP management"""
    
    def __init__(self, window_manager, input_manager, macro_manager):
        self.window_manager = window_manager
        self.input_manager = input_manager
        self.macro_manager = macro_manager
        
        # Sweet Scent state
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        self.hunt_thread = None
        
        # Sweet Scent configuration
        self.sweet_scent_uses = 6  # Maximum uses before needing to heal
        self.current_uses = 0
        self.selected_macro = None
        
        # Timing configurations
        self.sweet_scent_animation_delay = 4.0  # Wait after Sweet Scent
        self.initial_e_presses = 3  # Number of E presses after Sweet Scent
        self.initial_e_interval = 0.4  # Interval between initial E presses
        self.post_e_delay = 1.0  # Wait after all initial E presses are complete
        self.encounter_loop_duration = 10.0  # How long to run X+E loop
        self.encounter_loop_interval = 0.2  # Interval between X and E in loop
        self.heal_delay = 2.0  # Wait after heal
        self.cycle_pause = 1.0  # Pause between cycles
        self.initial_focus_delay = 2.0  # Wait before first Q press to ensure game focus
        self.use_e_plus_e = False  # Use E+E instead of X+E loop
        
        # Debug configuration
        self.debug_pokecenter_enabled = False  # Enable pokecenter stuck detection
        self.debug_s_key_duration = 2.0  # How long to press S key continuously
        self.debug_e_key_duration = 3.0  # How long to press E key multiple times
        self.debug_e_key_interval = 0.2  # Interval between E key presses
        self.debug_check_interval = 60.0  # How often to check for pokecenter (seconds) - increased to reduce false positives
        self.debug_last_check_time = 0  # Last time we checked for pokecenter
        
        # Statistics
        self.encounters_found = 0
        self.sweet_scent_cycles = 0
        self.heal_cycles = 0
        self.hunt_start_time = None
        self.total_hunt_time = 0
        
        # Callbacks
        self.status_callback = None
        self.encounter_callback = None
        
        # Preset management
        self.presets_dir = "sweet_scent_presets"
        self.ensure_presets_directory()
        
        # Template for pokecenter detection
        self.pokecenter_template = None
        self.template_threshold = 0.7  # Confidence threshold for template matching
        self.load_pokecenter_template()
        
    def load_pokecenter_template(self):
        """Load the pokecenter template for detection"""
        template_path = os.path.join("templates", "pokecenter_example.png")
        if os.path.exists(template_path):
            try:
                self.pokecenter_template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                if self.pokecenter_template is not None:
                    template_h, template_w = self.pokecenter_template.shape[:2]
                    print(f"✓ Loaded pokecenter template: {template_w}x{template_h}")
                else:
                    print(f"❌ Failed to load pokecenter template from {template_path}")
            except Exception as e:
                print(f"❌ Error loading pokecenter template: {e}")
                self.pokecenter_template = None
        else:
            print(f"⚠ Pokecenter template not found at {template_path}")
            self.pokecenter_template = None
    
    def capture_game_screen(self):
        """Capture the current game screen for analysis"""
        try:
            if not self.window_manager.is_game_running():
                return None
            
            # Get game window position and size
            game_pos = self.window_manager.get_game_position()
            if not game_pos:
                return None
            
            # Capture the game window area
            screenshot = ImageGrab.grab(bbox=(
                game_pos['x'], 
                game_pos['y'], 
                game_pos['x'] + game_pos['width'], 
                game_pos['y'] + game_pos['height']
            ))
            
            # Convert PIL image to OpenCV format
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            return screenshot_cv
            
        except Exception as e:
            print(f"❌ Error capturing game screen: {e}")
            return None
    
    def detect_pokecenter_dialogue(self, screenshot: np.ndarray) -> bool:
        """Detect if the player is stuck in pokecenter dialogue using multiple methods"""
        screenshot_h, screenshot_w = screenshot.shape[:2]
        print(f"🔍 Analyzing screenshot: {screenshot_w}x{screenshot_h}")
        
        # Method 1: Template matching (if template is available and appropriate size)
        template_confidence = 0.0
        template_detected = False
        
        if self.pokecenter_template is not None:
            try:
                template_h, template_w = self.pokecenter_template.shape[:2]
                print(f"📋 Template size: {template_w}x{template_h}")
                
                if template_h <= screenshot_h and template_w <= screenshot_w:
                    # Perform template matching
                    result = cv2.matchTemplate(screenshot, self.pokecenter_template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    template_confidence = max_val
                    
                    print(f"🎯 Template matching confidence: {template_confidence:.3f} (threshold: {self.template_threshold})")
                    
                    if template_confidence >= self.template_threshold:
                        template_detected = True
                        print(f"✅ Template match detected at ({max_loc[0]}, {max_loc[1]})")
                else:
                    print(f"⚠ Template ({template_w}x{template_h}) larger than screenshot ({screenshot_w}x{screenshot_h}) - using alternative detection")
                    
            except Exception as e:
                print(f"❌ Error in template matching: {e}")
        else:
            print("⚠ No pokecenter template loaded - using alternative detection")
        
        # Method 2: Black bottom detection (dialogue screens often have black bottom areas)
        black_bottom_detected = self.detect_black_bottom_area(screenshot)
        
        # Method 3: Overall darkness detection (dialogue screens are often darker)
        darkness_detected = self.detect_overall_darkness(screenshot)
        
        # Combine detection methods
        detection_result = template_detected or black_bottom_detected or darkness_detected
        
        print(f"🔍 Detection summary:")
        print(f"   Template: {'✅' if template_detected else '❌'} (confidence: {template_confidence:.3f})")
        print(f"   Black bottom: {'✅' if black_bottom_detected else '❌'}")
        print(f"   Overall darkness: {'✅' if darkness_detected else '❌'}")
        print(f"   Final result: {'🏥 POKECENTER DETECTED' if detection_result else '✓ No pokecenter detected'}")
        
        return detection_result
    
    def detect_black_bottom_area(self, screenshot: np.ndarray) -> bool:
        """Detect if the bottom portion of the screen is mostly black (indicating dialogue)"""
        try:
            screenshot_h, screenshot_w = screenshot.shape[:2]
            
            # Analyze bottom 20% of the screen (reduced from 25% for better accuracy)
            bottom_height = int(screenshot_h * 0.20)
            bottom_area = screenshot[screenshot_h - bottom_height:, :]
            
            # Convert to grayscale for analysis
            if len(bottom_area.shape) == 3:
                bottom_gray = cv2.cvtColor(bottom_area, cv2.COLOR_BGR2GRAY)
            else:
                bottom_gray = bottom_area
            
            # Calculate percentage of dark pixels (stricter threshold)
            dark_threshold = 25  # Stricter threshold (was 30)
            dark_pixels = np.sum(bottom_gray < dark_threshold)
            total_pixels = bottom_gray.size
            dark_percentage = (dark_pixels / total_pixels) * 100
            
            print(f"🌑 Bottom area analysis: {dark_percentage:.1f}% dark pixels")
            
            # More strict threshold: 90% instead of 70% to reduce false positives
            if dark_percentage > 90:
                print(f"🏥 Black bottom area detected! ({dark_percentage:.1f}% dark)")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error in black bottom detection: {e}")
            return False
    
    def detect_overall_darkness(self, screenshot: np.ndarray) -> bool:
        """Detect if the overall screen is darker than normal (indicating dialogue overlay)"""
        try:
            # Convert to grayscale for analysis
            if len(screenshot.shape) == 3:
                gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            else:
                gray = screenshot
            
            # Calculate average brightness
            avg_brightness = np.mean(gray)
            
            # Calculate percentage of very dark pixels
            very_dark_threshold = 15  # Stricter threshold (was 20)
            very_dark_pixels = np.sum(gray < very_dark_threshold)
            total_pixels = gray.size
            very_dark_percentage = (very_dark_pixels / total_pixels) * 100
            
            print(f"💡 Overall brightness: {avg_brightness:.1f}, Very dark pixels: {very_dark_percentage:.1f}%")
            
            # Much stricter criteria to reduce false positives
            if avg_brightness < 30 and very_dark_percentage > 60:
                print(f"🌚 Overall darkness detected! (brightness: {avg_brightness:.1f}, dark: {very_dark_percentage:.1f}%)")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error in darkness detection: {e}")
            return False
    
    def perform_debug_sequence(self) -> bool:
        """Perform the debug sequence to escape pokecenter dialogue"""
        print("🔧 Starting debug sequence to escape pokecenter dialogue...")
        
        # Step 1: Press S key continuously for specified duration while pressing E multiple times
        print(f"🔧 Step 1: Pressing S continuously for {self.debug_s_key_duration}s while pressing E every {self.debug_e_key_interval}s for {self.debug_e_key_duration}s")
        
        # Start pressing S key
        self.input_manager.press_key('s')
        
        # Press E key multiple times for the specified duration
        e_start_time = time.time()
        while time.time() - e_start_time < self.debug_e_key_duration:
            if self.stop_flag:
                self.input_manager.release_key('s')
                return False
            
            # Press and release E
            self.input_manager.press_key('e')
            if not self.interruptible_sleep(0.1):
                self.input_manager.release_key('e')
                self.input_manager.release_key('s')
                return False
            self.input_manager.release_key('e')
            
            # Wait for next E press
            if not self.interruptible_sleep(self.debug_e_key_interval):
                self.input_manager.release_key('s')
                return False
        
        # Continue pressing S for remaining time if needed
        s_remaining = self.debug_s_key_duration - self.debug_e_key_duration
        if s_remaining > 0:
            if not self.interruptible_sleep(s_remaining):
                self.input_manager.release_key('s')
                return False
        
        # Release S key
        self.input_manager.release_key('s')
        
        print("🔧 Step 2: Waiting 1 second before checking if still in pokecenter...")
        if not self.interruptible_sleep(1.0):
            return False
        
        # Step 2: Check if still in pokecenter
        screenshot = self.capture_game_screen()
        if screenshot is not None:
            if self.detect_pokecenter_dialogue(screenshot):
                print("🔧 Still in pokecenter after debug sequence - stopping Sweet Scent hunt")
                if self.status_callback:
                    self.status_callback('error', 'Player stuck in pokecenter dialogue - hunt stopped')
                return False
            else:
                print("🔧 Successfully escaped pokecenter dialogue!")
                
                # Step 3: Press 7 key to heal
                print("🔧 Step 3: Pressing 7 key to heal before continuing...")
                self.input_manager.press_key('7')
                if not self.interruptible_sleep(0.1):
                    self.input_manager.release_key('7')
                    return False
                self.input_manager.release_key('7')
                
                # Wait for heal animation
                if not self.interruptible_sleep(self.heal_delay):
                    return False
                
                # Step 4: Execute movement macro to return to position
                print("🔧 Step 4: Executing movement macro to return to hunting position...")
                if not self.execute_movement_macro():
                    print("❌ Failed to execute movement macro after debug sequence")
                    return False
                
                print("🔧 Debug sequence completed successfully - continuing hunt")
                return True
        else:
            print("🔧 Could not capture screenshot for verification")
            return False
    
    def check_pokecenter_stuck(self) -> bool:
        """Check if player is stuck in pokecenter dialogue and handle it"""
        if not self.debug_pokecenter_enabled:
            return True  # Continue normally if debug is disabled
        
        current_time = time.time()
        
        # Only check at specified intervals to avoid performance issues
        if current_time - self.debug_last_check_time < self.debug_check_interval:
            return True
        
        self.debug_last_check_time = current_time
        
        print("🔍 Checking for pokecenter dialogue...")
        screenshot = self.capture_game_screen()
        if screenshot is None:
            print("⚠ Could not capture screenshot for pokecenter check")
            return True  # Continue if we can't check
        
        # First check
        if self.detect_pokecenter_dialogue(screenshot):
            print("🏥 Pokecenter dialogue detected - performing second check in 3 seconds...")
            
            # Wait and check again to confirm
            if not self.interruptible_sleep(3.0):
                return False
            
            screenshot = self.capture_game_screen()
            if screenshot is not None and self.detect_pokecenter_dialogue(screenshot):
                print("🏥 Confirmed: Player is stuck in pokecenter dialogue")
                print("🛑 Stopping current Sweet Scent process for debug sequence...")
                
                # Execute debug sequence
                if self.perform_debug_sequence():
                    print("🔧 Debug sequence successful - resetting Sweet Scent counters...")
                    # Reset Sweet Scent usage counter since we healed
                    self.current_uses = 0
                    print("🔄 Sweet Scent PP restored, continuing hunt from current position")
                    return True  # Continue hunt normally from current position
                else:
                    print("❌ Debug sequence failed - stopping Sweet Scent hunt")
                    return False  # Stop hunt completely
            else:
                print("✓ False alarm - player is no longer in pokecenter")
                return True
        else:
            print("✓ No pokecenter dialogue detected")
            return True
    
    def interruptible_sleep(self, duration: float, check_interval: float = 0.1) -> bool:
        """Sleep for duration but check stop flag every check_interval seconds
        Returns True if completed normally, False if interrupted by stop flag"""
        if duration <= 0:
            return True
            
        elapsed = 0.0
        while elapsed < duration:
            if self.stop_flag:
                return False
            
            sleep_time = min(check_interval, duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
        
        return True
    
    def set_movement_macro(self, macro_name: str) -> bool:
        """Set the movement macro to use for positioning"""
        if macro_name and self.macro_exists(macro_name):
            self.selected_macro = macro_name
            print(f"✓ Selected movement macro: {macro_name}")
            return True
        else:
            print(f"❌ Macro '{macro_name}' not found")
            return False
    
    def get_available_macros(self) -> list:
        """Get list of available macros for movement"""
        macro_list = self.macro_manager.get_macro_list()
        return [macro['name'] for macro in macro_list]
    
    def macro_exists(self, macro_name: str) -> bool:
        """Check if a macro exists"""
        available_macros = self.get_available_macros()
        return macro_name in available_macros
    
    def execute_movement_macro(self):
        """Execute the selected movement macro"""
        if not self.selected_macro:
            print("❌ No movement macro selected")
            return False
        
        print(f"🎯 Executing movement macro: {self.selected_macro}")
        print(f"🔧 Debug: stop_flag = {self.stop_flag}, is_hunting = {self.is_hunting}")
        
        # Reset input manager stop flag to ensure macro can execute
        self.input_manager.stop_playback = False
        print(f"🔧 Debug: Reset input_manager.stop_playback to {self.input_manager.stop_playback}")
        
        # Load and play the macro
        try:
            # Find the macro file path by name
            macro_list = self.macro_manager.get_macro_list()
            macro_filepath = None
            for macro_info in macro_list:
                if macro_info['name'] == self.selected_macro:
                    macro_filepath = macro_info['filepath']
                    break
            
            if not macro_filepath:
                print(f"❌ Macro '{self.selected_macro}' not found")
                return False
            
            success, macro_data = self.macro_manager.load_macro(macro_filepath)
            if success and macro_data:
                macro_events = macro_data.get('events', [])
                print(f"▶️ Playing movement macro with {len(macro_events)} events")
                
                # Play macro synchronously (wait for completion)
                completed = threading.Event()
                
                def macro_callback(event_type, data):
                    if event_type == 'complete':
                        completed.set()
                    elif event_type == 'error':
                        print(f"❌ Macro error: {data}")
                        completed.set()
                    elif event_type == 'timeout':
                        print(f"⚠ Macro timeout after {data.get('loop', 1)} cycles")
                        completed.set()
                
                # Use higher timeout and pass it explicitly
                self.input_manager.play_macro(macro_events, speed=1.0, loop_count=1, callback=macro_callback, timeout=90)
                
                # Wait for macro completion with timeout, checking stop flag
                timeout_duration = 100  # 100 second timeout
                check_interval = 0.5  # Check every 0.5 seconds
                elapsed = 0.0
                
                while elapsed < timeout_duration:
                    if self.stop_flag:
                        print("🛑 Movement macro interrupted by stop request")
                        return False
                    
                    if completed.wait(timeout=check_interval):
                        print("✅ Movement macro completed")
                        # Small delay after macro completion, but interruptible
                        self.interruptible_sleep(1.0)
                        return True
                    
                    elapsed += check_interval
                
                print("⚠ Movement macro timed out")
                print("💡 This can happen if the macro contains many mouse movements")
                print("💡 Try using a simpler macro with only keyboard inputs")
                return False
            else:
                print(f"❌ Failed to load macro: {self.selected_macro}")
                return False
                
        except Exception as e:
            print(f"❌ Error executing movement macro: {e}")
            return False
    
    def press_key_with_delay(self, key: str, duration: float = 0.1):
        """Press a key for specified duration"""
        print(f"🎮 Pressing {key.upper()} key")
        self.input_manager.press_key(key)
        time.sleep(duration)
        self.input_manager.release_key(key)
    
    def perform_sweet_scent_sequence(self):
        """Perform the Sweet Scent move and initial encounter handling"""
        print(f"🌸 Using Sweet Scent (Use {self.current_uses + 1}/{self.sweet_scent_uses})")
        
        # Press Q for Sweet Scent
        self.press_key_with_delay('q', 0.1)
        
        if self.stop_flag:
            return False
        
        # Wait for Sweet Scent animation
        print(f"⏳ Waiting {self.sweet_scent_animation_delay}s for Sweet Scent animation")
        if not self.interruptible_sleep(self.sweet_scent_animation_delay):
            return False
        
        # Press E initial times with intervals
        print(f"🎮 Pressing E {self.initial_e_presses} times (interval: {self.initial_e_interval}s)")
        for i in range(self.initial_e_presses):
            if self.stop_flag:
                return False
            self.press_key_with_delay('e', 0.1)
            if i < self.initial_e_presses - 1:  # Don't wait after last press
                if not self.interruptible_sleep(self.initial_e_interval):
                    return False
        
        # Wait after all initial E presses are complete
        if self.post_e_delay > 0:
            print(f"⏳ Waiting {self.post_e_delay}s after initial E presses")
            if not self.interruptible_sleep(self.post_e_delay):
                return False
        
        return True
    
    def perform_encounter_loop(self):
        """Perform the encounter loop for specified duration (E+E or X+E based on setting)"""
        loop_type = "E+E" if self.use_e_plus_e else "X+E"
        print(f"🔄 Starting {loop_type} encounter loop for {self.encounter_loop_duration}s")
        
        start_time = time.time()
        loop_count = 0
        
        while time.time() - start_time < self.encounter_loop_duration:
            if self.stop_flag or self.is_paused:
                break
            
            loop_count += 1
            
            if self.use_e_plus_e:
                # E+E loop
                self.press_key_with_delay('e', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    break
                
                if self.stop_flag or self.is_paused:
                    break
                
                self.press_key_with_delay('e', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    break
            else:
                # X+E loop (default)
                self.press_key_with_delay('x', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    break
                
                if self.stop_flag or self.is_paused:
                    break
                
                self.press_key_with_delay('e', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    break
            
            # Update status occasionally
            if loop_count % 10 == 0:
                elapsed = time.time() - start_time
                remaining = self.encounter_loop_duration - elapsed
                print(f"🔄 {loop_type} loop: {remaining:.1f}s remaining")
        
        if self.stop_flag:
            print(f"🛑 {loop_type} encounter loop stopped by user ({loop_count} cycles)")
            return False
        else:
            print(f"✅ {loop_type} encounter loop completed ({loop_count} cycles)")
            return True
    
    def perform_heal_sequence(self):
        """Perform healing sequence to recover PP"""
        print("💊 Performing heal sequence (PP recovery)")
        self.heal_cycles += 1
        
        # Press 7 for heal
        self.press_key_with_delay('7', 0.1)
        
        if self.stop_flag:
            return False
        
        # Wait for heal animation/menu
        print(f"⏳ Waiting {self.heal_delay}s for heal animation")
        if not self.interruptible_sleep(self.heal_delay):
            return False
        
        print(f"✅ Heal sequence completed (Cycle #{self.heal_cycles})")
        return True
    
    def sweet_scent_hunt_loop(self):
        """Main Sweet Scent hunting loop"""
        print("🌸 Sweet Scent Hunt started!")
        self.hunt_start_time = time.time()
        
        # Add initial delay if started without macro to ensure game window is focused
        if getattr(self, 'started_without_macro', False):
            print(f"⏳ Waiting {self.initial_focus_delay}s for game window focus...")
            if not self.interruptible_sleep(self.initial_focus_delay):
                return
        
        while self.is_hunting and not self.stop_flag:
            try:
                # Check if we need to heal (no Sweet Scent uses left)
                if self.current_uses >= self.sweet_scent_uses:
                    print(f"🩹 Sweet Scent PP depleted ({self.current_uses}/{self.sweet_scent_uses} uses)")
                    
                    # Perform heal sequence
                    if not self.perform_heal_sequence():
                        break
                    
                    # Execute movement macro to return to position
                    if not self.execute_movement_macro():
                        print("❌ Failed to execute movement macro after heal")
                        break
                    
                    # Reset Sweet Scent counter
                    self.current_uses = 0
                    print("🔄 Sweet Scent PP restored, resuming hunt")
                
                # Check for pause
                if self.is_paused:
                    if not self.interruptible_sleep(0.5):
                        break
                    continue
                
                # Check for pokecenter dialogue (debug feature)
                if not self.check_pokecenter_stuck():
                    break
                
                # Perform Sweet Scent sequence
                if not self.perform_sweet_scent_sequence():
                    break
                
                if self.stop_flag:
                    break
                
                # Perform encounter loop
                if not self.perform_encounter_loop():
                    break
                
                # Increment Sweet Scent usage
                self.current_uses += 1
                self.sweet_scent_cycles += 1
                
                # Update statistics
                if self.status_callback:
                    elapsed = time.time() - self.hunt_start_time
                    self.status_callback('hunting', {
                        'sweet_scent_cycles': self.sweet_scent_cycles,
                        'current_uses': self.current_uses,
                        'max_uses': self.sweet_scent_uses,
                        'heal_cycles': self.heal_cycles,
                        'time': elapsed
                    })
                
                print(f"📊 Sweet Scent cycle completed ({self.current_uses}/{self.sweet_scent_uses} uses)")
                
                # Pause between cycles
                if self.cycle_pause > 0:
                    print(f"⏳ Cycle pause: {self.cycle_pause}s")
                    if not self.interruptible_sleep(self.cycle_pause):
                        break
                
            except Exception as e:
                print(f"❌ Error in Sweet Scent hunt loop: {e}")
                if self.status_callback:
                    self.status_callback('error', str(e))
                break
        
        # Hunt finished
        self.total_hunt_time += time.time() - self.hunt_start_time if self.hunt_start_time else 0
        print(f"🏁 Sweet Scent Hunt stopped. Cycles: {self.sweet_scent_cycles}, Heal cycles: {self.heal_cycles}")
        
        if self.status_callback:
            self.status_callback('hunt_finished', {
                'sweet_scent_cycles': self.sweet_scent_cycles,
                'heal_cycles': self.heal_cycles,
                'total_time': self.total_hunt_time
            })
    
    def start_hunt(self) -> bool:
        """Start the Sweet Scent hunt"""
        if self.is_hunting:
            print("⚠ Sweet Scent hunt already in progress")
            return False
        
        if not self.window_manager.is_game_running():
            print("❌ Cannot start hunt - game not running")
            print("💡 Try using 'Select PokeMMO Window' in Auto Hunt tab first")
            return False
        
        if not self.selected_macro:
            print("❌ Cannot start hunt - no movement macro selected")
            return False
        
        print("🌸 Starting Sweet Scent hunt...")
        print(f"📋 Configuration:")
        print(f"   Movement macro: {self.selected_macro}")
        print(f"   Sweet Scent uses per cycle: {self.sweet_scent_uses}")
        print(f"   Animation delay: {self.sweet_scent_animation_delay}s")
        print(f"   Encounter loop duration: {self.encounter_loop_duration}s")
        
        # Execute initial movement macro
        print("🎯 Attempting to execute initial movement macro...")
        if not self.execute_movement_macro():
            print("❌ Failed to execute initial movement macro")
            print("💡 Make sure you're positioned correctly before starting")
            print("💡 Or try starting without a movement macro (position manually)")
            return False
        
        # Reset statistics and flags FIRST
        self.stop_flag = False  # Reset stop flag immediately
        self.is_hunting = True
        self.is_paused = False
        self.encounters_found = 0
        self.sweet_scent_cycles = 0
        self.heal_cycles = 0
        self.current_uses = 0
        self.started_without_macro = False  # Flag for initial delay
        
        print(f"🔧 Debug: stop_flag reset to {self.stop_flag}, is_hunting set to {self.is_hunting}")
        
        # Start hunt thread
        self.hunt_thread = threading.Thread(target=self.sweet_scent_hunt_loop, daemon=True)
        self.hunt_thread.start()
        
        return True
    
    def start_hunt_no_macro(self) -> bool:
        """Start the Sweet Scent hunt without executing movement macro"""
        if self.is_hunting:
            print("⚠ Sweet Scent hunt already in progress")
            return False
        
        if not self.window_manager.is_game_running():
            print("❌ Cannot start hunt - game not running")
            print("💡 Try using 'Select PokeMMO Window' button first")
            return False
        
        print("🌸 Starting Sweet Scent hunt from current position...")
        print(f"📋 Configuration:")
        print(f"   Sweet Scent uses per cycle: {self.sweet_scent_uses}")
        print(f"   Animation delay: {self.sweet_scent_animation_delay}s")
        print(f"   Encounter loop duration: {self.encounter_loop_duration}s")
        print(f"   Initial focus delay: {self.initial_focus_delay}s")
        print("💡 Make sure you're positioned in the right location!")
        
        # Reset statistics and flags FIRST
        self.stop_flag = False  # Reset stop flag immediately
        self.is_hunting = True
        self.is_paused = False
        self.encounters_found = 0
        self.sweet_scent_cycles = 0
        self.heal_cycles = 0
        self.current_uses = 0
        self.started_without_macro = True  # Flag to add initial delay
        
        print(f"🔧 Debug: stop_flag reset to {self.stop_flag}, is_hunting set to {self.is_hunting}")
        
        # Start hunt thread
        self.hunt_thread = threading.Thread(target=self.sweet_scent_hunt_loop, daemon=True)
        self.hunt_thread.start()
        
        return True
    
    def stop_hunt(self):
        """Stop the Sweet Scent hunt"""
        if not self.is_hunting:
            return
        
        print("🛑 Stopping Sweet Scent hunt...")
        self.is_hunting = False
        self.stop_flag = True
        
        # Wait for thread to finish
        if self.hunt_thread and threading.current_thread() != self.hunt_thread:
            self.hunt_thread.join(timeout=3.0)
        
        # Reset all state flags to ensure clean restart
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        self.hunt_thread = None
        
        # Reset input manager stop flag as well
        if hasattr(self.input_manager, 'stop_playback'):
            self.input_manager.stop_playback = False
        
        print("✅ Sweet Scent hunt stopped and state reset")
    
    def force_reset_state(self):
        """Force reset all state flags - useful for fixing 'hunt in progress' issues"""
        print("🔧 Force resetting Sweet Scent engine state...")
        
        # Stop any running hunt
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        
        # Reset thread
        self.hunt_thread = None
        
        # Reset input manager flags
        if hasattr(self.input_manager, 'stop_playback'):
            self.input_manager.stop_playback = False
        
        # Reset debug timing
        self.debug_last_check_time = 0
        
        print("✅ Sweet Scent engine state force reset completed")
    
    def pause_hunt(self):
        """Pause the Sweet Scent hunt"""
        self.is_paused = True
        print("⏸ Sweet Scent hunt paused")
    
    def resume_hunt(self):
        """Resume the Sweet Scent hunt"""
        self.is_paused = False
        print("▶️ Sweet Scent hunt resumed")
    
    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def set_encounter_callback(self, callback):
        """Set callback for encounter events"""
        self.encounter_callback = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get Sweet Scent hunting statistics"""
        current_time = time.time() - self.hunt_start_time if self.hunt_start_time and self.is_hunting else 0
        
        return {
            'sweet_scent_cycles': self.sweet_scent_cycles,
            'current_uses': self.current_uses,
            'max_uses': self.sweet_scent_uses,
            'heal_cycles': self.heal_cycles,
            'hunt_time': current_time,
            'total_hunt_time': self.total_hunt_time,
            'is_hunting': self.is_hunting,
            'is_paused': self.is_paused,
            'selected_macro': self.selected_macro
        }
    
    def update_configuration(self, config: Dict[str, Any]):
        """Update Sweet Scent configuration"""
        if 'sweet_scent_uses' in config:
            self.sweet_scent_uses = max(1, min(10, config['sweet_scent_uses']))
        
        if 'sweet_scent_animation_delay' in config:
            self.sweet_scent_animation_delay = max(0.5, min(60.0, config['sweet_scent_animation_delay']))  # Increased from 15.0 to 60.0
        
        if 'initial_e_presses' in config:
            self.initial_e_presses = max(0, min(10, config['initial_e_presses']))
        
        if 'initial_e_interval' in config:
            self.initial_e_interval = max(0.1, min(2.0, config['initial_e_interval']))
        
        if 'encounter_loop_duration' in config:
            self.encounter_loop_duration = max(1.0, min(300.0, config['encounter_loop_duration']))  # Increased from 60.0 to 300.0
        
        if 'encounter_loop_interval' in config:
            self.encounter_loop_interval = max(0.1, min(2.0, config['encounter_loop_interval']))
        
        if 'heal_delay' in config:
            self.heal_delay = max(0.5, min(60.0, config['heal_delay']))  # Increased from 10.0 to 60.0
        
        if 'cycle_pause' in config:
            self.cycle_pause = max(0.0, min(60.0, config['cycle_pause']))  # Increased from 10.0 to 60.0
        
        if 'initial_focus_delay' in config:
            self.initial_focus_delay = max(0.5, min(60.0, config['initial_focus_delay']))  # Increased from 10.0 to 60.0
        
        if 'post_e_delay' in config:
            self.post_e_delay = max(0.0, min(60.0, config['post_e_delay']))  # Increased from 10.0 to 60.0
        
        if 'use_e_plus_e' in config:
            self.use_e_plus_e = config['use_e_plus_e']
        
        # Debug configuration
        if 'debug_pokecenter_enabled' in config:
            self.debug_pokecenter_enabled = config['debug_pokecenter_enabled']
        
        if 'debug_s_key_duration' in config:
            self.debug_s_key_duration = max(0.5, min(10.0, config['debug_s_key_duration']))
        
        if 'debug_e_key_duration' in config:
            self.debug_e_key_duration = max(0.5, min(10.0, config['debug_e_key_duration']))
        
        if 'debug_e_key_interval' in config:
            self.debug_e_key_interval = max(0.1, min(2.0, config['debug_e_key_interval']))
        
        if 'debug_check_interval' in config:
            self.debug_check_interval = max(10.0, min(300.0, config['debug_check_interval']))
        
        print("✅ Sweet Scent configuration updated")
    
    def ensure_presets_directory(self):
        """Ensure the presets directory exists"""
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
            print(f"📁 Created presets directory: {self.presets_dir}")
    
    def save_preset(self, preset_name: str) -> bool:
        """Save current configuration as a preset"""
        try:
            self.ensure_presets_directory()
            
            preset_config = {
                'sweet_scent_uses': self.sweet_scent_uses,
                'sweet_scent_animation_delay': self.sweet_scent_animation_delay,
                'initial_e_presses': self.initial_e_presses,
                'initial_e_interval': self.initial_e_interval,
                'post_e_delay': self.post_e_delay,
                'encounter_loop_duration': self.encounter_loop_duration,
                'encounter_loop_interval': self.encounter_loop_interval,
                'heal_delay': self.heal_delay,
                'cycle_pause': self.cycle_pause,
                'initial_focus_delay': self.initial_focus_delay,
                'use_e_plus_e': self.use_e_plus_e,
                'selected_macro': self.selected_macro,
                'debug_pokecenter_enabled': self.debug_pokecenter_enabled,
                'debug_s_key_duration': self.debug_s_key_duration,
                'debug_e_key_duration': self.debug_e_key_duration,
                'debug_e_key_interval': self.debug_e_key_interval,
                'debug_check_interval': self.debug_check_interval
            }
            
            preset_path = os.path.join(self.presets_dir, f"{preset_name}.json")
            with open(preset_path, 'w') as f:
                json.dump(preset_config, f, indent=2)
            
            print(f"💾 Saved preset '{preset_name}' to {preset_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save preset '{preset_name}': {e}")
            return False
    
    def load_preset(self, preset_name: str) -> bool:
        """Load a preset configuration"""
        try:
            preset_path = os.path.join(self.presets_dir, f"{preset_name}.json")
            
            if not os.path.exists(preset_path):
                print(f"❌ Preset '{preset_name}' not found")
                return False
            
            with open(preset_path, 'r') as f:
                preset_config = json.load(f)
            
            # Apply the preset configuration
            self.update_configuration(preset_config)
            
            # Set the macro if it exists
            if 'selected_macro' in preset_config and preset_config['selected_macro']:
                self.set_movement_macro(preset_config['selected_macro'])
            
            print(f"📥 Loaded preset '{preset_name}' from {preset_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load preset '{preset_name}': {e}")
            return False
    
    def delete_preset(self, preset_name: str) -> bool:
        """Delete a preset"""
        try:
            preset_path = os.path.join(self.presets_dir, f"{preset_name}.json")
            
            if not os.path.exists(preset_path):
                print(f"❌ Preset '{preset_name}' not found")
                return False
            
            os.remove(preset_path)
            print(f"🗑️ Deleted preset '{preset_name}'")
            return True
            
        except Exception as e:
            print(f"❌ Failed to delete preset '{preset_name}': {e}")
            return False
    
    def get_preset_list(self) -> list:
        """Get list of available presets"""
        try:
            self.ensure_presets_directory()
            presets = []
            
            for filename in os.listdir(self.presets_dir):
                if filename.endswith('.json'):
                    preset_name = filename[:-5]  # Remove .json extension
                    presets.append(preset_name)
            
            return sorted(presets)
            
        except Exception as e:
            print(f"❌ Failed to get preset list: {e}")
            return [] 