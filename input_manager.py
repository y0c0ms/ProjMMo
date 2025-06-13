"""
Input Manager for recording and playing back keyboard/mouse events
"""
import time
import json
import threading
from pynput import mouse, keyboard
from pynput.mouse import Button, Listener as MouseListener
from pynput.keyboard import Key, Listener as KeyboardListener
import win32api
import win32con
from config import *

class InputManager:
    def __init__(self, window_manager):
        self.window_manager = window_manager
        self.is_recording = False
        self.is_playing = False
        self.recorded_events = []
        self.start_time = None
        
        # Listeners
        self.mouse_listener = None
        self.keyboard_listener = None
        self.hotkey_listener = None
        
        # Playback
        self.playback_thread = None
        self.stop_playback = False
        
        # Last mouse position for movement threshold
        self.last_mouse_pos = (0, 0)
        
        # Recording control callbacks
        self.stop_recording_callback = None
        self.stop_loop_callback = None
        
        # Start global hotkey listener
        self.start_hotkey_listener()
        
    def start_recording(self):
        """Start recording input events"""
        if self.is_recording:
            return False
        
        # Move mouse to center of game window for consistent starting position
        self._center_mouse_in_game()
        
        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()
        
        print(f"Recording started at {self.start_time}")
        print(f"Game running: {self.window_manager.is_game_running()}")
        if self.window_manager.game_rect:
            print(f"Game window rect: {self.window_manager.game_rect}")
        else:
            print("No game window rect found!")
        
        # Start listeners with better error handling
        try:
            # Create listeners with error handling wrappers
            self.mouse_listener = MouseListener(
                on_move=self._safe_on_mouse_move,
                on_click=self._safe_on_mouse_click,
                on_scroll=self._safe_on_mouse_scroll,
                suppress=False
            )
            
            self.keyboard_listener = KeyboardListener(
                on_press=self._safe_on_key_press,
                on_release=self._safe_on_key_release,
                suppress=False
            )
            
            self.mouse_listener.start()
            self.keyboard_listener.start()
            print("Input listeners started successfully")
        except Exception as e:
            print(f"Error starting input listeners: {e}")
            return False
        
        return True
    
    def stop_recording(self):
        """Stop recording input events"""
        if not self.is_recording:
            return []
        
        self.is_recording = False
        
        # Stop listeners
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        # Move mouse back to center for consistent ending position
        self._center_mouse_in_game()
        
        return self.recorded_events.copy()
    
    def _get_timestamp(self):
        """Get current timestamp relative to recording start"""
        return time.time() - self.start_time
    
    def _safe_on_mouse_move(self, x, y):
        """Safe wrapper for mouse move events"""
        try:
            self._on_mouse_move(x, y)
        except Exception as e:
            print(f"Error in mouse move handler: {e}")
    
    def _safe_on_mouse_click(self, x, y, button, pressed):
        """Safe wrapper for mouse click events"""
        try:
            self._on_mouse_click(x, y, button, pressed)
        except Exception as e:
            print(f"Error in mouse click handler: {e}")
    
    def _safe_on_mouse_scroll(self, x, y, dx, dy):
        """Safe wrapper for mouse scroll events"""
        try:
            self._on_mouse_scroll(x, y, dx, dy)
        except Exception as e:
            print(f"Error in mouse scroll handler: {e}")
    
    def _safe_on_key_press(self, key):
        """Safe wrapper for key press events"""
        try:
            self._on_key_press(key)
        except Exception as e:
            print(f"Error in key press handler: {e}")
    
    def _safe_on_key_release(self, key):
        """Safe wrapper for key release events"""
        try:
            self._on_key_release(key)
        except Exception as e:
            print(f"Error in key release handler: {e}")
    
    def _on_mouse_move(self, x, y):
        """Handle mouse movement"""
        if not self.is_recording:
            return
        
        print(f"Mouse move detected at {x}, {y}")
        
        # Only record when game is running (less strict than active)
        if not self.window_manager.is_game_running():
            print("Game not running, skipping mouse move")
            return
        
        # Check if mouse is within game window bounds
        if not self._is_mouse_in_game_window(x, y):
            print(f"Mouse outside game window ({x}, {y}), skipping")
            return
        
        # Check movement threshold
        if abs(x - self.last_mouse_pos[0]) < MOUSE_MOVE_THRESHOLD and \
           abs(y - self.last_mouse_pos[1]) < MOUSE_MOVE_THRESHOLD:
            return
        
        self.last_mouse_pos = (x, y)
        
        # Convert to game coordinates
        game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'mouse_move',
            'x': game_x,
            'y': game_y,
            'screen_x': x,
            'screen_y': y
        }
        
        self.recorded_events.append(event)
        print(f"✓ Recorded mouse move: {len(self.recorded_events)} events total")
    
    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse clicks"""
        if not self.is_recording:
            return
        
        print(f"Mouse {button.name} {'press' if pressed else 'release'} at {x}, {y}")
        
        # Only record when game is running (less strict than active)
        if not self.window_manager.is_game_running():
            print("Game not running, skipping mouse click")
            return
        
        # Check if click is within game window bounds
        if not self._is_mouse_in_game_window(x, y):
            print(f"Click outside game window ({x}, {y}), skipping")
            return
        
        # Convert to game coordinates
        game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'mouse_click',
            'x': game_x,
            'y': game_y,
            'screen_x': x,
            'screen_y': y,
            'button': button.name,
            'pressed': pressed
        }
        
        self.recorded_events.append(event)
        print(f"✓ Recorded mouse {button.name} click: {len(self.recorded_events)} events total")
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll"""
        if not self.is_recording:
            return
        
        # Only record when game is active
        if not self.window_manager.is_game_active():
            return
        
        # Convert to game coordinates  
        game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'mouse_scroll',
            'x': game_x,
            'y': game_y,
            'screen_x': x,
            'screen_y': y,
            'dx': dx,
            'dy': dy
        }
        
        self.recorded_events.append(event)
    
    def _on_key_press(self, key):
        """Handle key press"""
        if not self.is_recording:
            return
        
        # Only record when game is running (less strict than active)
        if not self.window_manager.is_game_running():
            return
        
        # Get key name
        try:
            key_name = key.char if hasattr(key, 'char') and key.char else key.name
        except:
            key_name = str(key)
        
        # Skip the stop recording hotkey
        if key_name == '«':
            return
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'key_press', 
            'key': key_name,
            'pressed': True
        }
        
        self.recorded_events.append(event)
        print(f"Recorded key press '{key_name}': {len(self.recorded_events)} events")
    
    def _on_key_release(self, key):
        """Handle key release"""
        if not self.is_recording:
            return
        
        # Only record when game is running (less strict than active)
        if not self.window_manager.is_game_running():
            return
        
        # Get key name
        try:
            key_name = key.char if hasattr(key, 'char') and key.char else key.name
        except:
            key_name = str(key)
        
        # Skip the stop recording hotkey
        if key_name == '«':
            return
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'key_release',
            'key': key_name, 
            'pressed': False
        }
        
        self.recorded_events.append(event)
    
    def play_macro(self, events, speed=1.0, loop_count=1, callback=None):
        """Play back recorded events"""
        if self.is_playing:
            return False
        
        self.is_playing = True
        self.stop_playback = False
        
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(events, speed, loop_count, callback),
            daemon=True
        )
        
        self.playback_thread.start()
        return True
    
    def stop_macro(self):
        """Stop macro playback"""
        self.stop_playback = True
        self.is_playing = False
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2.0)
    
    def _playback_loop(self, events, speed, loop_count, callback):
        """Main playback loop"""
        try:
            loop = 0
            while True:
                if self.stop_playback:
                    break
                
                # Check if we've reached the loop limit (unless infinite)
                if loop_count != -1 and loop >= loop_count:
                    break
                
                # Move mouse to center before each loop iteration for consistency
                self._center_mouse_in_game()
                time.sleep(0.2)  # Small delay after centering
                
                last_timestamp = 0
                
                for event in events:
                    if self.stop_playback:
                        break
                    
                    # Wait for correct timing
                    wait_time = (event['timestamp'] - last_timestamp) / speed
                    if wait_time > 0:
                        time.sleep(wait_time)
                    
                    # Execute event
                    self._execute_event(event)
                    last_timestamp = event['timestamp']
                
                # Break out if stop was requested during event execution
                if self.stop_playback:
                    break
                    
                loop += 1
                
                # Callback for loop completion
                if callback:
                    callback('loop_completed', loop)
                
                # Small delay between loops
                if loop_count == -1 or loop < loop_count:
                    time.sleep(0.5)
        
        except Exception as e:
            if callback:
                callback('error', str(e))
        
        finally:
            self.is_playing = False
            if callback:
                callback('playback_finished', None)
    
    def _execute_event(self, event):
        """Execute a single event"""
        try:
            if event['type'] == 'mouse_move':
                # Convert back to screen coordinates
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                win32api.SetCursorPos((int(screen_x), int(screen_y)))
            
            elif event['type'] == 'mouse_click':
                # Convert back to screen coordinates
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                
                # Set cursor position
                win32api.SetCursorPos((int(screen_x), int(screen_y)))
                
                # Determine button
                if event['button'] == 'left':
                    down_flag = win32con.MOUSEEVENTF_LEFTDOWN
                    up_flag = win32con.MOUSEEVENTF_LEFTUP
                elif event['button'] == 'right':
                    down_flag = win32con.MOUSEEVENTF_RIGHTDOWN
                    up_flag = win32con.MOUSEEVENTF_RIGHTUP
                elif event['button'] == 'middle':
                    down_flag = win32con.MOUSEEVENTF_MIDDLEDOWN
                    up_flag = win32con.MOUSEEVENTF_MIDDLEUP
                else:
                    return
                
                # Send click
                if event['pressed']:
                    win32api.mouse_event(down_flag, 0, 0, 0, 0)
                else:
                    win32api.mouse_event(up_flag, 0, 0, 0, 0)
            
            elif event['type'] == 'mouse_scroll':
                # Convert back to screen coordinates
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                win32api.SetCursorPos((int(screen_x), int(screen_y)))
                
                # Send scroll
                scroll_amount = int(event['dy'] * 120)  # Windows scroll units
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, scroll_amount, 0)
            
            elif event['type'] in ['key_press', 'key_release']:
                # Handle keyboard events
                self._send_key_event(event['key'], event['pressed'])
        
        except Exception as e:
            print(f"Error executing event: {e}")
    
    def _send_key_event(self, key_name, pressed):
        """Send keyboard event"""
        try:
            # Convert key name to virtual key code
            vk_code = self._get_virtual_key_code(key_name)
            if vk_code:
                if pressed:
                    win32api.keybd_event(vk_code, 0, 0, 0)
                else:
                    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
        except:
            pass
    
    def _get_virtual_key_code(self, key_name):
        """Get Windows virtual key code from key name"""
        key_map = {
            'space': win32con.VK_SPACE,
            'enter': win32con.VK_RETURN,
            'tab': win32con.VK_TAB,
            'esc': win32con.VK_ESCAPE,
            'shift': win32con.VK_SHIFT,
            'ctrl': win32con.VK_CONTROL,
            'alt': win32con.VK_MENU,
            'up': win32con.VK_UP,
            'down': win32con.VK_DOWN,
            'left': win32con.VK_LEFT,
            'right': win32con.VK_RIGHT,
            # Add more as needed
        }
        
        # Handle single characters
        if len(key_name) == 1:
            return ord(key_name.upper())
        
        return key_map.get(key_name.lower())
    
    def _center_mouse_in_game(self):
        """Move mouse to center of game window"""
        if not self.window_manager.game_rect:
            return
        
        try:
            # Calculate center of game window
            x1, y1, x2, y2 = self.window_manager.game_rect
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            # Move mouse to center
            win32api.SetCursorPos((center_x, center_y))
            time.sleep(0.1)  # Small delay to ensure position is set
        except Exception as e:
            print(f"Error centering mouse: {e}")
    
    def start_hotkey_listener(self):
        """Start global hotkey listener for recording control"""
        try:
            def on_hotkey_press(key):
                try:
                    # Check for stop recording hotkey
                    if hasattr(key, 'char') and key.char == STOP_RECORDING_KEY:
                        if self.is_recording and self.stop_recording_callback:
                            self.stop_recording_callback()
                    # Check for stop loop hotkey
                    elif hasattr(key, 'name') and key.name.lower() == STOP_LOOP_KEY.lower():
                        if self.is_playing and self.stop_loop_callback:
                            self.stop_loop_callback()
                    elif hasattr(key, 'char') and key.char == STOP_LOOP_KEY:
                        if self.is_playing and self.stop_loop_callback:
                            self.stop_loop_callback()
                except:
                    pass
            
            self.hotkey_listener = KeyboardListener(on_press=on_hotkey_press, suppress=False)
            self.hotkey_listener.start()
        except Exception as e:
            print(f"Error starting hotkey listener: {e}")
    
    def set_stop_recording_callback(self, callback):
        """Set callback for when recording should be stopped via hotkey"""
        self.stop_recording_callback = callback
    
    def set_stop_loop_callback(self, callback):
        """Set callback for when loop should be stopped via hotkey"""
        self.stop_loop_callback = callback
    
    def _is_mouse_in_game_window(self, x, y):
        """Check if mouse coordinates are within game window bounds"""
        if not self.window_manager.game_rect:
            print("No game window rect available")
            return False
        
        x1, y1, x2, y2 = self.window_manager.game_rect
        in_bounds = x1 <= x <= x2 and y1 <= y <= y2
        print(f"Game window bounds: ({x1}, {y1}) to ({x2}, {y2}), mouse at ({x}, {y}), in bounds: {in_bounds}")
        return in_bounds
    
    def cleanup(self):
        """Clean up all listeners"""
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.is_playing:
            self.stop_macro() 