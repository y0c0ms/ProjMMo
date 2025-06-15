"""
PP-Based Auto Hunt System
Automates hunting with PP management and macro integration
"""
import threading
import time
import os
import json
import cv2
import numpy as np
from PIL import Image, ImageGrab
from typing import Dict, Any, Optional, Callable


class PPAutoHuntEngine:
    """Engine for automating hunting with PP management"""
    
    def __init__(self, window_manager, input_manager, macro_manager, template_manager):
        self.window_manager = window_manager
        self.input_manager = input_manager
        self.macro_manager = macro_manager
        self.template_manager = template_manager
        
        # Create an AutoHuntEngine instance for battle detection
        from auto_hunt import AutoHuntEngine
        self.auto_hunt_engine = AutoHuntEngine(window_manager, input_manager)
        
        # Hunt state
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        self.hunt_thread = None
        
        # PP Hunt configuration
        self.max_encounters = 20  # Maximum encounters before needing to heal
        self.current_encounters = 0
        self.selected_macro = None
        
        # Movement configuration
        self.movement_keys = ['a', 'd']  # Keys to press for movement (A to D)
        self.movement_interval = 0.5  # Interval between A and D presses
        self.key_hold_duration = 1.0  # How long to hold each key (in seconds)
        
        # Battle configuration
        self.initial_e_presses = 6  # Number of initial E presses
        self.battle_key_interval = 0.2  # 0.2s delay between E presses
        self.post_e_delay = 8.5  # Delay after initial E presses before starting loop
        self.encounter_loop_duration = 12.0  # Duration for E+E or X+E loop
        self.encounter_loop_type = 'e+e'  # 'e+e' or 'x+e'
        self.encounter_loop_interval = 0.3  # Interval between key combinations in loop
        
        # Healing configuration
        self.heal_key = '7'
        self.heal_delay = 3.0  # Wait time after pressing heal key
        
        # Statistics
        self.encounters_found = 0
        self.hunt_cycles = 0
        self.heal_cycles = 0
        self.hunt_start_time = None
        self.total_hunt_time = 0
        
        # Callbacks
        self.status_callback = None
        self.encounter_callback = None
        
        # Preset management
        self.presets_dir = "auto_hunt_presets"
        self.ensure_presets_directory()
        
    def interruptible_sleep(self, duration: float, check_interval: float = 0.1) -> bool:
        """Sleep for duration but check stop flag every check_interval seconds
        Returns True if completed normally, False if interrupted by stop flag"""
        if duration <= 0:
            return True
            
        elapsed = 0.0
        while elapsed < duration:
            if self.stop_flag or self.is_paused:
                return False
            
            sleep_time = min(check_interval, duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
        
        return True
    
    def set_movement_macro(self, macro_name: str) -> bool:
        """Set the movement macro for returning to hunt position"""
        if not macro_name:
            self.selected_macro = None
            return False
        
        if self.macro_manager.get_macro_list():
            for macro in self.macro_manager.get_macro_list():
                if macro['name'] == macro_name:
                    self.selected_macro = macro_name
                    print(f"✓ Selected movement macro: {macro_name}")
                    return True
        
        print(f"❌ Macro '{macro_name}' not found")
        return False
    
    def get_available_macros(self) -> list:
        """Get list of available macros"""
        return self.macro_manager.get_macro_list()
    
    def macro_exists(self, macro_name: str) -> bool:
        """Check if a macro exists"""
        return any(macro['name'] == macro_name for macro in self.get_available_macros())
    
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
            success, macro_data = self.macro_manager.load_macro(self.selected_macro)
            if not success:
                print(f"❌ Failed to load macro: {self.selected_macro}")
                return False
            
            macro_events = macro_data.get('events', [])
            if not macro_events:
                print(f"❌ No events found in macro: {self.selected_macro}")
                return False
            
            print(f"▶️ Playing movement macro with {len(macro_events)} events")
            
            # Set up completion tracking
            completed = threading.Event()
            
            def macro_callback(event_type, data):
                if event_type in ['complete', 'stopped', 'timeout']:
                    completed.set()
            
            # Use higher timeout and pass it explicitly
            self.input_manager.play_macro(macro_events, speed=1.0, loop_count=1, callback=macro_callback, timeout=90)
            
            # Wait for macro completion with timeout
            if completed.wait(timeout=100):  # 100 second timeout
                print("✅ Movement macro completed")
                if not self.interruptible_sleep(1.0):  # Small delay after macro completion
                    return False
                return True
            else:
                print("⚠ Movement macro timed out")
                print("💡 This can happen if the macro contains many mouse movements")
                print("💡 Try using a simpler macro with only keyboard inputs")
                return False
                
        except Exception as e:
            print(f"❌ Error executing movement macro: {e}")
            return False
    
    def press_key_with_delay(self, key: str, duration: float = 0.1):
        """Press and release a key with specified duration"""
        self.input_manager.press_key(key)
        self.interruptible_sleep(duration)
        self.input_manager.release_key(key)
    
    def perform_movement_cycle(self) -> bool:
        """Perform A to D movement until battle menu is detected"""
        print(f"🚶 Starting movement cycle (A→D pattern, {self.key_hold_duration}s hold duration)")
        
        # Clean up any leftover screenshots from previous cycles
        self.auto_hunt_engine.cleanup_encounter_screenshots()
        
        movement_index = 0
        cycle_count = 0
        
        while not self.stop_flag and not self.is_paused:
            # Check for beforeMenu template first
            screenshot = self.auto_hunt_engine.capture_full_game_screen()
            if screenshot is not None:
                # Check for beforeMenu template
                beforemenu_detected, _ = self.auto_hunt_engine.detect_template(screenshot, "beforeMenu")
                if beforemenu_detected:
                    print("🎬 Pre-battle screen detected! Waiting 2 seconds before checking for battle menu...")
                    if not self.interruptible_sleep(2.0):
                        return False
                    
                    # Now check for actual battle menu
                    screenshot = self.auto_hunt_engine.capture_full_game_screen()
                    if screenshot is not None and self.auto_hunt_engine.detect_battle_menu(screenshot):
                        print("⚔️ Battle menu confirmed after beforeMenu detection!")
                        return True
                    else:
                        print("⚠️ No battle menu found after beforeMenu - continuing movement")
                
                # Regular battle menu detection (fallback)
                if self.auto_hunt_engine.detect_battle_menu(screenshot):
                    print("⚔️ Battle menu detected directly! Stopping movement")
                    return True
            
            # Press and hold current movement key for specified duration
            current_key = self.movement_keys[movement_index]
            print(f"🎮 Holding {current_key.upper()} key for {self.key_hold_duration}s")
            
            # Press key
            self.input_manager.press_key(current_key)
            
            # Hold for specified duration with interruptible sleep
            if not self.interruptible_sleep(self.key_hold_duration):
                # Release key if interrupted
                self.input_manager.release_key(current_key)
                return False
            
            # Release key
            self.input_manager.release_key(current_key)
            print(f"✓ Released {current_key.upper()} key")
            
            # Check for beforeMenu and battle menu after movement
            screenshot = self.auto_hunt_engine.capture_full_game_screen()
            if screenshot is not None:
                # Check for beforeMenu template
                beforemenu_detected, _ = self.auto_hunt_engine.detect_template(screenshot, "beforeMenu")
                if beforemenu_detected:
                    print("🎬 Pre-battle screen detected after movement! Waiting 2 seconds...")
                    if not self.interruptible_sleep(2.0):
                        return False
                    
                    # Now check for actual battle menu
                    screenshot = self.auto_hunt_engine.capture_full_game_screen()
                    if screenshot is not None and self.auto_hunt_engine.detect_battle_menu(screenshot):
                        print("⚔️ Battle menu confirmed after post-movement beforeMenu detection!")
                        return True
                    else:
                        print("⚠️ No battle menu found after post-movement beforeMenu - continuing")
                
                # Regular battle menu detection (fallback)
                if self.auto_hunt_engine.detect_battle_menu(screenshot):
                    print("⚔️ Battle menu detected after movement! Stopping")
                    return True
            
            # Wait between key presses
            if not self.interruptible_sleep(self.movement_interval):
                return False
            
            # Alternate between A and D
            movement_index = (movement_index + 1) % len(self.movement_keys)
            cycle_count += 1
            
            # Add some status output every 10 cycles (reduced frequency since keys hold longer)
            if cycle_count % 10 == 0:
                print(f"🔄 Movement cycle {cycle_count} - still searching for battle...")
        
        return False
    
    def perform_battle_sequence(self) -> bool:
        """Perform Sweet Scent-style battle sequence with initial E presses + loop"""
        print("⚔️ Starting battle sequence")
        
        # Phase 1: Initial E presses
        print(f"🎮 Pressing E {self.initial_e_presses} times (interval: {self.battle_key_interval}s)")
        for i in range(self.initial_e_presses):
            if self.stop_flag or self.is_paused:
                return False
            
            print(f"🎮 Pressing E key ({i+1}/{self.initial_e_presses})")
            self.press_key_with_delay('e', 0.1)
            
            # Wait between E presses (except after the last one)
            if i < self.initial_e_presses - 1:
                if not self.interruptible_sleep(self.battle_key_interval):
                    return False
        
        # Phase 2: Post-E delay
        if self.post_e_delay > 0:
            print(f"⏳ Waiting {self.post_e_delay}s after initial E presses")
            if not self.interruptible_sleep(self.post_e_delay):
                return False
        
        # Phase 3: Encounter loop (E+E or X+E)
        print(f"🔄 Starting {self.encounter_loop_type.upper()} encounter loop for {self.encounter_loop_duration}s")
        loop_start_time = time.time()
        loop_cycles = 0
        
        while not self.stop_flag and not self.is_paused:
            elapsed_time = time.time() - loop_start_time
            remaining_time = self.encounter_loop_duration - elapsed_time
            
            if remaining_time <= 0:
                break
            
            # Check if battle menu is gone
            screenshot = self.auto_hunt_engine.capture_full_game_screen()
            if screenshot is None or not self.auto_hunt_engine.detect_battle_menu(screenshot):
                print("✅ Battle menu no longer detected during loop - battle complete")
                break
            
            loop_cycles += 1
            
            # Execute the encounter loop sequence
            if self.encounter_loop_type == 'e+e':
                # E + E sequence
                print("🎮 Pressing E key")
                self.press_key_with_delay('e', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    return False
                
                print("🎮 Pressing E key")
                self.press_key_with_delay('e', 0.1)
                
            elif self.encounter_loop_type == 'x+e':
                # X + E sequence
                print("🎮 Pressing X key")
                self.press_key_with_delay('x', 0.1)
                if not self.interruptible_sleep(self.encounter_loop_interval):
                    return False
                
                print("🎮 Pressing E key")
                self.press_key_with_delay('e', 0.1)
            
            # Wait between combinations
            if not self.interruptible_sleep(self.encounter_loop_interval):
                return False
            
            # Show progress every 20 cycles
            if loop_cycles % 20 == 0:
                print(f"🔄 {self.encounter_loop_type.upper()} loop: {remaining_time:.1f}s remaining")
        
        print(f"✅ {self.encounter_loop_type.upper()} encounter loop completed ({loop_cycles} cycles)")
        
        # Clean up encounter screenshots to save disk space
        self.auto_hunt_engine.cleanup_encounter_screenshots()
        
        # Mark encounter as completed
        self.encounters_found += 1
        self.current_encounters += 1
        print(f"📊 Encounter completed! Total: {self.encounters_found}, Current PP cycle: {self.current_encounters}/{self.max_encounters}")
        
        return True
    
    def perform_heal_sequence(self) -> bool:
        """Perform healing sequence to recover PP"""
        print("💊 Performing heal sequence (PP recovery)")
        self.heal_cycles += 1
        
        # Press heal key
        print(f"🎮 Pressing {self.heal_key} key for heal")
        self.press_key_with_delay(self.heal_key, 0.1)
        
        if self.stop_flag:
            return False
        
        # Wait for heal animation
        print(f"⏳ Waiting {self.heal_delay}s for heal animation")
        if not self.interruptible_sleep(self.heal_delay):
            return False
        
        print(f"✅ Heal sequence completed (Cycle #{self.heal_cycles})")
        return True
    
    def auto_hunt_loop(self):
        """Main auto hunt loop"""
        print("🏹 Starting PP-based auto hunt loop")
        self.hunt_start_time = time.time()
        
        try:
            while not self.stop_flag and self.is_hunting:
                # Check for pause
                if self.is_paused:
                    if not self.interruptible_sleep(0.5):
                        break
                    continue
                
                # Check if we need to heal (max encounters reached)
                if self.current_encounters >= self.max_encounters:
                    print(f"🩹 PP depleted ({self.current_encounters}/{self.max_encounters} encounters)")
                    
                    # Perform heal sequence
                    if not self.perform_heal_sequence():
                        break
                    
                    # Execute movement macro to return to position
                    if not self.execute_movement_macro():
                        print("❌ Failed to execute movement macro after heal")
                        break
                    
                    # Reset encounter counter
                    self.current_encounters = 0
                    self.hunt_cycles += 1
                    print("🔄 PP restored, resuming hunt")
                
                # Perform movement cycle until battle is detected
                if not self.perform_movement_cycle():
                    break
                
                # Perform battle sequence
                if not self.perform_battle_sequence():
                    break
                
                # Small delay before next cycle
                if not self.interruptible_sleep(0.5):
                    break
                    
        except Exception as e:
            print(f"❌ Error in hunt loop: {e}")
        
        finally:
            # Calculate total time
            if self.hunt_start_time:
                self.total_hunt_time += time.time() - self.hunt_start_time
            
            print("🏁 PP Auto Hunt stopped")
            print(f"📊 Final stats: {self.encounters_found} encounters, {self.heal_cycles} heals, {self.hunt_cycles} cycles")
            
            # Notify status callback
            if self.status_callback:
                self.status_callback('hunt_finished', {
                    'encounters_found': self.encounters_found,
                    'heal_cycles': self.heal_cycles,
                    'hunt_cycles': self.hunt_cycles,
                    'total_time': self.total_hunt_time
                })
    
    def start_hunt(self) -> bool:
        """Start the PP-based auto hunt"""
        if self.is_hunting:
            print("⚠ PP Auto Hunt already in progress")
            return False
        
        if not self.selected_macro:
            print("❌ No movement macro selected")
            return False
        
        if not self.window_manager.is_game_running():
            print("❌ PokeMMO window not found")
            return False
        
        print("🏹 Starting PP-based auto hunt...")
        print("📋 Configuration:")
        print(f"   Movement macro: {self.selected_macro}")
        print(f"   Max encounters per cycle: {self.max_encounters}")
        print(f"   Battle sequence: {self.initial_e_presses} E presses + {self.encounter_loop_type.upper()} loop ({self.encounter_loop_duration}s)")
        print(f"   Movement: {' to '.join([k.upper() for k in self.movement_keys])}")
        
        # Reset statistics and flags
        self.stop_flag = False
        self.is_hunting = True
        self.is_paused = False
        self.encounters_found = 0
        self.hunt_cycles = 0
        self.heal_cycles = 0
        self.current_encounters = 0
        
        print(f"🔧 Debug: stop_flag reset to {self.stop_flag}, is_hunting set to {self.is_hunting}")
        
        # Execute initial movement macro
        print("🎯 Attempting to execute initial movement macro...")
        if not self.execute_movement_macro():
            print("❌ Failed to execute initial movement macro")
            self.is_hunting = False
            return False
        
        # Start hunt thread
        self.hunt_thread = threading.Thread(target=self.auto_hunt_loop, daemon=True)
        self.hunt_thread.start()
        
        print("🏹 PP Auto Hunt started!")
        return True
    
    def start_hunt_no_macro(self) -> bool:
        """Start hunt without initial movement macro (from current position)"""
        if self.is_hunting:
            print("⚠ PP Auto Hunt already in progress")
            return False
        
        if not self.window_manager.is_game_running():
            print("❌ PokeMMO window not found")
            return False
        
        print("🏹 Starting PP-based auto hunt from current position...")
        print("📋 Configuration:")
        print(f"   Movement macro: {self.selected_macro or 'None (starting from current position)'}")
        print(f"   Max encounters per cycle: {self.max_encounters}")
        print(f"   Battle sequence: {self.initial_e_presses} E presses + {self.encounter_loop_type.upper()} loop ({self.encounter_loop_duration}s)")
        
        # Reset statistics and flags
        self.stop_flag = False
        self.is_hunting = True
        self.is_paused = False
        self.encounters_found = 0
        self.hunt_cycles = 0
        self.heal_cycles = 0
        self.current_encounters = 0
        self.started_without_macro = True
        
        print(f"🔧 Debug: stop_flag reset to {self.stop_flag}, is_hunting set to {self.is_hunting}")
        
        # Start hunt thread
        self.hunt_thread = threading.Thread(target=self.auto_hunt_loop, daemon=True)
        self.hunt_thread.start()
        
        print("🏹 PP Auto Hunt started from current position!")
        return True
    
    def stop_hunt(self):
        """Stop the PP-based auto hunt"""
        if not self.is_hunting:
            return
        
        print("🛑 Stopping PP Auto Hunt...")
        self.is_hunting = False
        self.stop_flag = True
        
        # Wait for thread to finish
        if self.hunt_thread and threading.current_thread() != self.hunt_thread:
            self.hunt_thread.join(timeout=3.0)
        
        # Clean up any remaining screenshots
        self.auto_hunt_engine.cleanup_encounter_screenshots()
        
        # Reset all state flags to ensure clean restart
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        self.hunt_thread = None
        
        # Reset input manager stop flag as well
        if hasattr(self.input_manager, 'stop_playback'):
            self.input_manager.stop_playback = False
        
        print("✅ PP Auto Hunt stopped and state reset")
    
    def force_reset_state(self):
        """Force reset all state flags - useful for fixing 'hunt in progress' issues"""
        print("🔧 Force resetting PP Auto Hunt engine state...")
        
        # Clean up any remaining screenshots
        self.auto_hunt_engine.cleanup_encounter_screenshots()
        
        # Stop any running hunt
        self.is_hunting = False
        self.is_paused = False
        self.stop_flag = False
        
        # Reset thread
        self.hunt_thread = None
        
        # Reset input manager flags
        if hasattr(self.input_manager, 'stop_playback'):
            self.input_manager.stop_playback = False
        
        print("✅ PP Auto Hunt engine state force reset completed")
    
    def pause_hunt(self):
        """Pause the PP-based auto hunt"""
        self.is_paused = True
        print("⏸ PP Auto Hunt paused")
    
    def resume_hunt(self):
        """Resume the PP-based auto hunt"""
        self.is_paused = False
        print("▶️ PP Auto Hunt resumed")
    
    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def set_encounter_callback(self, callback):
        """Set callback for encounter events"""
        self.encounter_callback = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get auto hunt statistics"""
        current_time = time.time() - self.hunt_start_time if self.hunt_start_time and self.is_hunting else 0
        
        return {
            'encounters_found': self.encounters_found,
            'current_encounters': self.current_encounters,
            'max_encounters': self.max_encounters,
            'hunt_cycles': self.hunt_cycles,
            'heal_cycles': self.heal_cycles,
            'hunt_time': current_time,
            'total_hunt_time': self.total_hunt_time,
            'is_hunting': self.is_hunting,
            'is_paused': self.is_paused,
            'selected_macro': self.selected_macro
        }
    
    def update_configuration(self, config: Dict[str, Any]):
        """Update auto hunt configuration"""
        if 'max_encounters' in config:
            self.max_encounters = max(1, min(100, config['max_encounters']))
        
        if 'movement_interval' in config:
            self.movement_interval = max(0.1, min(5.0, config['movement_interval']))
        
        if 'key_hold_duration' in config:
            self.key_hold_duration = max(0.1, min(10.0, config['key_hold_duration']))
        
        if 'initial_e_presses' in config:
            self.initial_e_presses = max(1, min(20, config['initial_e_presses']))
        
        if 'battle_key_interval' in config:
            self.battle_key_interval = max(0.1, min(2.0, config['battle_key_interval']))
        
        if 'post_e_delay' in config:
            self.post_e_delay = max(0.0, min(30.0, config['post_e_delay']))
        
        if 'encounter_loop_duration' in config:
            self.encounter_loop_duration = max(1.0, min(60.0, config['encounter_loop_duration']))
        
        if 'encounter_loop_type' in config:
            if config['encounter_loop_type'] in ['e+e', 'x+e']:
                self.encounter_loop_type = config['encounter_loop_type']
        
        if 'encounter_loop_interval' in config:
            self.encounter_loop_interval = max(0.1, min(2.0, config['encounter_loop_interval']))
        
        if 'heal_delay' in config:
            self.heal_delay = max(0.5, min(60.0, config['heal_delay']))
        
        print("✅ PP Auto Hunt configuration updated")
    
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
                'max_encounters': self.max_encounters,
                'movement_interval': self.movement_interval,
                'key_hold_duration': self.key_hold_duration,
                'initial_e_presses': self.initial_e_presses,
                'battle_key_interval': self.battle_key_interval,
                'post_e_delay': self.post_e_delay,
                'encounter_loop_duration': self.encounter_loop_duration,
                'encounter_loop_type': self.encounter_loop_type,
                'encounter_loop_interval': self.encounter_loop_interval,
                'heal_delay': self.heal_delay,
                'selected_macro': self.selected_macro
            }
            
            preset_path = os.path.join(self.presets_dir, f"{preset_name}.json")
            with open(preset_path, 'w') as f:
                json.dump(preset_config, f, indent=2)
            
            print(f"💾 Saved PP Auto Hunt preset '{preset_name}' to {preset_path}")
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
            
            print(f"📥 Loaded PP Auto Hunt preset '{preset_name}' from {preset_path}")
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
            print(f"🗑️ Deleted PP Auto Hunt preset '{preset_name}'")
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