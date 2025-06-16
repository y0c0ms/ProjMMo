"""
PokeMMO Overlay - Main application with improved UI and polling-based input capture
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import win32api
import win32con
import win32gui
from config import *
from window_manager import WindowManager
from macro_manager import MacroManager
from auto_hunt import AutoHuntEngine, TemplateManager
from sweet_scent import SweetScentEngine
from auto_hunt_pp import PPAutoHuntEngine

class InputCapturePolling:
    """Polling-based input capture - more compatible than pynput"""
    
    def __init__(self, window_manager):
        self.window_manager = window_manager
        self.is_recording = False
        self.recorded_events = []
        self.start_time = None
        self.last_mouse_pos = (0, 0)
        self.last_key_states = {}
        self.recording_thread = None
        self.stop_recording_flag = False
        self.stop_playback = False
        self.record_mouse_movements = True  # Add mouse recording toggle
        
        # Initialize key states for tracking
        self._init_key_states()
    
    def _init_key_states(self):
        """Initialize tracking of key states"""
        # Track common keys
        keys_to_track = [
            win32con.VK_LBUTTON, win32con.VK_RBUTTON, win32con.VK_MBUTTON,
            win32con.VK_ESCAPE, win32con.VK_SPACE, win32con.VK_RETURN,
            win32con.VK_LEFT, win32con.VK_RIGHT, win32con.VK_UP, win32con.VK_DOWN,
        ]
        
        # Add A-Z keys
        for i in range(ord('A'), ord('Z') + 1):
            keys_to_track.append(i)
        
        # Add 0-9 keys
        for i in range(ord('0'), ord('9') + 1):
            keys_to_track.append(i)
        
        # Initialize all as not pressed
        self.last_key_states = {key: False for key in keys_to_track}
    
    def start_recording(self):
        """Start recording input events"""
        if self.is_recording:
            return False
        
        self.is_recording = True
        self.recorded_events = []
        self.start_time = time.time()
        self.stop_recording_flag = False
        
        print(f"Recording started at {self.start_time}")
        print(f"Game running: {self.window_manager.is_game_running()}")
        if self.window_manager.game_rect:
            print(f"Game window rect: {self.window_manager.game_rect}")
        
        # Start recording thread
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()
        
        return True
    
    def stop_recording(self):
        """Stop recording input events"""
        if not self.is_recording:
            return []
        
        self.is_recording = False
        self.stop_recording_flag = True
        
        # Wait for recording thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
        print(f"Recording stopped. Total events: {len(self.recorded_events)}")
        return self.recorded_events.copy()
    
    def _recording_loop(self):
        """Main recording loop using polling"""
        try:
            while self.is_recording and not self.stop_recording_flag:
                if not self.window_manager.is_game_running():
                    time.sleep(0.1)
                    continue
                
                # Poll mouse position
                self._poll_mouse()
                
                # Poll key states
                self._poll_keys()
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)  # 100 Hz polling
                
        except Exception as e:
            print(f"Error in recording loop: {e}")
    
    def _poll_mouse(self):
        """Poll mouse position and buttons"""
        try:
            # Get current mouse position
            x, y = win32gui.GetCursorPos()
            
            # Check if mouse moved significantly (only if mouse recording is enabled)
            if self.record_mouse_movements and (abs(x - self.last_mouse_pos[0]) >= MOUSE_MOVE_THRESHOLD or \
               abs(y - self.last_mouse_pos[1]) >= MOUSE_MOVE_THRESHOLD):
                
                # Check if mouse is in game window
                if self._is_mouse_in_game_window(x, y):
                    # Record mouse movement
                    game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
                    
                    event = {
                        'timestamp': time.time() - self.start_time,
                        'type': 'mouse_move',
                        'x': game_x,
                        'y': game_y,
                        'screen_x': x,
                        'screen_y': y
                    }
                    
                    self.recorded_events.append(event)
                    print(f"✓ Mouse move recorded: {len(self.recorded_events)} events")
                
                self.last_mouse_pos = (x, y)
            
            # Always update last mouse position for threshold calculation
            if not self.record_mouse_movements:
                self.last_mouse_pos = (x, y)
            
            # Check mouse buttons (always record clicks even if movement is disabled)
            left_pressed = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) < 0
            right_pressed = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) < 0
            middle_pressed = win32api.GetAsyncKeyState(win32con.VK_MBUTTON) < 0
            
            # Check for button state changes
            for button, vk_code, name in [
                (left_pressed, win32con.VK_LBUTTON, 'left'),
                (right_pressed, win32con.VK_RBUTTON, 'right'),
                (middle_pressed, win32con.VK_MBUTTON, 'middle')
            ]:
                last_state = self.last_key_states.get(vk_code, False)
                
                if button != last_state:  # State changed
                    if self._is_mouse_in_game_window(x, y):
                        game_x, game_y = self.window_manager.screen_to_game_coords(x, y)
                        
                        event = {
                            'timestamp': time.time() - self.start_time,
                            'type': 'mouse_click',
                            'x': game_x,
                            'y': game_y,
                            'screen_x': x,
                            'screen_y': y,
                            'button': name,
                            'pressed': button
                        }
                        
                        self.recorded_events.append(event)
                        print(f"✓ Mouse {name} {'press' if button else 'release'} recorded: {len(self.recorded_events)} events")
                    
                    self.last_key_states[vk_code] = button
                    
        except Exception as e:
            print(f"Error polling mouse: {e}")
    
    def _poll_keys(self):
        """Poll keyboard state"""
        try:
            for vk_code in self.last_key_states:
                # Skip mouse buttons (already handled)
                if vk_code in [win32con.VK_LBUTTON, win32con.VK_RBUTTON, win32con.VK_MBUTTON]:
                    continue
                
                # Check key state
                current_state = win32api.GetAsyncKeyState(vk_code) < 0
                last_state = self.last_key_states[vk_code]
                
                if current_state != last_state:  # State changed
                    key_name = self._vk_to_key_name(vk_code)
                    
                    event = {
                        'timestamp': time.time() - self.start_time,
                        'type': 'key_press' if current_state else 'key_release',
                        'key': key_name,
                        'pressed': current_state
                    }
                    
                    self.recorded_events.append(event)
                    print(f"✓ Key {key_name} {'press' if current_state else 'release'} recorded: {len(self.recorded_events)} events")
                    
                    self.last_key_states[vk_code] = current_state
                    
        except Exception as e:
            print(f"Error polling keys: {e}")
    
    def _vk_to_key_name(self, vk_code):
        """Convert virtual key code to readable key name"""
        key_map = {
            win32con.VK_SPACE: 'space',
            win32con.VK_RETURN: 'enter',
            win32con.VK_TAB: 'tab',
            win32con.VK_ESCAPE: 'esc',
            win32con.VK_SHIFT: 'shift',
            win32con.VK_CONTROL: 'ctrl',
            win32con.VK_MENU: 'alt',
            win32con.VK_UP: 'up',
            win32con.VK_DOWN: 'down',
            win32con.VK_LEFT: 'left',
            win32con.VK_RIGHT: 'right',
        }
        
        if vk_code in key_map:
            return key_map[vk_code]
        elif ord('0') <= vk_code <= ord('9'):
            return chr(vk_code)
        elif ord('A') <= vk_code <= ord('Z'):
            return chr(vk_code).lower()
        else:
            return f'key_{vk_code}'
    
    def _is_mouse_in_game_window(self, x, y):
        """Check if mouse coordinates are within game window bounds"""
        if not self.window_manager.game_rect:
            return False
        
        x1, y1, x2, y2 = self.window_manager.game_rect
        return x1 <= x <= x2 and y1 <= y <= y2
    
    def play_macro(self, events, speed=1.0, loop_count=1, callback=None, timeout=120):
        """Play back recorded events with improved timeout handling"""
        playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(events, speed, loop_count, callback, timeout),
            daemon=True
        )
        playback_thread.start()
        return True
    
    def _playback_loop(self, events, speed, loop_count, callback, timeout=120):
        """Playback loop with improved error handling and timeout"""
        try:
            self.stop_playback = False
            loop = 0
            start_time = time.time()
            
            while True:
                if self.stop_playback:
                    break
                    
                # Check timeout (per loop, with increased time for multiple loops)
                current_timeout = timeout if loop_count == 1 else timeout * min(loop_count, 5)
                if time.time() - start_time > current_timeout:
                    if callback:
                        callback('timeout', {'loop': loop, 'timeout': current_timeout})
                    break
                
                if loop_count != -1 and loop >= loop_count:
                    break
                
                last_timestamp = 0
                
                for event in events:
                    if self.stop_playback:
                        break
                        
                    # Wait for correct timing
                    wait_time = (event['timestamp'] - last_timestamp) / speed
                    if wait_time > 0:
                        time.sleep(wait_time)
                    
                    # Execute event (errors are handled gracefully)
                    self._execute_event(event)
                    last_timestamp = event['timestamp']
                
                loop += 1
                
                if callback:
                    callback('loop_completed', loop)
                
                if loop_count == -1 or loop < loop_count:
                    time.sleep(0.5)
        
        except Exception as e:
            if callback:
                callback('error', str(e))
        
        finally:
            self.stop_playback = False
            if callback:
                callback('complete', None)
    
    def _execute_event(self, event):
        """Execute a single event"""
        try:
            if event['type'] == 'mouse_move':
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                try:
                    win32api.SetCursorPos((int(screen_x), int(screen_y)))
                except Exception as e:
                    # Mouse movement failures are non-critical, continue execution
                    print(f"Warning: SetCursorPos failed (non-critical): {e}")
            
            elif event['type'] == 'mouse_click':
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                try:
                    # Move mouse to position first (if it fails, still try to click)
                    try:
                        win32api.SetCursorPos((int(screen_x), int(screen_y)))
                    except:
                        pass  # Ignore cursor position errors
                    
                    # Determine click action
                    if event['button'] == 'left':
                        vk_code = win32con.VK_LBUTTON
                    elif event['button'] == 'right':
                        vk_code = win32con.VK_RBUTTON  
                    elif event['button'] == 'middle':
                        vk_code = win32con.VK_MBUTTON
                    else:
                        return
                    
                    if event['pressed']:
                        win32api.keybd_event(vk_code, 0, 0, 0)
                    else:
                        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                except Exception as e:
                    print(f"Warning: Mouse click failed (non-critical): {e}")
            
            elif event['type'] in ['key_press', 'key_release']:
                key_name = event['key']
                vk_code = self._get_virtual_key_code(key_name)
                
                if vk_code:
                    try:
                        if event['type'] == 'key_press':
                            win32api.keybd_event(vk_code, 0, 0, 0)
                            print(f"✓ Key {key_name} pressed")
                        else:
                            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                            print(f"✓ Key {key_name} released")
                    except Exception as e:
                        print(f"❌ Error with key {key_name}: {e}")
                        
        except Exception as e:
            # Log error but don't stop macro execution
            print(f"Warning: Event execution failed (continuing): {e}")
    
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
            'w': ord('W'),
            'a': ord('A'),
            's': ord('S'),
            'd': ord('D'),
        }
        
        if len(key_name) == 1:
            return ord(key_name.upper())
        
        return key_map.get(key_name.lower())
    
    def press_key(self, key_name: str):
        """Press a key (for Auto Hunt system)"""
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
        """Release a key (for Auto Hunt system)"""
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
        """Click at game coordinates (for Auto Hunt system)"""
        try:
            # Convert game coordinates to screen coordinates
            if self.window_manager.game_rect:
                # game_rect is a tuple: (left, top, right, bottom)
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
    
    def set_record_mouse_movements(self, enabled):
        """Toggle mouse movement recording"""
        self.record_mouse_movements = enabled
        print(f"Mouse movement recording: {'enabled' if enabled else 'disabled'}")

class PokeMMOOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        
        # Initialize components
        self.window_manager = WindowManager()
        
        # Window selection is now manual only - use Settings tab to select window
        print("💡 Use Settings tab → 'Select PokeMMO Window' to choose the correct game window")
        
        self.input_manager = InputCapturePolling(self.window_manager)
        self.macro_manager = MacroManager()
        self.template_manager = TemplateManager()
        self.auto_hunt_engine = AutoHuntEngine(self.window_manager, self.input_manager)
        self.sweet_scent_engine = SweetScentEngine(self.window_manager, self.input_manager, self.macro_manager)
        self.pp_auto_hunt_engine = PPAutoHuntEngine(self.window_manager, self.input_manager, self.macro_manager, self.template_manager)
        
        # UI variables
        self.is_recording = False
        self.current_events = []
        
        # Create UI
        self.create_ui()
        
        # Start periodic updates
        self.update_status()
        
        print("All components initialized successfully!")
    
    def setup_window(self):
        """Setup main overlay window"""
        self.root.title("PokeMMO Overlay")
        self.root.geometry("340x720")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.95)
        self.root.configure(bg='#1e1e1e')
        
        # Position in top-right corner
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry("+{}+{}".format(screen_width - 360, 20))
        
        # Allow resizing for user customization
        self.root.resizable(True, True)
        self.root.minsize(340, 600)
        
        # Bind hotkey for recording toggle
        self.root.bind('<Key>', self.on_key_press)
        self.root.focus_set()  # Allow window to receive key events
    
    def create_ui(self):
        """Create the user interface"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="PokeMMO Overlay", 
                              font=('Segoe UI', 14, 'bold'), 
                              fg='#00d4ff', bg='#1e1e1e')
        title_label.pack(pady=(0, 10))
        
        # Status section
        self.create_status_section(main_frame)
        
        # Create notebook for tabs
        self.create_tabbed_interface(main_frame)
    
    def create_status_section(self, parent):
        """Create status display section"""
        status_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(status_frame, text="Status", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 2))
        
        self.status_label = tk.Label(status_frame, text="Initializing...", 
                                   font=('Segoe UI', 9), 
                                   fg='#cccccc', bg='#2a2a2a')
        self.status_label.pack(pady=(0, 6))
    
    def create_tabbed_interface(self, parent):
        """Create tabbed interface for different functions"""
        # Configure ttk notebook style
        style = ttk.Style()
        style.configure('Dark.TNotebook', background='#1e1e1e', borderwidth=0)
        style.configure('Dark.TNotebook.Tab', 
                       background='#2a2a2a', 
                       foreground='#ffffff',
                       padding=[12, 8],
                       font=('Segoe UI', 9, 'bold'))
        style.map('Dark.TNotebook.Tab',
                 background=[('selected', '#00d4ff'), ('active', '#34495e')],
                 foreground=[('selected', '#000000'), ('active', '#ffffff')])
        
        # Create notebook
        self.notebook = ttk.Notebook(parent, style='Dark.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        # Macros tab
        self.macros_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.macros_frame, text='📋 Macros')
        
        # Fishing tab (placeholder)
        self.fishing_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.fishing_frame, text='🎣 Fishing')
        
        # Auto Hunt tab
        self.auto_hunt_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.auto_hunt_frame, text='🎯 Auto Hunt')
        
        # Sweet Scent tab
        self.sweet_scent_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.sweet_scent_frame, text='🌸 Sweet Scent')
        
        # Settings tab (placeholder)
        self.settings_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.settings_frame, text='⚙️ Settings')
        
        # Create content for each tab
        self.create_macros_tab()
        self.create_fishing_tab()
        self.create_auto_hunt_tab()
        self.create_sweet_scent_tab()
        self.create_settings_tab()
    
    def create_macros_tab(self):
        """Create the macros tab content"""
        # Recording section
        self.create_recording_section(self.macros_frame)
        
        # Save section
        self.create_save_section(self.macros_frame)
        
        # Macro management section
        self.create_macro_section(self.macros_frame)
    
    def create_recording_section(self, parent):
        """Create the recording section for macros tab"""
        # Recording section
        record_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        record_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(record_frame, text="🔴 Recording", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Recording button and status
        record_controls = tk.Frame(record_frame, bg='#2a2a2a')
        record_controls.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        self.record_button = tk.Button(record_controls, text="🔴 Start Recording", 
                                     command=self.toggle_recording,
                                     font=('Segoe UI', 10, 'bold'),
                                     fg='#ffffff', bg='#dc3545',
                                     activeforeground='#ffffff', activebackground='#c82333',
                                     relief=tk.RAISED, bd=2, pady=8)
        self.record_button.pack(fill=tk.X, pady=(0, 8))
        
        self.record_status = tk.Label(record_controls, text="Ready to record", 
                                    font=('Segoe UI', 9), 
                                    fg='#95a5a6', bg='#2a2a2a')
        self.record_status.pack()
        
        # Recording options
        options_frame = tk.Frame(record_frame, bg='#2a2a2a')
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        self.record_mouse_var = tk.BooleanVar(value=True)
        self.mouse_checkbox = tk.Checkbutton(options_frame, text="🖱️ Record Mouse Movements",
                                           variable=self.record_mouse_var,
                                           command=self._toggle_mouse_recording,
                                           font=('Segoe UI', 8),
                                           fg='#ffffff', bg='#2a2a2a',
                                           selectcolor='#2a2a2a',
                                           activeforeground='#ffffff', activebackground='#2a2a2a',
                                           borderwidth=0)
        self.mouse_checkbox.pack(side=tk.LEFT)
        
        tk.Label(options_frame, text="(Uncheck for keyboard-only macros)",
                font=('Segoe UI', 7, 'italic'),
                fg='#95a5a6', bg='#2a2a2a').pack(side=tk.LEFT, padx=(10, 0))
        
        # Hotkey info
        hotkey_frame = tk.Frame(record_frame, bg='#2a2a2a')
        hotkey_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        tk.Label(hotkey_frame, text="Hotkeys: ` = Toggle Recording | ESC = Emergency Stop",
                font=('Segoe UI', 8, 'italic'),
                fg='#95a5a6', bg='#2a2a2a').pack()
    
    def create_save_section(self, parent):
        """Create the macro save section"""
        # Save section
        save_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        save_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(save_frame, text="💾 Save Macro", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Name and category inputs
        input_frame = tk.Frame(save_frame, bg='#2a2a2a')
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Name input
        name_frame = tk.Frame(input_frame, bg='#2a2a2a')
        name_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(name_frame, text="Name:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.macro_name_entry = tk.Entry(name_frame, font=('Segoe UI', 9),
                                       bg='#ffffff', fg='#000000', 
                                       insertbackground='#000000',
                                       relief=tk.RAISED, bd=2)
        self.macro_name_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Category selection
        category_frame = tk.Frame(input_frame, bg='#2a2a2a')
        category_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(category_frame, text="Category:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.category_var = tk.StringVar(value="General")
        category_options = ["General", "Movement", "Battles", "Inventory", "Trading", "Custom"]
        self.category_dropdown = ttk.Combobox(category_frame, textvariable=self.category_var,
                                            values=category_options, state="readonly",
                                            font=('Segoe UI', 9))
        self.category_dropdown.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Save button
        self.save_button = tk.Button(save_frame, text="💾 Save Macro", 
                                   command=self.save_macro,
                                   font=('Segoe UI', 9, 'bold'),
                                   fg='#ffffff', bg='#28a745',
                                   activeforeground='#ffffff', activebackground='#218838',
                                   relief=tk.RAISED, bd=2, pady=8,
                                   state='disabled')
        self.save_button.pack(fill=tk.X, padx=10, pady=(0, 8))
    
    def create_fishing_tab(self):
        """Create the fishing tab content (placeholder)"""
        placeholder_frame = tk.Frame(self.fishing_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        placeholder_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(placeholder_frame, text="🎣 Fishing Bot", 
                font=('Segoe UI', 12, 'bold'), 
                fg='#00d4ff', bg='#2a2a2a').pack(pady=20)
        
        tk.Label(placeholder_frame, text="Coming Soon!\n\nAutomated fishing functionality\nwill be implemented here.", 
                font=('Segoe UI', 10), 
                fg='#cccccc', bg='#2a2a2a',
                justify=tk.CENTER).pack(pady=20)
        
        # Placeholder button
        tk.Button(placeholder_frame, text="Start Fishing (Coming Soon)", 
                 font=('Segoe UI', 10, 'bold'),
                 fg='#ffffff', bg='#7f8c8d',
                 state='disabled',
                 relief=tk.FLAT, bd=0, pady=10).pack(pady=20)
    
    def create_auto_hunt_tab(self):
        """Create the PP-based Auto Hunt tab content"""
        hunt_container = tk.Frame(self.auto_hunt_frame, bg='#1e1e1e')
        hunt_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Make the frame scrollable
        canvas = tk.Canvas(hunt_container, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(hunt_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Title section
        title_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_frame, text="🎯 PP-Based Auto Hunt", 
                font=('Segoe UI', 12, 'bold'), 
                fg='#00d4ff', bg='#2a2a2a').pack(pady=(8, 4))
        
        tk.Label(title_frame, text="Automated hunting with PP management and macro integration", 
                font=('Segoe UI', 9), 
                fg='#cccccc', bg='#2a2a2a').pack(pady=(0, 8))
        
        # Status section
        status_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(status_frame, text="📊 Hunt Status", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 4))
        
        self.pp_hunt_status_label = tk.Label(status_frame, text="Ready to hunt", 
                                            font=('Segoe UI', 9), 
                                            fg='#95a5a6', bg='#2a2a2a')
        self.pp_hunt_status_label.pack(pady=(0, 2))
        
        # Statistics display
        stats_grid = tk.Frame(status_frame, bg='#2a2a2a')
        stats_grid.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Row 1: Encounters and PP Counter
        encounters_frame = tk.Frame(stats_grid, bg='#2a2a2a')
        encounters_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(encounters_frame, text="Encounters:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        self.pp_encounters_label = tk.Label(encounters_frame, text="0", font=('Segoe UI', 10, 'bold'), 
                                           fg='#e74c3c', bg='#2a2a2a')
        self.pp_encounters_label.pack(anchor=tk.W)
        
        pp_frame = tk.Frame(stats_grid, bg='#2a2a2a')
        pp_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(pp_frame, text="PP Used:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        self.pp_counter_label = tk.Label(pp_frame, text="0/20", font=('Segoe UI', 10, 'bold'), 
                                        fg='#f39c12', bg='#2a2a2a')
        self.pp_counter_label.pack(anchor=tk.W)
        
        hunt_time_frame = tk.Frame(stats_grid, bg='#2a2a2a')
        hunt_time_frame.pack(side=tk.RIGHT)
        
        tk.Label(hunt_time_frame, text="Time:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.E)
        self.pp_hunt_time_label = tk.Label(hunt_time_frame, text="00:00", font=('Segoe UI', 10, 'bold'), 
                                          fg='#3498db', bg='#2a2a2a')
        self.pp_hunt_time_label.pack(anchor=tk.E)
        
        # Macro selection section
        macro_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        macro_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(macro_frame, text="🎯 Movement Macro", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        macro_controls = tk.Frame(macro_frame, bg='#2a2a2a')
        macro_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        tk.Label(macro_controls, text="Macro for returning to hunt spot:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        
        self.pp_macro_var = tk.StringVar(value="No macro selected")
        self.pp_macro_dropdown = ttk.Combobox(macro_controls, textvariable=self.pp_macro_var, 
                                             state="readonly", width=25, font=('Segoe UI', 8))
        self.pp_macro_dropdown.pack(side=tk.LEFT, pady=(5, 0))
        self.pp_macro_dropdown.bind('<<ComboboxSelected>>', self.on_pp_macro_selected)
        
        tk.Button(macro_controls, text="🔄", command=self.refresh_pp_macro_list,
                 font=('Segoe UI', 8), fg='#ffffff', bg='#34495e',
                 activeforeground='#ffffff', activebackground='#2c3e50',
                 relief=tk.RAISED, bd=1, width=3).pack(side=tk.LEFT, padx=(5, 0), pady=(5, 0))
        
        # Configuration section
        config_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(config_frame, text="⚙️ Hunt Configuration", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Settings grid
        settings_grid = tk.Frame(config_frame, bg='#2a2a2a')
        settings_grid.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Row 1: Max Encounters and Movement Interval
        tk.Label(settings_grid, text="Max Encounters (PP):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.pp_max_encounters_var = tk.StringVar(value="20")
        encounters_spinbox = tk.Spinbox(settings_grid, from_=1, to=100, width=5, 
                                       textvariable=self.pp_max_encounters_var, 
                                       command=self.update_pp_hunt_config)
        encounters_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        tk.Label(settings_grid, text="Movement Interval (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=0, column=2, sticky=tk.W, pady=2)
        
        self.pp_movement_interval_var = tk.StringVar(value="0.5")
        movement_spinbox = tk.Spinbox(settings_grid, from_=0.1, to=5.0, increment=0.1, width=5,
                                     textvariable=self.pp_movement_interval_var, 
                                     command=self.update_pp_hunt_config)
        movement_spinbox.grid(row=0, column=3, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Row 2: Key Hold Duration and Battle Key Interval
        tk.Label(settings_grid, text="Key Hold Duration (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=1, column=0, sticky=tk.W, pady=2)
        
        self.pp_key_hold_var = tk.StringVar(value="1.0")
        key_hold_spinbox = tk.Spinbox(settings_grid, from_=0.1, to=10.0, increment=0.1, width=5,
                                     textvariable=self.pp_key_hold_var, 
                                     command=self.update_pp_hunt_config)
        key_hold_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        tk.Label(settings_grid, text="Battle E Interval (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=1, column=2, sticky=tk.W, pady=2)
        
        self.pp_battle_interval_var = tk.StringVar(value="0.2")
        battle_spinbox = tk.Spinbox(settings_grid, from_=0.1, to=2.0, increment=0.1, width=5,
                                   textvariable=self.pp_battle_interval_var, 
                                   command=self.update_pp_hunt_config)
        battle_spinbox.grid(row=1, column=3, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Row 3: Heal Delay
        tk.Label(settings_grid, text="Heal Delay (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=2, column=0, sticky=tk.W, pady=2)
        
        self.pp_heal_delay_var = tk.StringVar(value="3.0")
        heal_spinbox = tk.Spinbox(settings_grid, from_=0.5, to=60.0, increment=0.5, width=5,
                                 textvariable=self.pp_heal_delay_var, 
                                 command=self.update_pp_hunt_config)
        heal_spinbox.grid(row=2, column=1, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Battle sequence section
        battle_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        battle_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(battle_frame, text="⚔️ Battle Sequence Configuration", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Battle settings grid
        battle_settings_grid = tk.Frame(battle_frame, bg='#2a2a2a')
        battle_settings_grid.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Row 1: Initial E presses and Post-E delay
        tk.Label(battle_settings_grid, text="Initial E Presses:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.pp_initial_e_var = tk.StringVar(value="6")
        initial_e_spinbox = tk.Spinbox(battle_settings_grid, from_=1, to=20, width=5, 
                                      textvariable=self.pp_initial_e_var, 
                                      command=self.update_pp_hunt_config)
        initial_e_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        tk.Label(battle_settings_grid, text="Post-E Delay (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=0, column=2, sticky=tk.W, pady=2)
        
        self.pp_post_e_delay_var = tk.StringVar(value="8.5")
        post_e_spinbox = tk.Spinbox(battle_settings_grid, from_=0.0, to=30.0, increment=0.5, width=5,
                                   textvariable=self.pp_post_e_delay_var, 
                                   command=self.update_pp_hunt_config)
        post_e_spinbox.grid(row=0, column=3, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Row 2: Loop duration and Loop type
        tk.Label(battle_settings_grid, text="Loop Duration (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=1, column=0, sticky=tk.W, pady=2)
        
        self.pp_loop_duration_var = tk.StringVar(value="12.0")
        loop_duration_spinbox = tk.Spinbox(battle_settings_grid, from_=1.0, to=60.0, increment=1.0, width=5,
                                          textvariable=self.pp_loop_duration_var, 
                                          command=self.update_pp_hunt_config)
        loop_duration_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        tk.Label(battle_settings_grid, text="Loop Type:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=1, column=2, sticky=tk.W, pady=2)
        
        self.pp_loop_type_var = tk.StringVar(value="e+e")
        loop_type_combo = ttk.Combobox(battle_settings_grid, textvariable=self.pp_loop_type_var, 
                                      values=["e+e", "x+e"], state="readonly", width=6, 
                                      font=('Segoe UI', 8))
        loop_type_combo.bind('<<ComboboxSelected>>', lambda e: self.update_pp_hunt_config())
        loop_type_combo.grid(row=1, column=3, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Row 3: Loop interval
        tk.Label(battle_settings_grid, text="Loop Interval (s):", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').grid(row=2, column=0, sticky=tk.W, pady=2)
        
        self.pp_loop_interval_var = tk.StringVar(value="0.3")
        loop_interval_spinbox = tk.Spinbox(battle_settings_grid, from_=0.1, to=2.0, increment=0.1, width=5,
                                          textvariable=self.pp_loop_interval_var, 
                                          command=self.update_pp_hunt_config)
        loop_interval_spinbox.grid(row=2, column=1, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Control buttons
        control_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(control_frame, text="🎮 Hunt Controls", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Button row - Main controls
        button_row = tk.Frame(control_frame, bg='#2a2a2a')
        button_row.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Start Hunt button
        self.start_pp_hunt_btn = tk.Button(button_row, text="🎯 Start Hunt", 
                                          command=self.start_pp_hunt,
                                          font=('Segoe UI', 9, 'bold'),
                                          fg='#ffffff', bg='#27ae60',
                                          activeforeground='#ffffff', activebackground='#229954',
                                          relief=tk.RAISED, bd=2, pady=6)
        self.start_pp_hunt_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        # Start without macro button
        self.start_pp_no_macro_btn = tk.Button(button_row, text="🎯 Start Here", 
                                              command=self.start_pp_hunt_no_macro,
                                              font=('Segoe UI', 9, 'bold'),
                                              fg='#ffffff', bg='#16a085',
                                              activeforeground='#ffffff', activebackground='#138d75',
                                              relief=tk.RAISED, bd=2, pady=6)
        self.start_pp_no_macro_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 3))
        
        # Pause Hunt button
        self.pause_pp_hunt_btn = tk.Button(button_row, text="⏸ Pause", 
                                          command=self.pause_pp_hunt,
                                          font=('Segoe UI', 9, 'bold'),
                                          fg='#ffffff', bg='#f39c12',
                                          activeforeground='#ffffff', activebackground='#e67e22',
                                          relief=tk.RAISED, bd=2, pady=6, state=tk.DISABLED)
        self.pause_pp_hunt_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 3))
        
        # Stop Hunt button
        self.stop_pp_hunt_btn = tk.Button(button_row, text="⏹ Stop", 
                                         command=self.stop_pp_hunt,
                                         font=('Segoe UI', 9, 'bold'),
                                         fg='#ffffff', bg='#e74c3c',
                                         activeforeground='#ffffff', activebackground='#c0392b',
                                         relief=tk.RAISED, bd=2, pady=6, state=tk.DISABLED)
        self.stop_pp_hunt_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        
        # Second row for additional controls
        button_row2 = tk.Frame(control_frame, bg='#2a2a2a')
        button_row2.pack(fill=tk.X, pady=(4, 0))
        
        # Force reset button
        self.force_reset_pp_btn = tk.Button(button_row2, text="🔧 Force Reset", 
                                           command=self.force_reset_pp_hunt,
                                           font=('Segoe UI', 8, 'bold'),
                                           fg='#ffffff', bg='#8e44ad',
                                           activeforeground='#ffffff', activebackground='#7d3c98',
                                           relief=tk.RAISED, bd=2, pady=4)
        self.force_reset_pp_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add explanation for force reset
        tk.Label(button_row2, text="Use if 'hunt in progress' error occurs", 
                font=('Segoe UI', 7), 
                fg='#95a5a6', bg='#2a2a2a').pack(side=tk.LEFT, padx=(10, 0))
        
        # Test section
        test_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(test_frame, text="🧪 Testing Tools", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Test buttons row
        test_button_row = tk.Frame(test_frame, bg='#2a2a2a')
        test_button_row.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Test Battle Menu button
        tk.Button(test_button_row, text="⚔️ Test Battle Menu", 
                 command=self.test_battle_menu,
                 font=('Segoe UI', 9),
                 fg='#ffffff', bg='#00b894',
                 activeforeground='#ffffff', activebackground='#00a085',
                 relief=tk.RAISED, bd=1, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Open Screenshots button
        tk.Button(test_button_row, text="📁 Screenshots", 
                 command=self.open_screenshots_folder,
                 font=('Segoe UI', 9),
                 fg='#ffffff', bg='#fd79a8',
                 activeforeground='#ffffff', activebackground='#e84393',
                 relief=tk.RAISED, bd=1, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Preset management section
        preset_frame = tk.Frame(scrollable_frame, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(preset_frame, text="💾 Configuration Presets", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Preset controls
        preset_controls = tk.Frame(preset_frame, bg='#2a2a2a')
        preset_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Preset dropdown and controls
        preset_row1 = tk.Frame(preset_controls, bg='#2a2a2a')
        preset_row1.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(preset_row1, text="Select Preset:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.pp_preset_var = tk.StringVar(value="No preset selected")
        self.pp_preset_dropdown = ttk.Combobox(preset_row1, textvariable=self.pp_preset_var, 
                                              state="readonly", width=20, font=('Segoe UI', 8))
        self.pp_preset_dropdown.pack(side=tk.LEFT, padx=(5, 5))
        
        tk.Button(preset_row1, text="🔄", command=self.refresh_pp_preset_list,
                 font=('Segoe UI', 8), fg='#ffffff', bg='#34495e',
                 activeforeground='#ffffff', activebackground='#2c3e50',
                 relief=tk.RAISED, bd=1, width=3).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(preset_row1, text="📥 Load", command=self.load_pp_preset,
                 font=('Segoe UI', 8, 'bold'), fg='#ffffff', bg='#3498db',
                 activeforeground='#ffffff', activebackground='#2980b9',
                 relief=tk.RAISED, bd=1, width=8).pack(side=tk.LEFT, padx=(0, 2))
        
        tk.Button(preset_row1, text="🗑️ Delete", command=self.delete_pp_preset,
                 font=('Segoe UI', 8, 'bold'), fg='#ffffff', bg='#e74c3c',
                 activeforeground='#ffffff', activebackground='#c0392b',
                 relief=tk.RAISED, bd=1, width=8).pack(side=tk.LEFT)
        
        # Save preset row
        preset_row2 = tk.Frame(preset_controls, bg='#2a2a2a')
        preset_row2.pack(fill=tk.X)
        
        tk.Label(preset_row2, text="Save as:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.pp_save_preset_var = tk.StringVar()
        tk.Entry(preset_row2, textvariable=self.pp_save_preset_var, width=15, 
                font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(5, 5))
        
        tk.Button(preset_row2, text="💾 Save", command=self.save_pp_preset,
                 font=('Segoe UI', 8, 'bold'), fg='#ffffff', bg='#27ae60',
                 activeforeground='#ffffff', activebackground='#229954',
                 relief=tk.RAISED, bd=1, width=8).pack(side=tk.LEFT)
        
        # Add explanatory text
        explanation_frame = tk.Frame(scrollable_frame, bg='#2a2a2a')
        explanation_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        explanation_text = ("💡 PP Hunt Guide:\n"
                           "• Set max encounters to match your move's PP (e.g., 20 for most moves)\n" 
                           "• Hunt will move A → D pattern (holding each key for the specified duration)\n"
                           "• Key Hold Duration: how long to hold A and D keys (1.0s = 1 second hold)\n"
                           "• Battle sequence: Initial E presses → Post-E delay → E+E or X+E loop\n"
                           "• E+E sequence: press E, E repeatedly | X+E sequence: press X, E repeatedly\n"
                           "• After max encounters: heals with key '7' and returns to position via macro\n"
                           "• Select a movement macro to return to hunt spot after healing\n"
                           "• Use 'Start Here' to begin hunting from current position")
        
        tk.Label(explanation_frame, text=explanation_text, font=('Segoe UI', 7), 
                fg='#95a5a6', bg='#2a2a2a', justify=tk.LEFT).pack(anchor=tk.W)
        
        # Refresh macro list on startup
        self.refresh_pp_macro_list()
        self.refresh_pp_preset_list()
        
        # Setup PP Auto Hunt callbacks
        self.pp_auto_hunt_engine.set_status_callback(self.on_pp_hunt_status_update)
        self.pp_auto_hunt_engine.set_encounter_callback(self.on_pp_encounter_detected)
    
    def create_sweet_scent_tab(self):
        """Create the Sweet Scent tab content with scrolling"""
        # Initialize configuration variables first
        self.use_e_plus_e_var = tk.BooleanVar(value=False)
        self.heal_delay_var = tk.StringVar(value="2.0")
        self.cycle_pause_var = tk.StringVar(value="1.0")
        self.initial_focus_delay_var = tk.StringVar(value="2.0")
        self.post_e_delay_var = tk.StringVar(value="1.0")
        self.debug_pokecenter_var = tk.BooleanVar(value=False)
        self.debug_s_duration_var = tk.StringVar(value="2.0")
        self.debug_e_duration_var = tk.StringVar(value="3.0")
        self.debug_e_interval_var = tk.StringVar(value="0.2")
        self.debug_check_interval_var = tk.StringVar(value="60.0")
        
        # Create scrollable frame
        main_frame = tk.Frame(self.sweet_scent_frame, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scent_container = tk.Frame(canvas, bg='#1e1e1e')
        
        # Configure scrolling
        scent_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scent_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Title section
        title_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_frame, text="🌸 Sweet Scent System", 
                font=('Segoe UI', 12, 'bold'), 
                fg='#00d4ff', bg='#2a2a2a').pack(pady=(8, 4))
        
        tk.Label(title_frame, text="Automated Sweet Scent encounters with PP management", 
                font=('Segoe UI', 9), 
                fg='#cccccc', bg='#2a2a2a').pack(pady=(0, 8))
        
        # Status section
        status_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(status_frame, text="📊 Sweet Scent Status", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 4))
        
        self.sweet_scent_status_label = tk.Label(status_frame, text="Ready for Sweet Scent", 
                                                font=('Segoe UI', 9), 
                                                fg='#95a5a6', bg='#2a2a2a')
        self.sweet_scent_status_label.pack(pady=(0, 2))
        
        # Statistics display
        stats_inner = tk.Frame(status_frame, bg='#2a2a2a')
        stats_inner.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Sweet Scent cycles
        cycles_frame = tk.Frame(stats_inner, bg='#2a2a2a')
        cycles_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(cycles_frame, text="Sweet Scent Cycles:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        self.scent_cycles_label = tk.Label(cycles_frame, text="0", font=('Segoe UI', 10, 'bold'), 
                                          fg='#e74c3c', bg='#2a2a2a')
        self.scent_cycles_label.pack(anchor=tk.W)
        
        # PP usage
        pp_frame = tk.Frame(stats_inner, bg='#2a2a2a')
        pp_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(pp_frame, text="PP Usage:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        self.pp_usage_label = tk.Label(pp_frame, text="0/6", font=('Segoe UI', 10, 'bold'), 
                                      fg='#f39c12', bg='#2a2a2a')
        self.pp_usage_label.pack(anchor=tk.W)
        
        # Hunt time
        time_frame = tk.Frame(stats_inner, bg='#2a2a2a')
        time_frame.pack(side=tk.RIGHT)
        
        tk.Label(time_frame, text="Hunt Time:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.E)
        self.hunt_time_label = tk.Label(time_frame, text="00:00", font=('Segoe UI', 10, 'bold'), 
                                       fg='#3498db', bg='#2a2a2a')
        self.hunt_time_label.pack(anchor=tk.E)
        
        # Macro selection section
        macro_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        macro_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(macro_frame, text="🎮 Movement Macro", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Macro selection controls
        macro_controls = tk.Frame(macro_frame, bg='#2a2a2a')
        macro_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        tk.Label(macro_controls, text="Select Macro:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(anchor=tk.W)
        
        self.selected_macro_var = tk.StringVar()
        self.macro_combobox = ttk.Combobox(macro_controls, textvariable=self.selected_macro_var,
                                          state="readonly", font=('Segoe UI', 9))
        self.macro_combobox.pack(fill=tk.X, pady=(4, 8))
        self.macro_combobox.bind('<<ComboboxSelected>>', self.on_macro_selected)
        
        # Refresh macros button
        tk.Button(macro_controls, text="🔄 Refresh Macros", 
                 command=self.refresh_macro_list,
                 font=('Segoe UI', 8),
                 fg='#ffffff', bg='#6c757d',
                 activeforeground='#ffffff', activebackground='#5a6268',
                 relief=tk.RAISED, bd=1, pady=4).pack(fill=tk.X)
        
        # Sweet Scent configuration section
        config_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(config_frame, text="⚙️ Sweet Scent Configuration", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        config_inner = tk.Frame(config_frame, bg='#2a2a2a')
        config_inner.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Sweet Scent uses
        uses_frame = tk.Frame(config_inner, bg='#2a2a2a')
        uses_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(uses_frame, text="Sweet Scent Uses per Cycle:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.sweet_scent_uses_var = tk.StringVar(value="6")
        tk.Entry(uses_frame, textvariable=self.sweet_scent_uses_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Animation delay
        delay_frame = tk.Frame(config_inner, bg='#2a2a2a')
        delay_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(delay_frame, text="Sweet Scent Animation Delay (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.animation_delay_var = tk.StringVar(value="4.0")
        tk.Entry(delay_frame, textvariable=self.animation_delay_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Initial E presses
        e_presses_frame = tk.Frame(config_inner, bg='#2a2a2a')
        e_presses_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(e_presses_frame, text="Initial E Presses:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.initial_e_presses_var = tk.StringVar(value="3")
        tk.Entry(e_presses_frame, textvariable=self.initial_e_presses_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Initial E interval
        e_interval_frame = tk.Frame(config_inner, bg='#2a2a2a')
        e_interval_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(e_interval_frame, text="Initial E Interval (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.initial_e_interval_var = tk.StringVar(value="0.4")
        tk.Entry(e_interval_frame, textvariable=self.initial_e_interval_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Loop duration
        loop_duration_frame = tk.Frame(config_inner, bg='#2a2a2a')
        loop_duration_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(loop_duration_frame, text="Encounter Loop Duration (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.loop_duration_var = tk.StringVar(value="10.0")
        tk.Entry(loop_duration_frame, textvariable=self.loop_duration_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Loop interval
        loop_interval_frame = tk.Frame(config_inner, bg='#2a2a2a')
        loop_interval_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(loop_interval_frame, text="Loop Interval (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.loop_interval_var = tk.StringVar(value="0.2")
        tk.Entry(loop_interval_frame, textvariable=self.loop_interval_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Loop type selection
        loop_type_frame = tk.Frame(config_inner, bg='#2a2a2a')
        loop_type_frame.pack(fill=tk.X, pady=(4, 8))
        
        tk.Checkbutton(loop_type_frame, text="Use E+E Loop (instead of X E presses)",
                      variable=self.use_e_plus_e_var,
                      command=self.update_sweet_scent_config,
                      font=('Segoe UI', 9),
                      fg='#ffffff', bg='#2a2a2a',
                      selectcolor='#2a2a2a',
                      activeforeground='#ffffff', activebackground='#2a2a2a',
                      borderwidth=0).pack(side=tk.LEFT)
        
        # Advanced timing configuration section
        advanced_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        advanced_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(advanced_frame, text="⏱️ Advanced Timing Configuration", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        advanced_inner = tk.Frame(advanced_frame, bg='#2a2a2a')
        advanced_inner.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Heal delay
        heal_delay_frame = tk.Frame(advanced_inner, bg='#2a2a2a')
        heal_delay_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(heal_delay_frame, text="Heal Animation Delay (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        tk.Entry(heal_delay_frame, textvariable=self.heal_delay_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Cycle pause
        cycle_pause_frame = tk.Frame(advanced_inner, bg='#2a2a2a')
        cycle_pause_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(cycle_pause_frame, text="Cycle Pause Delay (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        tk.Entry(cycle_pause_frame, textvariable=self.cycle_pause_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Initial focus delay
        focus_delay_frame = tk.Frame(advanced_inner, bg='#2a2a2a')
        focus_delay_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(focus_delay_frame, text="Initial Focus Delay (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        tk.Entry(focus_delay_frame, textvariable=self.initial_focus_delay_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Post E delay
        post_e_delay_frame = tk.Frame(advanced_inner, bg='#2a2a2a')
        post_e_delay_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(post_e_delay_frame, text="Post E Press Delay (s):", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        tk.Entry(post_e_delay_frame, textvariable=self.post_e_delay_var, font=('Segoe UI', 9),
                bg='#ffffff', fg='#000000', width=8).pack(side=tk.RIGHT)
        
        # Debug/Pokecenter section
        debug_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        debug_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(debug_frame, text="🔧 Debug & Pokecenter Escape", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        debug_inner = tk.Frame(debug_frame, bg='#2a2a2a')
        debug_inner.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Enable pokecenter detection
        pokecenter_frame = tk.Frame(debug_inner, bg='#2a2a2a')
        pokecenter_frame.pack(fill=tk.X, pady=(0, 4))
        
        tk.Checkbutton(pokecenter_frame, text="Enable Pokecenter Stuck Detection",
                      variable=self.debug_pokecenter_var,
                      font=('Segoe UI', 9),
                      fg='#ffffff', bg='#2a2a2a',
                      selectcolor='#2a2a2a',
                      activeforeground='#ffffff', activebackground='#2a2a2a',
                      borderwidth=0).pack(side=tk.LEFT)
        
        # Manual escape button
        escape_frame = tk.Frame(debug_inner, bg='#2a2a2a')
        escape_frame.pack(fill=tk.X, pady=(4, 8))
        
        tk.Button(escape_frame, text="🚪 Manual Pokecenter Escape", 
                 command=self.manual_pokecenter_escape,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#fd7e14',
                 activeforeground='#ffffff', activebackground='#e8590c',
                 relief=tk.RAISED, bd=2, pady=6).pack(fill=tk.X)
        
        tk.Label(escape_frame, text="Use this if stuck in pokecenter dialogue", 
                font=('Segoe UI', 8, 'italic'),
                fg='#95a5a6', bg='#2a2a2a').pack(pady=(2, 0))
        
        # Control buttons
        control_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(control_frame, text="🎮 Sweet Scent Controls", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Button row 1
        buttons1 = tk.Frame(control_frame, bg='#2a2a2a')
        buttons1.pack(fill=tk.X, padx=10, pady=(0, 4))
        
        self.start_scent_btn = tk.Button(buttons1, text="🌸 Start Hunt", 
                 command=self.start_sweet_scent,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#28a745',
                 activeforeground='#ffffff', activebackground='#1e7e34',
                 relief=tk.RAISED, bd=2, pady=6)
        self.start_scent_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        self.start_no_macro_btn = tk.Button(buttons1, text="📍 Start Here", 
                 command=self.start_sweet_scent_no_macro,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#17a2b8',
                 activeforeground='#ffffff', activebackground='#138496',
                 relief=tk.RAISED, bd=2, pady=6)
        self.start_no_macro_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Button row 2
        buttons2 = tk.Frame(control_frame, bg='#2a2a2a')
        buttons2.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        self.pause_scent_btn = tk.Button(buttons2, text="⏸️ Pause/Resume", 
                 command=self.pause_sweet_scent,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#ffc107',
                 activeforeground='#000000', activebackground='#e0a800',
                 relief=tk.RAISED, bd=2, pady=6)
        self.pause_scent_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        self.stop_scent_btn = tk.Button(buttons2, text="🛑 Stop Hunt", 
                 command=self.stop_sweet_scent,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#dc3545',
                 activeforeground='#ffffff', activebackground='#c82333',
                 relief=tk.RAISED, bd=2, pady=6)
        self.stop_scent_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Preset management section
        preset_frame = tk.Frame(scent_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(preset_frame, text="💾 Preset Management", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        preset_controls = tk.Frame(preset_frame, bg='#2a2a2a')
        preset_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        # Preset selection
        tk.Label(preset_controls, text="Select Preset:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(anchor=tk.W)
        
        self.selected_preset_var = tk.StringVar()
        self.preset_combobox = ttk.Combobox(preset_controls, textvariable=self.selected_preset_var,
                                           state="readonly", font=('Segoe UI', 9))
        self.preset_combobox.pack(fill=tk.X, pady=(4, 8))
        
        # Preset buttons
        preset_buttons = tk.Frame(preset_controls, bg='#2a2a2a')
        preset_buttons.pack(fill=tk.X, pady=(0, 4))
        
        tk.Button(preset_buttons, text="💾 Save", 
                 command=self.save_preset,
                 font=('Segoe UI', 8, 'bold'),
                 fg='#ffffff', bg='#28a745',
                 relief=tk.RAISED, bd=1, pady=4).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        tk.Button(preset_buttons, text="📁 Load", 
                 command=self.load_preset,
                 font=('Segoe UI', 8, 'bold'),
                 fg='#ffffff', bg='#007bff',
                 relief=tk.RAISED, bd=1, pady=4).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 2))
        
        tk.Button(preset_buttons, text="🗑️ Delete", 
                 command=self.delete_preset,
                 font=('Segoe UI', 8, 'bold'),
                 fg='#ffffff', bg='#dc3545',
                 relief=tk.RAISED, bd=1, pady=4).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Initialize UI
        self.refresh_macro_list()
        self.refresh_preset_list()
        
        # Set up callbacks
        self.sweet_scent_engine.set_status_callback(self.on_sweet_scent_status_update)
        self.sweet_scent_engine.set_encounter_callback(self.on_sweet_scent_status_update)
    
    def create_settings_tab(self):
        """Create the settings tab content"""
        settings_container = tk.Frame(self.settings_frame, bg='#1e1e1e')
        settings_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title section
        title_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_frame, text="⚙️ Settings & Configuration", 
                font=('Segoe UI', 12, 'bold'), 
                fg='#00d4ff', bg='#2a2a2a').pack(pady=(8, 4))
        
        tk.Label(title_frame, text="Configure PokeMMO window detection and application settings", 
                font=('Segoe UI', 9), 
                fg='#cccccc', bg='#2a2a2a').pack(pady=(0, 8))
        
        # Window selection section
        window_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        window_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(window_frame, text="🎮 PokeMMO Window Selection", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        window_controls = tk.Frame(window_frame, bg='#2a2a2a')
        window_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        tk.Button(window_controls, text="🔍 Select PokeMMO Window", 
                 command=self.select_pokemmo_window,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#007bff',
                 activeforeground='#ffffff', activebackground='#0056b3',
                 relief=tk.RAISED, bd=2, pady=6).pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(window_controls, text="Use this to manually select the PokeMMO game window", 
                font=('Segoe UI', 8), 
                fg='#95a5a6', bg='#2a2a2a').pack()
        
        # Template management section
        template_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        template_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(template_frame, text="🖼️ Template Management", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        template_controls = tk.Frame(template_frame, bg='#2a2a2a')
        template_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        template_buttons = tk.Frame(template_controls, bg='#2a2a2a')
        template_buttons.pack(fill=tk.X, pady=(0, 4))
        
        tk.Button(template_buttons, text="📸 Capture Template", 
                 command=self.capture_template,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#28a745',
                 activeforeground='#ffffff', activebackground='#1e7e34',
                 relief=tk.RAISED, bd=2, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        tk.Button(template_buttons, text="🔄 Load Templates", 
                 command=self.load_templates,
                 font=('Segoe UI', 9, 'bold'),
                 fg='#ffffff', bg='#17a2b8',
                 activeforeground='#ffffff', activebackground='#138496',
                 relief=tk.RAISED, bd=2, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        tk.Label(template_controls, text="Capture and manage battle menu detection templates", 
                font=('Segoe UI', 8), 
                fg='#95a5a6', bg='#2a2a2a').pack()
        
        # Testing section
        test_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        test_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(test_frame, text="🧪 Testing Tools", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        test_controls = tk.Frame(test_frame, bg='#2a2a2a')
        test_controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        test_buttons_row1 = tk.Frame(test_controls, bg='#2a2a2a')
        test_buttons_row1.pack(fill=tk.X, pady=(0, 4))
        
        tk.Button(test_buttons_row1, text="⚔️ Test Battle Menu", 
                 command=self.test_battle_menu,
                 font=('Segoe UI', 9),
                 fg='#ffffff', bg='#fd7e14',
                 activeforeground='#ffffff', activebackground='#e8590c',
                 relief=tk.RAISED, bd=1, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        
        tk.Button(test_buttons_row1, text="🖥️ Test Full Screen", 
                 command=self.test_full_screen,
                 font=('Segoe UI', 9),
                 fg='#ffffff', bg='#6610f2',
                 activeforeground='#ffffff', activebackground='#520dc2',
                 relief=tk.RAISED, bd=1, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 2))
        
        tk.Button(test_buttons_row1, text="📁 Screenshots", 
                 command=self.open_screenshots_folder,
                 font=('Segoe UI', 9),
                 fg='#ffffff', bg='#fd79a8',
                 activeforeground='#ffffff', activebackground='#e84393',
                 relief=tk.RAISED, bd=1, pady=6).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        tk.Label(test_controls, text="Test detection features and access debug screenshots", 
                font=('Segoe UI', 8), 
                fg='#95a5a6', bg='#2a2a2a').pack()
        
        # About section
        about_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        about_frame.pack(fill=tk.X)
        
        tk.Label(about_frame, text="ℹ️ About", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        about_text = ("PokeMMO Overlay - Macro System v2.0\n"
                     "🔧 Record and playback keyboard/mouse actions\n"
                     "🎯 Automated hunting with PP management\n" 
                     "🌸 Sweet Scent automation system\n"
                     "⚠️  Use responsibly and check PokeMMO ToS!")
        
        tk.Label(about_frame, text=about_text, 
                font=('Segoe UI', 8), 
                fg='#95a5a6', bg='#2a2a2a', justify=tk.CENTER).pack(pady=(0, 8))
    
    def create_macro_section(self, parent):
        """Create macro management section"""
        macro_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        macro_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(macro_frame, text="Saved Macros", 
                font=('Segoe UI', 11, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(8, 8))
        
        # Filter section
        filter_frame = tk.Frame(macro_frame, bg='#2a2a2a')
        filter_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
        
        tk.Label(filter_frame, text="Filter:", font=('Segoe UI', 9), 
                fg='#bdc3c7', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.filter_combo = ttk.Combobox(filter_frame, 
                                       values=["All"] + list(MACRO_CATEGORIES.keys()),
                                       font=('Segoe UI', 9),
                                       style='Dark.TCombobox',
                                       state='readonly', width=15)
        self.filter_combo.pack(side=tk.RIGHT)
        self.filter_combo.set("All")
        self.filter_combo.bind('<<ComboboxSelected>>', self.update_macro_list)
        
        # Macro list
        list_frame = tk.Frame(macro_frame, bg='#2a2a2a')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        
        # Scrollbar for listbox
        scrollbar = tk.Scrollbar(list_frame, bg='#ffffff', troughcolor='#e9ecef',
                               activebackground='#007bff')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.macro_listbox = tk.Listbox(list_frame, height=4,
                                      font=('Segoe UI', 9),
                                      bg='#ffffff', fg='#000000',
                                      selectbackground='#007bff', selectforeground='#ffffff',
                                      relief=tk.RAISED, bd=2,
                                      yscrollcommand=scrollbar.set)
        self.macro_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.macro_listbox.yview)
        
        # Control buttons
        self.create_control_buttons(macro_frame)
        
        # Initialize macro list
        self.update_macro_list()
    
    def create_control_buttons(self, parent):
        """Create playback control buttons"""
        # Loop controls
        loop_frame = tk.Frame(parent, bg='#2a2a2a')
        loop_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        
        tk.Label(loop_frame, text="Loops:", font=('Segoe UI', 9), 
                fg='#ffffff', bg='#2a2a2a').pack(side=tk.LEFT)
        
        self.loop_entry = tk.Entry(loop_frame, width=4, font=('Segoe UI', 9),
                                 bg='#ffffff', fg='#000000', 
                                 insertbackground='#000000',
                                 relief=tk.RAISED, bd=2)
        self.loop_entry.pack(side=tk.LEFT, padx=(8, 8))
        self.loop_entry.insert(0, "1")
        
        self.infinite_loop_var = tk.BooleanVar()
        self.infinite_loop_cb = tk.Checkbutton(loop_frame, text="Infinite", 
                                             variable=self.infinite_loop_var,
                                             font=('Segoe UI', 9),
                                             fg='#ffffff', bg='#2a2a2a',
                                             selectcolor='#ffffff',
                                             activeforeground='#ffffff',
                                             activebackground='#2a2a2a')
        self.infinite_loop_cb.pack(side=tk.LEFT)
        
        # Action buttons with better visibility
        button_frame = tk.Frame(parent, bg='#2a2a2a')
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.play_button = tk.Button(button_frame, text="▶️ Play", 
                                   command=self.play_macro,
                                   font=('Segoe UI', 9, 'bold'),
                                   fg='#ffffff', bg='#28a745',
                                   activeforeground='#ffffff', activebackground='#1e7e34',
                                   relief=tk.RAISED, bd=2, pady=8)
        self.play_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        
        self.loop_button = tk.Button(button_frame, text="🔄 Loop", 
                                   command=self.loop_macro,
                                   font=('Segoe UI', 9, 'bold'),
                                   fg='#ffffff', bg='#fd7e14',
                                   activeforeground='#ffffff', activebackground='#e8590c',
                                   relief=tk.RAISED, bd=2, pady=8)
        self.loop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 3))
        
        self.delete_button = tk.Button(button_frame, text="🗑️ Delete", 
                                     command=self.delete_macro,
                                     font=('Segoe UI', 9, 'bold'),
                                     fg='#ffffff', bg='#dc3545',
                                     activeforeground='#ffffff', activebackground='#c82333',
                                     relief=tk.RAISED, bd=2, pady=8)
        self.delete_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
    
    def on_key_press(self, event):
        """Handle key press events for hotkeys"""
        # Check for the « key (Left Guillemet)
        if event.char == '«' or event.keysym == 'guillemotleft':
            self.toggle_recording()
        elif event.keysym == 'Escape':
            # Emergency stop for any running macro
            if hasattr(self, 'input_manager'):
                self.input_manager.stop_playback = True
    
    def _toggle_mouse_recording(self):
        """Toggle mouse movement recording in input manager"""
        enabled = self.record_mouse_var.get()
        self.input_manager.set_record_mouse_movements(enabled)
        status_text = "enabled" if enabled else "disabled"
        print(f"🖱️ Mouse movement recording {status_text}")
        
        # Update status if not recording
        if not self.is_recording:
            mode = "keyboard-only" if not enabled else "full (keyboard + mouse)"
            self.record_status.config(text=f"Ready to record ({mode} mode)")
    
    def toggle_recording(self):
        """Toggle macro recording"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """Start recording macro"""
        if not self.window_manager.is_game_running():
            messagebox.showwarning("Game Not Found", 
                                 "Please start PokeMMO first!\n\nMake sure the game window is visible.")
            return
        
        if self.input_manager.start_recording():
            self.is_recording = True
            self.record_button.config(text="⏹️ Stop Recording", bg='#6c757d', activebackground='#5a6268')
            self.record_status.config(text="Recording... Click to stop", fg='#ffc107')
    
    def stop_recording(self):
        """Stop recording macro"""
        if self.is_recording:
            self.current_events = self.input_manager.stop_recording()
            self.is_recording = False
            self.record_button.config(text="🔴 Start Recording", bg='#dc3545', activebackground='#c82333')
            
            if self.current_events:
                self.record_status.config(text=f"Recorded {len(self.current_events)} events", fg='#28a745')
                self.save_button.config(state='normal')
            else:
                self.record_status.config(text="No events recorded", fg='#ffc107')
                self.save_button.config(state='disabled')
    
    def save_macro(self):
        """Save the recorded macro"""
        name = self.macro_name_entry.get().strip()
        category = self.category_dropdown.get()
        
        if not name:
            messagebox.showerror("Error", "Please enter a macro name!")
            return
        
        if not self.current_events:
            messagebox.showerror("Error", "No events to save!")
            return
        
        success, result = self.macro_manager.save_macro(name, self.current_events, category)
        if success:
            messagebox.showinfo("Success", f"Macro '{name}' saved successfully!")
            self.macro_name_entry.delete(0, tk.END)
            self.current_events = []
            self.save_button.config(state='disabled')
            self.record_status.config(text="Ready to record", fg='#6c757d')
            self.update_macro_list()
        else:
            messagebox.showerror("Error", f"Failed to save macro: {result}")
    
    def update_macro_list(self, event=None):
        """Update the macro list"""
        self.macro_listbox.delete(0, tk.END)
        
        category_filter = self.filter_combo.get()
        macros = self.macro_manager.get_macros(category_filter if category_filter != "All" else None)
        
        for macro in macros:
            display_name = f"[{macro['category']}] {macro['name']}"
            self.macro_listbox.insert(tk.END, display_name)
    
    def play_macro(self):
        """Play selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to play!")
            return
        
        macro_index = selection[0]
        category_filter = self.filter_combo.get()
        macros = self.macro_manager.get_macros(category_filter if category_filter != "All" else None)
        
        if macro_index < len(macros):
            macro = macros[macro_index]
            self.input_manager.play_macro(macro['events'], callback=self.playback_callback)
    
    def loop_macro(self):
        """Play selected macro in a loop"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to loop!")
            return
        
        try:
            if self.infinite_loop_var.get():
                loop_count = -1  # Infinite
            else:
                loop_count = int(self.loop_entry.get())
                if loop_count <= 0:
                    raise ValueError("Loop count must be positive")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid loop count!")
            return
        
        macro_index = selection[0]
        category_filter = self.filter_combo.get()
        macros = self.macro_manager.get_macros(category_filter if category_filter != "All" else None)
        
        if macro_index < len(macros):
            macro = macros[macro_index]
            self.input_manager.play_macro(macro['events'], loop_count=loop_count, callback=self.playback_callback)
    
    def delete_macro(self):
        """Delete selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to delete!")
            return
        
        macro_index = selection[0]
        category_filter = self.filter_combo.get()
        macros = self.macro_manager.get_macros(category_filter if category_filter != "All" else None)
        
        if macro_index < len(macros):
            macro = macros[macro_index]
            
            if messagebox.askyesno("Confirm Delete", f"Delete macro '{macro['name']}'?"):
                if self.macro_manager.delete_macro(macro['name']):
                    self.update_macro_list()
                else:
                    messagebox.showerror("Error", "Failed to delete macro!")
    
    def playback_callback(self, event_type, data):
        """Handle playback events"""
        if event_type == 'loop_completed':
            print(f"Loop {data} completed")
        elif event_type == 'playback_finished':
            print("Playback finished")
        elif event_type == 'error':
            print(f"Playback error: {data}")
    
    def update_status(self):
        """Update status display"""
        try:
            # Refresh window manager state
            self.window_manager.update_game_rect()
            
            if self.window_manager.is_game_running():
                if self.window_manager.is_game_active():
                    status = "🎮 Game: Active ✓"
                    color = "#27ae60"
                else:
                    status = "🎮 Game: Running (Inactive)"
                    color = "#f39c12"
            else:
                # Try to find the game window
                if self.window_manager.find_game_window():
                    status = "🎮 Game: Found ✓"
                    color = "#27ae60"
                else:
                    status = "❌ Game: Not Found"
                    color = "#e74c3c"
            
            self.status_label.config(text=status, fg=color)
        except Exception as e:
            self.status_label.config(text="❌ Status Error", fg="#e74c3c")
            print(f"Status update error: {e}")
        
        # Update again in 1 second
        self.root.after(1000, self.update_status)
    
    # Auto Hunt Methods
    def start_auto_hunt(self):
        """Start the auto hunt system"""
        if self.auto_hunt_engine.start_hunt():
            self.start_hunt_btn.configure(state=tk.DISABLED)
            self.pause_hunt_btn.configure(state=tk.NORMAL)
            self.stop_hunt_btn.configure(state=tk.NORMAL)
            self.hunt_status_label.configure(text="🎯 Hunting in progress...", fg='#27ae60')
        else:
            self.hunt_status_label.configure(text="❌ Failed to start hunt - check game status", fg='#e74c3c')
    
    def pause_auto_hunt(self):
        """Pause/Resume the auto hunt system"""
        if self.auto_hunt_engine.is_paused:
            self.auto_hunt_engine.resume_hunt()
            self.pause_hunt_btn.configure(text="⏸ Pause")
            self.hunt_status_label.configure(text="🎯 Hunting resumed...", fg='#27ae60')
        else:
            self.auto_hunt_engine.pause_hunt()
            self.pause_hunt_btn.configure(text="▶ Resume")
            self.hunt_status_label.configure(text="⏸ Hunt paused", fg='#f39c12')
    
    def stop_auto_hunt(self):
        """Stop the auto hunt system"""
        self.auto_hunt_engine.stop_hunt()
        self.start_hunt_btn.configure(state=tk.NORMAL)
        self.pause_hunt_btn.configure(state=tk.DISABLED, text="⏸ Pause")
        self.stop_hunt_btn.configure(state=tk.DISABLED)
        self.hunt_status_label.configure(text="⏹ Hunt stopped", fg='#95a5a6')
    

    
    def test_battle_menu(self):
        """Test battle menu detection on current screen"""
        print("⚔️ Testing battle menu detection...")
        
        # Capture full game screen for battle menu detection
        screenshot = self.auto_hunt_engine.capture_full_game_screen()
        if screenshot is None:
            print("❌ Could not capture game screen")
            from tkinter import messagebox
            messagebox.showerror("Error", "Could not capture game screen. Make sure PokeMMO is running.")
            return
        
        print(f"✓ Full game screenshot captured: {screenshot.shape[1]}x{screenshot.shape[0]} pixels")
        
        # Test battle menu detection
        battle_menu_detected = self.auto_hunt_engine.detect_battle_menu(screenshot)
        
        from tkinter import messagebox
        if battle_menu_detected:
            print("🎉 Battle menu detected!")
            messagebox.showinfo("Battle Menu Test", "✅ Battle menu detected on current screen!\n\nThe 4-button menu (FIGHT/BAG/Pokémon/RUN) was found.")
        else:
            print("❌ No battle menu detected")
            messagebox.showinfo("Battle Menu Test", "❌ No battle menu detected on current screen.\n\nMake sure you're in a battle with the menu visible.")
        
        print(f"Battle menu detection result: {battle_menu_detected}")
    
    def test_full_screen(self):
        """Test battle menu detection on full screen capture"""
        print("🖥️ Testing battle menu detection with full screen capture...")
        
        # Capture full screen (1920x1080)
        screenshot = self.auto_hunt_engine.capture_full_screen()
        if screenshot is None:
            print("❌ Could not capture full screen")
            from tkinter import messagebox
            messagebox.showerror("Error", "Could not capture full screen.")
            return
        
        print(f"✓ Full screen captured: {screenshot.shape[1]}x{screenshot.shape[0]} pixels")
        
        # Test battle menu detection on full screen
        battle_menu_detected = self.auto_hunt_engine.detect_battle_menu(screenshot)
        
        from tkinter import messagebox
        if battle_menu_detected:
            print("🎉 Battle menu detected on full screen!")
            messagebox.showinfo("Full Screen Test", "✅ Battle menu detected on full screen!\n\nThe 4-button menu (FIGHT/BAG/Pokémon/RUN) was found.")
        else:
            print("❌ No battle menu detected on full screen")
            messagebox.showinfo("Full Screen Test", "❌ No battle menu detected on full screen.\n\nMake sure you're in a battle with the menu visible.")
        
        print(f"Full screen battle menu detection result: {battle_menu_detected}")
    
    def test_templates(self):
        """Test template matching on current screen"""
        print("🖼️ Testing template matching...")
        
        # Load templates first
        self.auto_hunt_engine.load_templates()
        
        # Capture full screen for template testing
        screenshot = self.auto_hunt_engine.capture_full_screen()
        if screenshot is None:
            print("❌ Could not capture screen for template testing")
            from tkinter import messagebox
            messagebox.showerror("Error", "Could not capture screen for template testing.")
            return
        
        print(f"✓ Screen captured for template testing: {screenshot.shape[1]}x{screenshot.shape[0]} pixels")
        
        # Test all templates
        any_match = self.auto_hunt_engine.test_all_templates(screenshot)
        
        from tkinter import messagebox
        if any_match:
            print("🎉 At least one template matched!")
            messagebox.showinfo("Template Test", "✅ At least one template matched!\n\nCheck the console for details and debug_screenshots folder for saved images.")
        else:
            print("❌ No templates matched")
            messagebox.showinfo("Template Test", "❌ No templates matched.\n\nCheck the console for details and debug_screenshots folder for saved images.")
        
        print(f"Template testing completed. Check debug_screenshots folder for saved images.")
    
    def open_screenshots_folder(self):
        """Open the debug screenshots folder"""
        import os
        import subprocess
        
        screenshots_dir = "debug_screenshots"
        if os.path.exists(screenshots_dir):
            try:
                # Open folder in Windows Explorer
                subprocess.run(['explorer', os.path.abspath(screenshots_dir)], check=True)
                print(f"📁 Opened screenshots folder: {os.path.abspath(screenshots_dir)}")
            except Exception as e:
                print(f"❌ Error opening screenshots folder: {e}")
                from tkinter import messagebox
                messagebox.showerror("Error", f"Could not open screenshots folder:\n{e}")
        else:
            print("❌ Screenshots folder doesn't exist yet")
            from tkinter import messagebox
            messagebox.showwarning("Folder Not Found", "Screenshots folder doesn't exist yet.\n\nTake some test screenshots first!")
    
    def select_pokemmo_window(self):
        """Show manual window selection dialog with numbered list"""
        from tkinter import messagebox, simpledialog
        
        print("🎯 Listing all available windows for manual selection...")
        
        # Get all windows using the window manager's method
        window_candidates = self.window_manager.find_game_window()
        
        # Get all visible windows for manual selection
        import win32gui
        
        def enum_all_windows(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title.strip():  # Only show windows with titles
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        # Only show reasonably sized windows
                        if width > 200 and height > 150:
                            windows.append((hwnd, window_title, width, height))
                except:
                    pass
            return True
        
        all_windows = []
        win32gui.EnumWindows(enum_all_windows, all_windows)
        
        # Sort by window size (larger windows first) for better organization
        all_windows.sort(key=lambda x: x[2] * x[3], reverse=True)
        
        # Create selection dialog
        window_list = []
        for i, (hwnd, title, width, height) in enumerate(all_windows[:20]):  # Show top 20
            # Highlight PokeMMO candidates
            prefix = "🎮" if any(hwnd == candidate[0] for candidate in window_candidates) else "  "
            window_list.append(f"{prefix} {i+1:2d}. {title[:50]:<50} | {width:4d}x{height:4d}")
        
        if not window_list:
            messagebox.showerror("No Windows", "No suitable windows found!")
            return
        
        # Show selection dialog
        selection_text = ("Select the PokeMMO game window:\n"
                         "🎮 = Detected PokeMMO candidate\n\n" + 
                         "\n".join(window_list))
        
        try:
            choice = simpledialog.askinteger(
                "Select PokeMMO Window", 
                selection_text + f"\n\nEnter window number (1-{len(window_list)}):",
                minvalue=1, 
                maxvalue=len(window_list)
            )
            
            if choice:
                selected_hwnd, selected_title, width, height = all_windows[choice - 1]
                
                # Use the window manager's method to select the window
                if self.window_manager.select_window_by_handle(selected_hwnd):
                    messagebox.showinfo("Window Selected", 
                                      f"Successfully selected:\n{selected_title}\n\n"
                                      f"Size: {width}x{height}\n"
                                      f"Handle: {selected_hwnd}")
                else:
                    messagebox.showerror("Selection Failed", 
                                       f"Failed to select window:\n{selected_title}")
                
        except Exception as e:
            print(f"❌ Error in window selection: {e}")
            messagebox.showerror("Error", f"Error selecting window:\n{e}")
    
    def capture_template(self):
        """Capture a template for encounter detection"""
        from tkinter import simpledialog, messagebox
        
        template_name = simpledialog.askstring("Template Name", "Enter template name:")
        if not template_name:
            return
        
        messagebox.showinfo("Capture Template", 
                           f"Position your game window to show the encounter dialog,\nthen click OK to capture template '{template_name}'")
        
        # Capture current game screen
        if self.window_manager.is_game_running():
            game_rect = self.window_manager.game_rect
            if game_rect:
                # game_rect is a tuple: (left, top, right, bottom)
                success = self.template_manager.capture_template(
                    template_name, 
                    game_rect  # Already in the correct format
                )
                if success:
                    messagebox.showinfo("Success", f"Template '{template_name}' captured successfully!")
                else:
                    messagebox.showerror("Error", f"Failed to capture template '{template_name}'")
            else:
                messagebox.showerror("Error", "Could not get game window bounds")
        else:
            messagebox.showerror("Error", "Game not running!")
    
    def load_templates(self):
        """Load templates for encounter detection"""
        self.auto_hunt_engine.load_templates()
        templates = self.template_manager.list_templates()
        
        from tkinter import messagebox
        if templates:
            template_list = "\n".join(templates)
            messagebox.showinfo("Templates Loaded", f"Loaded templates:\n{template_list}")
        else:
            messagebox.showwarning("No Templates", "No templates found in templates directory")
    
    def on_hunt_status_update(self, status_type, data):
        """Handle hunt status updates"""
        if status_type == 'hunting':
            encounters = data.get('encounters', 0)
            hunt_time = data.get('time', 0)
            direction = data.get('direction', 'unknown')
            
            # Update UI
            self.encounters_label.configure(text=str(encounters))
            
            # Format time as MM:SS
            minutes = int(hunt_time // 60)
            seconds = int(hunt_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            self.hunt_time_label.configure(text=time_str)
            
            self.hunt_status_label.configure(text=f"🎯 Hunting... Moving {direction.upper()}", fg='#27ae60')
            
        elif status_type == 'error':
            self.hunt_status_label.configure(text=f"❌ Error: {data}", fg='#e74c3c')
            self.stop_auto_hunt()  # Auto-stop on error
            
        elif status_type == 'hunt_finished':
            encounters = data.get('encounters', 0)
            total_time = data.get('total_time', 0)
            
            minutes = int(total_time // 60)
            seconds = int(total_time % 60)
            
            self.hunt_status_label.configure(
                text=f"🏁 Hunt finished: {encounters} encounters in {minutes:02d}:{seconds:02d}", 
                fg='#95a5a6'
            )
    
    def on_encounter_detected(self, event_type, data):
        """Handle encounter detection events"""
        if event_type == 'encounter_detected':
            count = data.get('count', 0)
            hunt_time = data.get('time', 0)
            
            minutes = int(hunt_time // 60)
            seconds = int(hunt_time % 60)
            
            self.hunt_status_label.configure(
                text=f"🎉 Encounter #{count} detected at {minutes:02d}:{seconds:02d}!", 
                fg='#e74c3c'
            )
    
    # Sweet Scent event handlers
    def refresh_macro_list(self):
        """Refresh the list of available macros for Sweet Scent"""
        try:
            macros = self.sweet_scent_engine.get_available_macros()
            self.macro_combobox['values'] = macros if macros else ["No macros available"]
            if not macros:
                self.selected_macro_var.set("No macros available")
            elif self.selected_macro_var.get() not in macros:
                self.selected_macro_var.set("No macro selected")
        except Exception as e:
            print(f"Error refreshing macro list: {e}")
            self.macro_combobox['values'] = ["Error loading macros"]
            self.selected_macro_var.set("Error loading macros")
    
    def refresh_preset_list(self):
        """Refresh the list of available presets"""
        try:
            presets = self.sweet_scent_engine.get_preset_list()
            self.preset_combobox['values'] = presets if presets else ["No presets available"]
            if not presets:
                self.selected_preset_var.set("No presets available")
            elif self.selected_preset_var.get() not in presets:
                self.selected_preset_var.set("No preset selected")
        except Exception as e:
            print(f"Error refreshing preset list: {e}")
            self.preset_combobox['values'] = ["Error loading presets"]
            self.selected_preset_var.set("Error loading presets")
    
    def save_preset(self):
        """Save current configuration as a preset"""
        from tkinter import simpledialog, messagebox
        
        preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if not preset_name or not preset_name.strip():
            return
        
        preset_name = preset_name.strip()
        
        # Update configuration before saving
        self.update_sweet_scent_config()
        
        if self.sweet_scent_engine.save_preset(preset_name):
            messagebox.showinfo("Preset Saved", f"Preset '{preset_name}' saved successfully!")
            self.refresh_preset_list()
            self.selected_preset_var.set(preset_name)
        else:
            messagebox.showerror("Save Failed", f"Failed to save preset '{preset_name}'")
    
    def load_preset(self):
        """Load selected preset"""
        selected = self.selected_preset_var.get()
        if selected and selected not in ["No preset selected", "No presets available", "Error loading presets"]:
            if self.sweet_scent_engine.load_preset(selected):
                # Update UI to reflect loaded preset
                self.sweet_scent_uses_var.set(str(self.sweet_scent_engine.sweet_scent_uses))
                self.animation_delay_var.set(str(self.sweet_scent_engine.sweet_scent_animation_delay))
                self.initial_e_presses_var.set(str(self.sweet_scent_engine.initial_e_presses))
                self.initial_e_interval_var.set(str(self.sweet_scent_engine.initial_e_interval))
                self.loop_duration_var.set(str(self.sweet_scent_engine.encounter_loop_duration))
                self.loop_interval_var.set(str(self.sweet_scent_engine.encounter_loop_interval))
                self.heal_delay_var.set(str(self.sweet_scent_engine.heal_delay))
                self.cycle_pause_var.set(str(self.sweet_scent_engine.cycle_pause))
                self.initial_focus_delay_var.set(str(self.sweet_scent_engine.initial_focus_delay))
                self.post_e_delay_var.set(str(self.sweet_scent_engine.post_e_delay))
                self.use_e_plus_e_var.set(str(self.sweet_scent_engine.use_e_plus_e))
                self.debug_pokecenter_var.set(self.sweet_scent_engine.debug_pokecenter_enabled)
                
                # Update debug settings in Settings tab if they exist
                if hasattr(self, 'debug_s_duration_var'):
                    self.debug_s_duration_var.set(str(self.sweet_scent_engine.debug_s_key_duration))
                    self.debug_e_duration_var.set(str(self.sweet_scent_engine.debug_e_key_duration))
                    self.debug_e_interval_var.set(str(self.sweet_scent_engine.debug_e_key_interval))
                    self.debug_check_interval_var.set(str(self.sweet_scent_engine.debug_check_interval))
                
                # Update macro selection
                if self.sweet_scent_engine.selected_macro:
                    self.selected_macro_var.set(self.sweet_scent_engine.selected_macro)
                else:
                    self.selected_macro_var.set("No macro selected")
                
                from tkinter import messagebox
                messagebox.showinfo("Preset Loaded", f"Preset '{selected}' loaded successfully!")
            else:
                from tkinter import messagebox
                messagebox.showerror("Load Failed", f"Failed to load preset '{selected}'")
        else:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a preset to load!")
    
    def delete_preset(self):
        """Delete selected preset"""
        selected = self.selected_preset_var.get()
        if selected and selected not in ["No preset selected", "No presets available", "Error loading presets"]:
            from tkinter import messagebox
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{selected}'?"):
                if self.sweet_scent_engine.delete_preset(selected):
                    messagebox.showinfo("Preset Deleted", f"Preset '{selected}' deleted successfully!")
                    self.refresh_preset_list()
                else:
                    messagebox.showerror("Delete Failed", f"Failed to delete preset '{selected}'")
        else:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a preset to delete!")
    
    def on_macro_selected(self, event=None):
        """Handle macro selection for Sweet Scent"""
        selected = self.selected_macro_var.get()
        if selected and selected not in ["No macro selected", "No macros available", "Error loading macros"]:
            success = self.sweet_scent_engine.set_movement_macro(selected)
            if success:
                print(f"✓ Selected macro for Sweet Scent: {selected}")
            else:
                print(f"❌ Failed to select macro: {selected}")
                self.selected_macro_var.set("No macro selected")
    
    def update_sweet_scent_config(self):
        """Update Sweet Scent configuration from UI"""
        try:
            config = {
                'sweet_scent_uses': int(self.sweet_scent_uses_var.get()),
                'sweet_scent_animation_delay': float(self.animation_delay_var.get()),
                'initial_e_presses': int(self.initial_e_presses_var.get()),
                'initial_e_interval': float(self.initial_e_interval_var.get()),
                'encounter_loop_duration': float(self.loop_duration_var.get()),
                'encounter_loop_interval': float(self.loop_interval_var.get()),
                'heal_delay': float(self.heal_delay_var.get()),
                'cycle_pause': float(self.cycle_pause_var.get()),
                'initial_focus_delay': float(self.initial_focus_delay_var.get()),
                'post_e_delay': float(self.post_e_delay_var.get()),
                'use_e_plus_e': self.use_e_plus_e_var.get(),
                'debug_pokecenter_enabled': self.debug_pokecenter_var.get(),
            }
            self.sweet_scent_engine.update_configuration(config)
            
            # Update loop type labels
            self._update_loop_type_labels()
            
        except ValueError as e:
            print(f"Invalid configuration values: {e}")
    
    def _update_loop_type_labels(self):
        """Update the loop type labels based on current setting"""
        if hasattr(self, 'loop_duration_label') and hasattr(self, 'loop_interval_label'):
            loop_type = "E+E" if self.use_e_plus_e_var.get() else "X+E"
            self.loop_duration_label.config(text=f"{loop_type} Loop Duration (s):")
            self.loop_interval_label.config(text=f"{loop_type} Loop Interval (s):")
    
    def update_debug_config(self):
        """Update debug configuration from Settings tab"""
        try:
            debug_config = {
                'debug_s_key_duration': float(self.debug_s_duration_var.get()),
                'debug_e_key_duration': float(self.debug_e_duration_var.get()),
                'debug_e_key_interval': float(self.debug_e_interval_var.get()),
                'debug_check_interval': float(self.debug_check_interval_var.get()),
            }
            self.sweet_scent_engine.update_configuration(debug_config)
        except ValueError as e:
            print(f"Invalid debug configuration values: {e}")
    
    def start_sweet_scent(self):
        """Start Sweet Scent hunting with macro"""
        # Update configuration before starting
        self.update_sweet_scent_config()
        
        if self.sweet_scent_engine.start_hunt():
            self.start_scent_btn.config(state=tk.DISABLED)
            self.start_no_macro_btn.config(state=tk.DISABLED)
            self.pause_scent_btn.config(state=tk.NORMAL)
            self.stop_scent_btn.config(state=tk.NORMAL)
            self.sweet_scent_status_label.config(text="Sweet Scent hunting active", fg='#27ae60')
            print("✅ Sweet Scent hunt started")
        else:
            print("❌ Failed to start Sweet Scent hunt")
    
    def start_sweet_scent_no_macro(self):
        """Start Sweet Scent hunting without movement macro (start from current position)"""
        # Update configuration before starting
        self.update_sweet_scent_config()
        
        if self.sweet_scent_engine.start_hunt_no_macro():
            self.start_scent_btn.config(state=tk.DISABLED)
            self.start_no_macro_btn.config(state=tk.DISABLED)
            self.pause_scent_btn.config(state=tk.NORMAL)
            self.stop_scent_btn.config(state=tk.NORMAL)
            self.sweet_scent_status_label.config(text="Sweet Scent hunting active (no macro)", fg='#27ae60')
            print("✅ Sweet Scent hunt started from current position")
        else:
            print("❌ Failed to start Sweet Scent hunt")
    
    def pause_sweet_scent(self):
        """Pause Sweet Scent hunting"""
        if self.sweet_scent_engine.is_hunting and not self.sweet_scent_engine.is_paused:
            self.sweet_scent_engine.pause_hunt()
            self.pause_scent_btn.config(text="▶️ Resume")
            self.sweet_scent_status_label.config(text="Sweet Scent hunt paused", fg='#f39c12')
        else:
            self.sweet_scent_engine.resume_hunt()
            self.pause_scent_btn.config(text="⏸ Pause")
            self.sweet_scent_status_label.config(text="Sweet Scent hunting active", fg='#27ae60')
    
    def stop_sweet_scent(self):
        """Stop Sweet Scent hunting"""
        self.sweet_scent_engine.stop_hunt()
        self.reset_sweet_scent_ui()
        print("✅ Sweet Scent hunt stopped")
    
    def force_reset_sweet_scent(self):
        """Force reset Sweet Scent engine state"""
        self.sweet_scent_engine.force_reset_state()
        self.reset_sweet_scent_ui()
        print("✅ Sweet Scent engine force reset")
    
    def manual_pokecenter_escape(self):
        """Manually trigger pokecenter escape sequence"""
        try:
            print("🚪 Manual pokecenter escape triggered")
            success = self.sweet_scent_engine.perform_debug_sequence()
            if success:
                from tkinter import messagebox
                messagebox.showinfo("Escape Successful", "Successfully escaped from pokecenter!")
                print("✅ Manual pokecenter escape completed successfully")
            else:
                from tkinter import messagebox
                messagebox.showwarning("Escape Failed", "Failed to escape from pokecenter. Try again or check your position.")
                print("❌ Manual pokecenter escape failed")
        except Exception as e:
            print(f"❌ Error during manual pokecenter escape: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error during pokecenter escape: {e}")
    
    def reset_sweet_scent_ui(self):
        """Reset Sweet Scent UI to default state"""
        self.start_scent_btn.config(state=tk.NORMAL)
        self.start_no_macro_btn.config(state=tk.NORMAL)
        self.pause_scent_btn.config(state=tk.DISABLED, text="⏸ Pause")
        self.stop_scent_btn.config(state=tk.DISABLED)
        self.sweet_scent_status_label.config(text="Sweet Scent hunt stopped", fg='#95a5a6')
    
    def on_sweet_scent_status_update(self, status_type, data):
        """Handle Sweet Scent status updates"""
        try:
            if status_type == 'hunting':
                # Update statistics
                cycles = data.get('sweet_scent_cycles', 0)
                current_uses = data.get('current_uses', 0)
                max_uses = data.get('max_uses', 6)
                
                self.scent_cycles_label.config(text=str(cycles))
                self.pp_usage_label.config(text=f"{current_uses}/{max_uses}")
                
                # Update status text
                self.sweet_scent_status_label.config(text=f"Hunting... (Cycle {cycles}, PP: {current_uses}/{max_uses})")
                
            elif status_type == 'hunt_finished':
                cycles = data.get('sweet_scent_cycles', 0)
                heal_cycles = data.get('heal_cycles', 0)
                total_time = data.get('total_time', 0)
                
                self.sweet_scent_status_label.config(
                    text=f"Hunt completed - {cycles} cycles, {heal_cycles} heals, {total_time:.1f}s", 
                    fg='#95a5a6'
                )
                
                # Reset button states
                self.start_scent_btn.config(state=tk.NORMAL)
                self.start_no_macro_btn.config(state=tk.NORMAL)
                self.pause_scent_btn.config(state=tk.DISABLED, text="⏸ Pause")
                self.stop_scent_btn.config(state=tk.DISABLED)
                
            elif status_type == 'error':
                self.sweet_scent_status_label.config(text=f"Error: {data}", fg='#e74c3c')
                
                # Reset button states on error
                self.start_scent_btn.config(state=tk.NORMAL)
                self.start_no_macro_btn.config(state=tk.NORMAL)
                self.pause_scent_btn.config(state=tk.DISABLED, text="⏸ Pause")
                self.stop_scent_btn.config(state=tk.DISABLED)
                
        except Exception as e:
            print(f"Error updating Sweet Scent status: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        try:
            if hasattr(self, 'input_manager'):
                # Stop any ongoing recording
                if self.is_recording:
                    self.input_manager.stop_recording()
            
            print("Cleaning up...")
            self.root.destroy()
            print("Cleanup complete.")
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.root.destroy()
    
    def run(self):
        """Run the overlay application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("Starting overlay window...")
        self.root.mainloop()
    
    # PP Auto Hunt Methods
    def refresh_pp_macro_list(self):
        """Refresh the PP Auto Hunt macro dropdown"""
        try:
            macros = self.pp_auto_hunt_engine.get_available_macros()
            
            if macros:
                macro_names = [macro['name'] for macro in macros]
                self.pp_macro_dropdown['values'] = macro_names
                
                # If current selection is not valid, reset
                current = self.pp_macro_var.get()
                if current not in macro_names and current not in ["No macro selected", "No macros available"]:
                    self.pp_macro_var.set("No macro selected")
            else:
                self.pp_macro_dropdown['values'] = ["No macros available"]
                self.pp_macro_var.set("No macros available")
                
        except Exception as e:
            print(f"Error refreshing PP macro list: {e}")
            self.pp_macro_dropdown['values'] = ["Error loading macros"]
            self.pp_macro_var.set("Error loading macros")
    
    def on_pp_macro_selected(self, event=None):
        """Handle PP Auto Hunt macro selection"""
        selected = self.pp_macro_var.get()
        if selected and selected not in ["No macro selected", "No macros available", "Error loading macros"]:
            success = self.pp_auto_hunt_engine.set_movement_macro(selected)
            if success:
                print(f"✓ Selected macro for PP Auto Hunt: {selected}")
            else:
                print(f"❌ Failed to select macro: {selected}")
                self.pp_macro_var.set("No macro selected")
    
    def update_pp_hunt_config(self):
        """Update PP Auto Hunt configuration from UI"""
        try:
            config = {
                'max_encounters': int(self.pp_max_encounters_var.get()),
                'movement_interval': float(self.pp_movement_interval_var.get()),
                'key_hold_duration': float(self.pp_key_hold_var.get()),
                'initial_e_presses': int(self.pp_initial_e_var.get()),
                'battle_key_interval': float(self.pp_battle_interval_var.get()),
                'post_e_delay': float(self.pp_post_e_delay_var.get()),
                'encounter_loop_duration': float(self.pp_loop_duration_var.get()),
                'encounter_loop_type': self.pp_loop_type_var.get(),
                'encounter_loop_interval': float(self.pp_loop_interval_var.get()),
                'heal_delay': float(self.pp_heal_delay_var.get()),
            }
            self.pp_auto_hunt_engine.update_configuration(config)
            print("✅ PP Auto Hunt configuration updated")
            
        except ValueError as e:
            print(f"Invalid PP Auto Hunt configuration values: {e}")
    
    def start_pp_hunt(self):
        """Start PP Auto Hunt with macro"""
        # Update configuration before starting
        self.update_pp_hunt_config()
        
        if self.pp_auto_hunt_engine.start_hunt():
            self.start_pp_hunt_btn.config(state=tk.DISABLED)
            self.start_pp_no_macro_btn.config(state=tk.DISABLED)
            self.pause_pp_hunt_btn.config(state=tk.NORMAL)
            self.stop_pp_hunt_btn.config(state=tk.NORMAL)
            self.pp_hunt_status_label.config(text="PP Auto Hunt active", fg='#27ae60')
            print("✅ PP Auto Hunt started")
        else:
            print("❌ Failed to start PP Auto Hunt")
    
    def start_pp_hunt_no_macro(self):
        """Start PP Auto Hunt without movement macro (start from current position)"""
        # Update configuration before starting
        self.update_pp_hunt_config()
        
        if self.pp_auto_hunt_engine.start_hunt_no_macro():
            self.start_pp_hunt_btn.config(state=tk.DISABLED)
            self.start_pp_no_macro_btn.config(state=tk.DISABLED)
            self.pause_pp_hunt_btn.config(state=tk.NORMAL)
            self.stop_pp_hunt_btn.config(state=tk.NORMAL)
            self.pp_hunt_status_label.config(text="PP Auto Hunt active (no macro)", fg='#27ae60')
            print("✅ PP Auto Hunt started from current position")
        else:
            print("❌ Failed to start PP Auto Hunt")
    
    def pause_pp_hunt(self):
        """Pause PP Auto Hunt"""
        if self.pp_auto_hunt_engine.is_hunting and not self.pp_auto_hunt_engine.is_paused:
            self.pp_auto_hunt_engine.pause_hunt()
            self.pause_pp_hunt_btn.config(text="▶️ Resume")
            self.pp_hunt_status_label.config(text="PP Auto Hunt paused", fg='#f39c12')
        else:
            self.pp_auto_hunt_engine.resume_hunt()
            self.pause_pp_hunt_btn.config(text="⏸ Pause")
            self.pp_hunt_status_label.config(text="PP Auto Hunt active", fg='#27ae60')
    
    def stop_pp_hunt(self):
        """Stop PP Auto Hunt"""
        self.pp_auto_hunt_engine.stop_hunt()
        self.reset_pp_hunt_ui()
        print("✅ PP Auto Hunt stopped")
    
    def force_reset_pp_hunt(self):
        """Force reset PP Auto Hunt engine state"""
        self.pp_auto_hunt_engine.force_reset_state()
        self.reset_pp_hunt_ui()
        print("✅ PP Auto Hunt engine force reset")
    
    def reset_pp_hunt_ui(self):
        """Reset PP Auto Hunt UI to default state"""
        self.start_pp_hunt_btn.config(state=tk.NORMAL)
        self.start_pp_no_macro_btn.config(state=tk.NORMAL)
        self.pause_pp_hunt_btn.config(state=tk.DISABLED, text="⏸ Pause")
        self.stop_pp_hunt_btn.config(state=tk.DISABLED)
        self.pp_hunt_status_label.config(text="PP Auto Hunt stopped", fg='#95a5a6')
    
    def refresh_pp_preset_list(self):
        """Refresh the PP Auto Hunt preset dropdown"""
        try:
            presets = self.pp_auto_hunt_engine.get_preset_list()
            
            if presets:
                self.pp_preset_dropdown['values'] = presets
                
                # If current selection is not valid, reset
                current = self.pp_preset_var.get()
                if current not in presets and current not in ["No preset selected", "No presets available"]:
                    self.pp_preset_var.set("No preset selected")
            else:
                self.pp_preset_dropdown['values'] = ["No presets available"]
                self.pp_preset_var.set("No presets available")
                
        except Exception as e:
            print(f"Error refreshing PP preset list: {e}")
            self.pp_preset_dropdown['values'] = ["Error loading presets"]
            self.pp_preset_var.set("Error loading presets")
    
    def save_pp_preset(self):
        """Save current PP Auto Hunt configuration as preset"""
        preset_name = self.pp_save_preset_var.get().strip()
        if not preset_name:
            from tkinter import messagebox
            messagebox.showwarning("Invalid Name", "Please enter a preset name!")
            return
        
        # Update configuration before saving
        self.update_pp_hunt_config()
        
        if self.pp_auto_hunt_engine.save_preset(preset_name):
            from tkinter import messagebox
            messagebox.showinfo("Preset Saved", f"Preset '{preset_name}' saved successfully!")
            self.pp_save_preset_var.set("")  # Clear the entry
            self.refresh_pp_preset_list()
        else:
            from tkinter import messagebox
            messagebox.showerror("Save Failed", f"Failed to save preset '{preset_name}'")
    
    def load_pp_preset(self):
        """Load selected PP Auto Hunt preset"""
        selected = self.pp_preset_var.get()
        if selected and selected not in ["No preset selected", "No presets available", "Error loading presets"]:
            if self.pp_auto_hunt_engine.load_preset(selected):
                # Update UI with loaded configuration
                config = self.pp_auto_hunt_engine
                self.pp_max_encounters_var.set(str(config.max_encounters))
                self.pp_movement_interval_var.set(str(config.movement_interval))
                self.pp_key_hold_var.set(str(config.key_hold_duration))
                self.pp_initial_e_var.set(str(config.initial_e_presses))
                self.pp_battle_interval_var.set(str(config.battle_key_interval))
                self.pp_post_e_delay_var.set(str(config.post_e_delay))
                self.pp_loop_duration_var.set(str(config.encounter_loop_duration))
                self.pp_loop_type_var.set(str(config.encounter_loop_type))
                self.pp_loop_interval_var.set(str(config.encounter_loop_interval))
                self.pp_heal_delay_var.set(str(config.heal_delay))
                
                # Update macro selection
                if config.selected_macro:
                    self.pp_macro_var.set(config.selected_macro)
                
                from tkinter import messagebox
                messagebox.showinfo("Preset Loaded", f"Preset '{selected}' loaded successfully!")
            else:
                from tkinter import messagebox
                messagebox.showerror("Load Failed", f"Failed to load preset '{selected}'")
        else:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a preset to load!")
    
    def delete_pp_preset(self):
        """Delete selected PP Auto Hunt preset"""
        selected = self.pp_preset_var.get()
        if selected and selected not in ["No preset selected", "No presets available", "Error loading presets"]:
            from tkinter import messagebox
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{selected}'?"):
                if self.pp_auto_hunt_engine.delete_preset(selected):
                    messagebox.showinfo("Preset Deleted", f"Preset '{selected}' deleted successfully!")
                    self.refresh_pp_preset_list()
                else:
                    messagebox.showerror("Delete Failed", f"Failed to delete preset '{selected}'")
        else:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a preset to delete!")
    
    def on_pp_hunt_status_update(self, status_type, data):
        """Handle PP Auto Hunt status updates"""
        try:
            if status_type == 'hunting':
                # Update statistics
                encounters = data.get('encounters_found', 0)
                current_encounters = data.get('current_encounters', 0)
                max_encounters = data.get('max_encounters', 20)
                hunt_time = data.get('hunt_time', 0)
                
                self.pp_encounters_label.config(text=str(encounters))
                self.pp_counter_label.config(text=f"{current_encounters}/{max_encounters}")
                
                # Format time as MM:SS
                minutes = int(hunt_time // 60)
                seconds = int(hunt_time % 60)
                self.pp_hunt_time_label.config(text=f"{minutes:02d}:{seconds:02d}")
                
                # Update status text
                self.pp_hunt_status_label.config(text=f"Hunting... (PP: {current_encounters}/{max_encounters}, Encounters: {encounters})")
                
            elif status_type == 'hunt_finished':
                encounters = data.get('encounters_found', 0)
                heal_cycles = data.get('heal_cycles', 0)
                hunt_cycles = data.get('hunt_cycles', 0)
                total_time = data.get('total_time', 0)
                
                self.pp_hunt_status_label.config(
                    text=f"Hunt completed - {encounters} encounters, {heal_cycles} heals, {hunt_cycles} cycles, {total_time:.1f}s", 
                    fg='#95a5a6'
                )
                
                # Reset button states
                self.start_pp_hunt_btn.config(state=tk.NORMAL)
                self.start_pp_no_macro_btn.config(state=tk.NORMAL)
                self.pause_pp_hunt_btn.config(state=tk.DISABLED, text="⏸ Pause")
                self.stop_pp_hunt_btn.config(state=tk.DISABLED)
                
            elif status_type == 'error':
                self.pp_hunt_status_label.config(text=f"Error: {data}", fg='#e74c3c')
                
                # Reset button states on error
                self.start_pp_hunt_btn.config(state=tk.NORMAL)
                self.start_pp_no_macro_btn.config(state=tk.NORMAL)
                self.pause_pp_hunt_btn.config(state=tk.DISABLED, text="⏸ Pause")
                self.stop_pp_hunt_btn.config(state=tk.DISABLED)
                
        except Exception as e:
            print(f"Error updating PP Auto Hunt status: {e}")
    
    def on_pp_encounter_detected(self, event_type, data):
        """Handle PP Auto Hunt encounter events"""
        if event_type == 'encounter_start':
            print(f"🎯 Encounter detected at {data}")
        elif event_type == 'encounter_end':
            print(f"✅ Encounter completed")

def print_header():
    """Print application header and instructions"""
    print("=" * 60)
    print("    PokeMMO Overlay - Macro System v2.0")
    print("=" * 60)
    print("🎯 Features:")
    print("  • Record keyboard and mouse actions")
    print("  • Play back saved macros with loop functionality")
    print("  • Organize macros by category")
    print("  • Modern dark theme UI")
    print("  • Automatic PokeMMO detection")
    print("  • Python 3.13 compatible (no pynput)")
    print("")
    print("📋 Instructions:")
    print("  1. Start PokeMMO")
    print(f"  2. Press {TOGGLE_RECORDING_KEY} key or click 'Start Recording'")
    print("  3. Perform actions in PokeMMO")
    print(f"  4. Press {TOGGLE_RECORDING_KEY} key again or click 'Stop Recording'")
    print("  5. Save your macro with a name")
    print("  6. Use 'Play' or 'Loop' to replay macros")
    print("")
    print("⌨️  Hotkeys:")
    print(f"  • {TOGGLE_RECORDING_KEY} (Backtick) - Toggle recording")
    print("  • ESC - Emergency stop any macro")
    print("")
    print("📑 Tabs:")
    print("  • Macros - Record and manage macros")
    print("  • Fishing - Automated fishing (coming soon)")
    print("  • Settings - Configuration and hotkeys")
    print("")
    print("⚠️  Safety:")
    print("  • Only works when PokeMMO is running")
    print("  • Coordinates are game-window relative")
    print("  • Use responsibly and check PokeMMO ToS!")
    print("=" * 60)

def main():
    """Main application entry point"""
    print_header()
    
    print("Initializing PokeMMO Overlay...")
    
    try:
        overlay = PokeMMOOverlay()
        overlay.run()
    except KeyboardInterrupt:
        print("\nShutdown requested by user...")
    except Exception as e:
        print(f"Fatal error: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main() 