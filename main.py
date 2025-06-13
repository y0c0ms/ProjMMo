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
            
            # Check if mouse moved significantly
            if abs(x - self.last_mouse_pos[0]) >= MOUSE_MOVE_THRESHOLD or \
               abs(y - self.last_mouse_pos[1]) >= MOUSE_MOVE_THRESHOLD:
                
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
            
            # Check mouse buttons
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
    
    def play_macro(self, events, speed=1.0, loop_count=1, callback=None):
        """Play back recorded events"""
        playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(events, speed, loop_count, callback),
            daemon=True
        )
        playback_thread.start()
        return True
    
    def _playback_loop(self, events, speed, loop_count, callback):
        """Playback loop"""
        try:
            self.stop_playback = False
            loop = 0
            while True:
                if self.stop_playback or (loop_count != -1 and loop >= loop_count):
                    break
                
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
                callback('playback_finished', None)
    
    def _execute_event(self, event):
        """Execute a single event"""
        try:
            if event['type'] == 'mouse_move':
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                win32api.SetCursorPos((int(screen_x), int(screen_y)))
            
            elif event['type'] == 'mouse_click':
                screen_x, screen_y = self.window_manager.game_to_screen_coords(
                    event['x'], event['y']
                )
                win32api.SetCursorPos((int(screen_x), int(screen_y)))
                
                if event['button'] == 'left':
                    flag = win32con.MOUSEEVENTF_LEFTDOWN if event['pressed'] else win32con.MOUSEEVENTF_LEFTUP
                elif event['button'] == 'right':
                    flag = win32con.MOUSEEVENTF_RIGHTDOWN if event['pressed'] else win32con.MOUSEEVENTF_RIGHTUP
                elif event['button'] == 'middle':
                    flag = win32con.MOUSEEVENTF_MIDDLEDOWN if event['pressed'] else win32con.MOUSEEVENTF_MIDDLEUP
                else:
                    return
                
                win32api.mouse_event(flag, 0, 0, 0, 0)
            
            elif event['type'] in ['key_press', 'key_release']:
                vk_code = self._get_virtual_key_code(event['key'])
                if vk_code:
                    flags = 0 if event['pressed'] else win32con.KEYEVENTF_KEYUP
                    win32api.keybd_event(vk_code, 0, flags, 0)
        
        except Exception as e:
            print(f"Error executing event: {e}")
    
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
        }
        
        if len(key_name) == 1:
            return ord(key_name.upper())
        
        return key_map.get(key_name.lower())

class PokeMMOOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        
        # Initialize components
        self.window_manager = WindowManager()
        
        # Try to find game window initially
        if self.window_manager.find_game_window():
            print("PokeMMO window found!")
        else:
            print("PokeMMO window not found - will keep searching...")
        
        self.input_manager = InputCapturePolling(self.window_manager)
        self.macro_manager = MacroManager()
        
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
        
        # Settings tab (placeholder)
        self.settings_frame = tk.Frame(self.notebook, bg='#1e1e1e')
        self.notebook.add(self.settings_frame, text='⚙️ Settings')
        
        # Create content for each tab
        self.create_macros_tab()
        self.create_fishing_tab()
        self.create_settings_tab()
    
    def create_macros_tab(self):
        """Create the macros tab content"""
        # Recording section
        self.create_recording_section(self.macros_frame)
        
        # Save section
        self.create_save_section(self.macros_frame)
        
        # Macro management section
        self.create_macro_section(self.macros_frame)
    
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
    
    def create_settings_tab(self):
        """Create the settings tab content (placeholder)"""
        settings_container = tk.Frame(self.settings_frame, bg='#1e1e1e')
        settings_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Hotkeys section
        hotkeys_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        hotkeys_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(hotkeys_frame, text="⌨️ Hotkeys", 
                font=('Segoe UI', 11, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(8, 8))
        
        tk.Label(hotkeys_frame, text="« (Left Guillemet) - Toggle Recording", 
                font=('Segoe UI', 9), 
                fg='#cccccc', bg='#2a2a2a').pack(pady=(0, 4))
        
        tk.Label(hotkeys_frame, text="ESC - Emergency Stop", 
                font=('Segoe UI', 9), 
                fg='#cccccc', bg='#2a2a2a').pack(pady=(0, 8))
        
        # General settings section
        general_frame = tk.Frame(settings_container, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        general_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(general_frame, text="⚙️ General Settings", 
                font=('Segoe UI', 11, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(8, 8))
        
        tk.Label(general_frame, text="More settings will be\nadded in future updates.", 
                font=('Segoe UI', 10), 
                fg='#cccccc', bg='#2a2a2a',
                justify=tk.CENTER).pack(pady=(0, 8))
    
    def create_recording_section(self, parent):
        """Create recording controls section"""
        record_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        record_frame.pack(fill=tk.X, pady=(10, 8))
        
        tk.Label(record_frame, text="🎮 Recording Controls", 
                font=('Segoe UI', 11, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(8, 4))
        
        # Hotkey info
        tk.Label(record_frame, text="Press « key to start/stop recording", 
                font=('Segoe UI', 8), 
                fg='#95a5a6', bg='#2a2a2a').pack(pady=(0, 8))
        
        self.record_button = tk.Button(record_frame, text="🔴 Start Recording", 
                                     command=self.toggle_recording,
                                     font=('Segoe UI', 10, 'bold'),
                                     fg='#ffffff', bg='#dc3545',
                                     activeforeground='#ffffff', activebackground='#c82333',
                                     relief=tk.RAISED, bd=2, pady=10)
        self.record_button.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        self.record_status = tk.Label(record_frame, text="Ready to record",
                                    font=('Segoe UI', 9), 
                                    fg='#95a5a6', bg='#2a2a2a')
        self.record_status.pack(pady=(0, 8))
    
    def create_save_section(self, parent):
        """Create macro save section"""
        save_frame = tk.Frame(parent, bg='#2a2a2a', relief=tk.RAISED, bd=1)
        save_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(save_frame, text="💾 Save Macro", 
                font=('Segoe UI', 10, 'bold'), 
                fg='#ffffff', bg='#2a2a2a').pack(pady=(6, 6))
        
        # Name and Category in one row
        inputs_frame = tk.Frame(save_frame, bg='#2a2a2a')
        inputs_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        
        # Name entry
        name_frame = tk.Frame(inputs_frame, bg='#2a2a2a')
        name_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Label(name_frame, text="Name:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        self.macro_name_entry = tk.Entry(name_frame, font=('Segoe UI', 9),
                                       bg='#ffffff', fg='#000000', 
                                       insertbackground='#000000',
                                       relief=tk.RAISED, bd=2)
        self.macro_name_entry.pack(fill=tk.X, pady=(2, 0))
        
        # Category selection
        cat_frame = tk.Frame(inputs_frame, bg='#2a2a2a')
        cat_frame.pack(side=tk.RIGHT, padx=(5, 0))
        
        tk.Label(cat_frame, text="Category:", font=('Segoe UI', 8), 
                fg='#bdc3c7', bg='#2a2a2a').pack(anchor=tk.W)
        
        # Configure ttk combobox style
        style = ttk.Style()
        style.configure('Dark.TCombobox', 
                       fieldbackground='#ffffff',
                       background='#ffffff',
                       foreground='#000000',
                       arrowcolor='#000000')
        
        self.category_combo = ttk.Combobox(cat_frame, values=list(MACRO_CATEGORIES.keys()),
                                         font=('Segoe UI', 8),
                                         style='Dark.TCombobox',
                                         state='readonly', width=12)
        self.category_combo.pack(pady=(2, 0))
        self.category_combo.set("General")
        
        self.save_button = tk.Button(save_frame, text="💾 Save Macro", 
                                   command=self.save_macro, state='disabled',
                                   font=('Segoe UI', 9, 'bold'),
                                   fg='#ffffff', bg='#007bff',
                                   activeforeground='#ffffff', activebackground='#0056b3',
                                   disabledforeground='#6c757d',
                                   relief=tk.RAISED, bd=2, pady=8)
        self.save_button.pack(fill=tk.X, padx=10, pady=(0, 8))
    
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
        category = self.category_combo.get()
        
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
    print("  2. Press « key or click 'Start Recording'")
    print("  3. Perform actions in PokeMMO")
    print("  4. Press « key again or click 'Stop Recording'")
    print("  5. Save your macro with a name")
    print("  6. Use 'Play' or 'Loop' to replay macros")
    print("")
    print("⌨️  Hotkeys:")
    print("  • « (Left Guillemet) - Toggle recording")
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