"""
Input Manager for recording and playing back keyboard/mouse events
Uses Windows API for better compatibility and reliability
"""
import time
import json
import threading
import win32api
import win32con
import win32gui
from config import *

class InputManager:
    def __init__(self, window_manager):
        self.window_manager = window_manager
        self.is_recording = False
        self.is_playing = False
        self.recorded_events = []
        self.start_time = None
        
        # Recording options
        self.record_mouse_movements = True  # Can be toggled
        
        # Hook handles
        self.keyboard_hook = None
        self.mouse_hook = None
        self.hotkey_hook = None
        
        # Playback
        self.playback_thread = None
        self.stop_playback = False
        
        # Last mouse position for movement threshold
        self.last_mouse_pos = (0, 0)
        
        # Recording control callbacks
        self.toggle_recording_callback = None
        self.stop_loop_callback = None
        self.emergency_stop_callback = None
        
        # Hook thread
        self.hook_thread = None
        self.hook_thread_running = False
        
        # Start global hotkey listener
        self.start_hotkey_listener()
        
    def set_record_mouse_movements(self, enabled):
        """Toggle mouse movement recording"""
        self.record_mouse_movements = enabled
        print(f"Mouse movement recording: {'enabled' if enabled else 'disabled'}")
        
    def start_recording(self):
        """Start recording input events"""
        if self.is_recording:
            return False
        
        # Move mouse to center of game window for consistent starting position
        if self.record_mouse_movements:
            self._center_mouse_in_game()
        
        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()
        
        print(f"Recording started at {self.start_time}")
        print(f"Mouse movements: {'enabled' if self.record_mouse_movements else 'disabled'}")
        print(f"Game running: {self.window_manager.is_game_running()}")
        if self.window_manager.game_rect:
            print(f"Game window rect: {self.window_manager.game_rect}")
        else:
            print("No game window rect found!")
        
        # Start hooks
        try:
            self._start_recording_hooks()
            print("Input hooks started successfully")
        except Exception as e:
            print(f"Error starting input hooks: {e}")
            return False
        
        return True
    
    def stop_recording(self):
        """Stop recording input events"""
        if not self.is_recording:
            return []
        
        self.is_recording = False
        
        # Stop hooks
        self._stop_recording_hooks()
        
        # Move mouse back to center for consistent ending position
        if self.record_mouse_movements:
            self._center_mouse_in_game()
        
        print(f"Recording stopped. Recorded {len(self.recorded_events)} events")
        return self.recorded_events.copy()
    
    def _start_recording_hooks(self):
        """Start Windows API hooks for recording"""
        def keyboard_hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and self.is_recording:
                try:
                    self._on_keyboard_event(wParam, lParam)
                except Exception as e:
                    print(f"Error in keyboard hook: {e}")
            return win32api.CallNextHookEx(self.keyboard_hook, nCode, wParam, lParam)
        
        def mouse_hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and self.is_recording and self.record_mouse_movements:
                try:
                    self._on_mouse_event(wParam, lParam)
                except Exception as e:
                    print(f"Error in mouse hook: {e}")
            return win32api.CallNextHookEx(self.mouse_hook, nCode, wParam, lParam)
        
        # Install hooks
        self.keyboard_hook = win32api.SetWindowsHookEx(
            win32con.WH_KEYBOARD_LL, keyboard_hook_proc, win32api.GetModuleHandle(None), 0)
        
        if self.record_mouse_movements:
            self.mouse_hook = win32api.SetWindowsHookEx(
                win32con.WH_MOUSE_LL, mouse_hook_proc, win32api.GetModuleHandle(None), 0)
    
    def _stop_recording_hooks(self):
        """Stop Windows API hooks"""
        if self.keyboard_hook:
            win32api.UnhookWindowsHookEx(self.keyboard_hook)
            self.keyboard_hook = None
        if self.mouse_hook:
            win32api.UnhookWindowsHookEx(self.mouse_hook)
            self.mouse_hook = None
    
    def _on_keyboard_event(self, wParam, lParam):
        """Handle keyboard events during recording"""
        if not self.is_recording:
            return
        
        # Only record when game is running
        if not self.window_manager.is_game_running():
            return
        
        # Get key info
        vk_code = lParam[0] if isinstance(lParam, tuple) else win32api.LOWORD(lParam)
        pressed = wParam in [win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN]
        
        # Get key name
        key_name = self._get_key_name_from_vk(vk_code)
        if not key_name:
            return
        
        # Skip the recording toggle key to avoid recursion
        if key_name == TOGGLE_RECORDING_KEY:
            return
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'key_press' if pressed else 'key_release',
            'key': key_name,
            'vk_code': vk_code
        }
        
        self.recorded_events.append(event)
        print(f"✓ Recorded key {key_name} {'press' if pressed else 'release'}: {len(self.recorded_events)} events total")
    
    def _on_mouse_event(self, wParam, lParam):
        """Handle mouse events during recording"""
        if not self.is_recording or not self.record_mouse_movements:
            return
        
        # Only record when game is running
        if not self.window_manager.is_game_running():
            return
        
        # Parse mouse data
        if isinstance(lParam, tuple) and len(lParam) >= 2:
            x, y = lParam[0], lParam[1]
        else:
            # Fallback to current cursor position
            x, y = win32gui.GetCursorPos()
        
        # Check if mouse is within game window bounds
        if not self._is_mouse_in_game_window(x, y):
            return
        
        # Handle different mouse events
        if wParam == win32con.WM_MOUSEMOVE:
            self._record_mouse_move(x, y)
        elif wParam in [win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP]:
            self._record_mouse_click(x, y, 'left', wParam == win32con.WM_LBUTTONDOWN)
        elif wParam in [win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP]:
            self._record_mouse_click(x, y, 'right', wParam == win32con.WM_RBUTTONDOWN)
        elif wParam in [win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP]:
            self._record_mouse_click(x, y, 'middle', wParam == win32con.WM_MBUTTONDOWN)
    
    def _record_mouse_move(self, x, y):
        """Record mouse movement with threshold"""
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
    
    def _record_mouse_click(self, x, y, button, pressed):
        """Record mouse click"""
        # Convert to game coordinates
        game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
        
        event = {
            'timestamp': self._get_timestamp(),
            'type': 'mouse_click',
            'x': game_x,
            'y': game_y,
            'button': button,
            'pressed': pressed,
            'screen_x': x,
            'screen_y': y
        }
        
        self.recorded_events.append(event)
        print(f"✓ Recorded mouse {button} {'press' if pressed else 'release'}: {len(self.recorded_events)} events total")
    
    def _get_timestamp(self):
        """Get current timestamp relative to recording start"""
        return time.time() - self.start_time
    
    def _get_key_name_from_vk(self, vk_code):
        """Convert virtual key code to key name"""
        key_map = {
            # Letters (A-Z)
            **{ord(chr(i)): chr(i).lower() for i in range(ord('A'), ord('Z') + 1)},
            # Numbers (0-9)
            **{ord(str(i)): str(i) for i in range(10)},
            # Function keys
            win32con.VK_F1: 'f1', win32con.VK_F2: 'f2', win32con.VK_F3: 'f3',
            win32con.VK_F4: 'f4', win32con.VK_F5: 'f5', win32con.VK_F6: 'f6',
            win32con.VK_F7: 'f7', win32con.VK_F8: 'f8', win32con.VK_F9: 'f9',
            win32con.VK_F10: 'f10', win32con.VK_F11: 'f11', win32con.VK_F12: 'f12',
            # Special keys
            win32con.VK_SPACE: 'space',
            win32con.VK_RETURN: 'enter',
            win32con.VK_ESCAPE: 'esc',
            win32con.VK_TAB: 'tab',
            win32con.VK_SHIFT: 'shift',
            win32con.VK_CONTROL: 'ctrl',
            win32con.VK_MENU: 'alt',
            win32con.VK_BACK: 'backspace',
            win32con.VK_DELETE: 'delete',
            win32con.VK_INSERT: 'insert',
            win32con.VK_HOME: 'home',
            win32con.VK_END: 'end',
            win32con.VK_PRIOR: 'page_up',
            win32con.VK_NEXT: 'page_down',
            win32con.VK_UP: 'up',
            win32con.VK_DOWN: 'down',
            win32con.VK_LEFT: 'left',
            win32con.VK_RIGHT: 'right',
            # Common symbols
            win32con.VK_OEM_3: '`',  # backtick
            win32con.VK_OEM_MINUS: '-',
            win32con.VK_OEM_PLUS: '=',
            win32con.VK_OEM_4: '[',
            win32con.VK_OEM_6: ']',
            win32con.VK_OEM_5: '\\',
            win32con.VK_OEM_1: ';',
            win32con.VK_OEM_7: "'",
            win32con.VK_OEM_COMMA: ',',
            win32con.VK_OEM_PERIOD: '.',
            win32con.VK_OEM_2: '/',
        }
        
        return key_map.get(vk_code)

    def play_macro(self, events, speed=1.0, loop_count=1, callback=None, timeout=30):
        """Play back recorded macro with increased timeout"""
        if self.is_playing:
            print("Already playing a macro")
            return False
        
        self.is_playing = True
        self.stop_playback = False
        
        # Start playback in separate thread
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(events, speed, loop_count, callback, timeout),
            daemon=True
        )
        self.playback_thread.start()
        return True
    
    def stop_macro(self):
        """Stop macro playback"""
        self.stop_playback = True
        self.is_playing = False
        print("🛑 Macro playback stopped")
    
    def _playback_loop(self, events, speed, loop_count, callback, timeout):
        """Main playback loop with better error handling"""
        try:
            start_time = time.time()
            
            for loop in range(loop_count):
                if self.stop_playback:
                    break
                
                # Check timeout
                if time.time() - start_time > timeout:
                    print(f"⚠ Macro timed out after {timeout}s")
                    if callback:
                        callback("timeout", {"loop": loop + 1, "total": loop_count})
                    break
                
                print(f"🔄 Starting loop {loop + 1}/{loop_count}")
                
                if callback:
                    callback("loop_start", {"loop": loop + 1, "total": loop_count})
                
                last_timestamp = 0
                events_executed = 0
                events_failed = 0
                
                for event in events:
                    if self.stop_playback:
                        break
                    
                    # Calculate delay
                    delay = (event['timestamp'] - last_timestamp) / speed
                    if delay > 0:
                        time.sleep(delay)
                    
                    # Execute event with error handling
                    try:
                        success = self._execute_event(event)
                        if success:
                            events_executed += 1
                        else:
                            events_failed += 1
                            # Don't break on mouse movement failures
                            if event['type'] != 'mouse_move':
                                print(f"⚠ Critical event failed: {event['type']}")
                    except Exception as e:
                        print(f"❌ Event execution error: {e}")
                        events_failed += 1
                    
                    last_timestamp = event['timestamp']
                
                print(f"✅ Loop {loop + 1} completed: {events_executed} events, {events_failed} failed")
                
                if callback:
                    callback("loop_complete", {
                        "loop": loop + 1, 
                        "total": loop_count, 
                        "events_executed": events_executed,
                        "events_failed": events_failed
                    })
            
            print(f"🏁 Macro playback finished")
            
        except Exception as e:
            print(f"❌ Playback error: {e}")
            if callback:
                callback("error", {"error": str(e)})
        finally:
            self.is_playing = False
            if callback:
                callback("complete", {"success": not self.stop_playback})
    
    def _execute_event(self, event):
        """Execute a single event with improved error handling"""
        try:
            event_type = event['type']
            
            if event_type == 'mouse_move':
                return self._execute_mouse_move(event)
            elif event_type == 'mouse_click':
                return self._execute_mouse_click(event)
            elif event_type in ['key_press', 'key_release']:
                return self._execute_key_event(event)
            else:
                print(f"⚠ Unknown event type: {event_type}")
                return False
                
        except Exception as e:
            print(f"❌ Event execution failed: {e}")
            return False
    
    def _execute_mouse_move(self, event):
        """Execute mouse movement with better error handling"""
        try:
            # Convert game coordinates to screen coordinates
            screen_x, screen_y = self.window_manager.game_to_screen_coords(event['x'], event['y'])
            
            # Try to set cursor position
            try:
                win32api.SetCursorPos((screen_x, screen_y))
                return True
            except Exception as e:
                # SetCursorPos can fail for various reasons, but it's not critical
                # Just skip the mouse movement but don't stop the macro
                print(f"⚠ Mouse move failed (non-critical): {e}")
                return False
                
        except Exception as e:
            print(f"❌ Mouse move coordinate conversion failed: {e}")
            return False
    
    def _execute_mouse_click(self, event):
        """Execute mouse click"""
        try:
            # Convert game coordinates to screen coordinates
            screen_x, screen_y = self.window_manager.game_to_screen_coords(event['x'], event['y'])
            
            # Move mouse first
            try:
                win32api.SetCursorPos((screen_x, screen_y))
            except:
                # If we can't move the mouse, still try to click at current position
                screen_x, screen_y = win32gui.GetCursorPos()
            
            # Determine button and action
            button = event.get('button', 'left')
            pressed = event.get('pressed', True)
            
            if button == 'left':
                flag = win32con.MOUSEEVENTF_LEFTDOWN if pressed else win32con.MOUSEEVENTF_LEFTUP
            elif button == 'right':
                flag = win32con.MOUSEEVENTF_RIGHTDOWN if pressed else win32con.MOUSEEVENTF_RIGHTUP
            elif button == 'middle':
                flag = win32con.MOUSEEVENTF_MIDDLEDOWN if pressed else win32con.MOUSEEVENTF_MIDDLEUP
            else:
                print(f"⚠ Unknown mouse button: {button}")
                return False
            
            win32api.mouse_event(flag, screen_x, screen_y, 0, 0)
            return True
            
        except Exception as e:
            print(f"❌ Mouse click failed: {e}")
            return False
    
    def _execute_key_event(self, event):
        """Execute keyboard event"""
        try:
            key_name = event['key']
            pressed = event['type'] == 'key_press'
            
            vk_code = self._get_virtual_key_code(key_name)
            if not vk_code:
                print(f"⚠ Unknown key: {key_name}")
                return False
            
            flags = 0 if pressed else win32con.KEYEVENTF_KEYUP
            win32api.keybd_event(vk_code, 0, flags, 0)
            return True
            
        except Exception as e:
            print(f"❌ Key event failed: {e}")
            return False

    def _get_virtual_key_code(self, key_name):
        """Get virtual key code from key name"""
        key_map = {
            # Letters
            **{chr(i).lower(): ord(chr(i)) for i in range(ord('A'), ord('Z') + 1)},
            # Numbers
            **{str(i): ord(str(i)) for i in range(10)},
            # Function keys
            'f1': win32con.VK_F1, 'f2': win32con.VK_F2, 'f3': win32con.VK_F3,
            'f4': win32con.VK_F4, 'f5': win32con.VK_F5, 'f6': win32con.VK_F6,
            'f7': win32con.VK_F7, 'f8': win32con.VK_F8, 'f9': win32con.VK_F9,
            'f10': win32con.VK_F10, 'f11': win32con.VK_F11, 'f12': win32con.VK_F12,
            # Special keys
            'space': win32con.VK_SPACE,
            'enter': win32con.VK_RETURN,
            'esc': win32con.VK_ESCAPE,
            'escape': win32con.VK_ESCAPE,
            'tab': win32con.VK_TAB,
            'shift': win32con.VK_SHIFT,
            'ctrl': win32con.VK_CONTROL,
            'control': win32con.VK_CONTROL,
            'alt': win32con.VK_MENU,
            'backspace': win32con.VK_BACK,
            'delete': win32con.VK_DELETE,
            'insert': win32con.VK_INSERT,
            'home': win32con.VK_HOME,
            'end': win32con.VK_END,
            'page_up': win32con.VK_PRIOR,
            'page_down': win32con.VK_NEXT,
            'up': win32con.VK_UP,
            'down': win32con.VK_DOWN,
            'left': win32con.VK_LEFT,
            'right': win32con.VK_RIGHT,
            # Symbols
            '`': win32con.VK_OEM_3,
            '-': win32con.VK_OEM_MINUS,
            '=': win32con.VK_OEM_PLUS,
            '[': win32con.VK_OEM_4,
            ']': win32con.VK_OEM_6,
            '\\': win32con.VK_OEM_5,
            ';': win32con.VK_OEM_1,
            "'": win32con.VK_OEM_7,
            ',': win32con.VK_OEM_COMMA,
            '.': win32con.VK_OEM_PERIOD,
            '/': win32con.VK_OEM_2,
        }
        
        return key_map.get(key_name.lower())
    
    def _center_mouse_in_game(self):
        """Move mouse to center of game window"""
        if not self.window_manager.game_rect:
            print("Cannot center mouse - no game window rect available")
            return
        
        try:
            # Calculate center of game window
            left, top, right, bottom = self.window_manager.game_rect
            center_x = (left + right) // 2
            center_y = (top + bottom) // 2
            
            print(f"Centering mouse to ({center_x}, {center_y}) in game window")
            
            # Move mouse to center
            win32api.SetCursorPos((center_x, center_y))
            time.sleep(0.2)  # Small delay to ensure position is set
            
        except Exception as e:
            print(f"Error centering mouse: {e}")
    
    def start_hotkey_listener(self):
        """Start global hotkey listener using Windows API"""
        def hotkey_hook_proc(nCode, wParam, lParam):
            if nCode >= 0:
                try:
                    self._handle_hotkey(wParam, lParam)
                except Exception as e:
                    print(f"Error in hotkey handler: {e}")
            return win32api.CallNextHookEx(self.hotkey_hook, nCode, wParam, lParam)
        
        try:
            # Install global keyboard hook for hotkeys
            self.hotkey_hook = win32api.SetWindowsHookEx(
                win32con.WH_KEYBOARD_LL, hotkey_hook_proc, win32api.GetModuleHandle(None), 0)
            
            print(f"Global hotkey listener started - Toggle recording: '{TOGGLE_RECORDING_KEY}', Stop loop: '{STOP_LOOP_KEY}'")
            
            # Start message pump in separate thread
            self.hook_thread_running = True
            self.hook_thread = threading.Thread(target=self._message_pump, daemon=True)
            self.hook_thread.start()
            
        except Exception as e:
            print(f"Error starting hotkey listener: {e}")
    
    def _message_pump(self):
        """Message pump for Windows hooks"""
        try:
            while self.hook_thread_running:
                # Simple sleep-based approach instead of complex message pumping
                time.sleep(0.01)  # Small delay to prevent high CPU usage
        except Exception as e:
            print(f"Message pump error: {e}")
    
    def _handle_hotkey(self, wParam, lParam):
        """Handle hotkey events"""
        if wParam not in [win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN]:
            return
        
        # Get key info
        vk_code = lParam[0] if isinstance(lParam, tuple) else win32api.LOWORD(lParam)
        key_name = self._get_key_name_from_vk(vk_code)
        
        if not key_name:
            return
        
        # Handle toggle recording hotkey
        if key_name == TOGGLE_RECORDING_KEY:
            print(f"Toggle recording hotkey '{TOGGLE_RECORDING_KEY}' detected!")
            if self.toggle_recording_callback:
                threading.Thread(target=self.toggle_recording_callback, daemon=True).start()
        
        # Handle stop loop hotkey
        elif key_name.lower() == STOP_LOOP_KEY.lower():
            print(f"Stop loop hotkey '{STOP_LOOP_KEY}' detected!")
            if self.is_playing and self.stop_loop_callback:
                threading.Thread(target=self.stop_loop_callback, daemon=True).start()
        
        # Handle P key emergency stop (only when not recording)
        elif key_name.lower() == 'p' and not self.is_recording:
            print("P key detected - emergency stop!")
            if self.is_playing:
                self.stop_macro()
                if self.emergency_stop_callback:
                    threading.Thread(target=self.emergency_stop_callback, daemon=True).start()
    
    def set_toggle_recording_callback(self, callback):
        """Set callback for when recording should be toggled via hotkey"""
        self.toggle_recording_callback = callback
    
    def set_stop_loop_callback(self, callback):
        """Set callback for when loop should be stopped via hotkey"""
        self.stop_loop_callback = callback
    
    def set_emergency_stop_callback(self, callback):
        """Set callback for when emergency stop is triggered via P key"""
        self.emergency_stop_callback = callback
    
    def _is_mouse_in_game_window(self, x, y):
        """Check if mouse coordinates are within game window bounds"""
        if not self.window_manager.game_rect:
            return False
        
        left, top, right, bottom = self.window_manager.game_rect
        return left <= x <= right and top <= y <= bottom
    
    def cleanup(self):
        """Clean up all hooks and threads"""
        self.hook_thread_running = False
        
        if self.keyboard_hook:
            win32api.UnhookWindowsHookEx(self.keyboard_hook)
        if self.mouse_hook:
            win32api.UnhookWindowsHookEx(self.mouse_hook)
        if self.hotkey_hook:
            win32api.UnhookWindowsHookEx(self.hotkey_hook)
        
        if self.is_playing:
            self.stop_macro()
    
    def press_key(self, key_name: str):
        """Press a key (for Sweet Scent system)"""
        try:
            vk_code = self._get_virtual_key_code(key_name)
            if vk_code:
                win32api.keybd_event(vk_code, 0, 0, 0)  # Key down
                print(f"✓ Key {key_name} pressed")
            else:
                print(f"❌ Unknown key for press: {key_name}")
        except Exception as e:
            print(f"❌ Error pressing key {key_name}: {e}")
    
    def release_key(self, key_name: str):
        """Release a key (for Sweet Scent system)"""
        try:
            vk_code = self._get_virtual_key_code(key_name)
            if vk_code:
                win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up
                print(f"✓ Key {key_name} released")
            else:
                print(f"❌ Unknown key for release: {key_name}")
        except Exception as e:
            print(f"❌ Error releasing key {key_name}: {e}")
    
    def click_at_game_coords(self, x: int, y: int):
        """Click at game coordinates (for Sweet Scent system)"""
        try:
            # Convert game coordinates to screen coordinates
            if hasattr(self, 'window_manager') and self.window_manager.game_rect:
                left, top, right, bottom = self.window_manager.game_rect
                screen_x = left + x
                screen_y = top + y
                
                # Move mouse and click
                win32api.SetCursorPos((screen_x, screen_y))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screen_x, screen_y, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screen_x, screen_y, 0, 0)
                print(f"✓ Clicked at game coords ({x}, {y}) -> screen ({screen_x}, {screen_y})")
            else:
                print("❌ Cannot click - game window not found")
        except Exception as e:
            print(f"❌ Error clicking at ({x}, {y}): {e}") 