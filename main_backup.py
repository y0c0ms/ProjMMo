"""
PokeMMO Overlay - Main application with polling-based input capture (Python 3.13 compatible)
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
            loop = 0
            while True:
                if loop_count != -1 and loop >= loop_count:
                    break
                
                last_timestamp = 0
                
                for event in events:
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
        self.root.geometry("320x500")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.95)
        self.root.configure(bg='#2b2b2b')
        
        # Position in top-right corner
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry("+{}+{}".format(screen_width - 340, 20))
        
        # Set window icon and styling
        try:
            self.root.iconname("PokeMMO Overlay")
        except:
            pass
    
    def create_ui(self):
        """Create the user interface"""
        # Configure ttk styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'), foreground='#4a9eff')
        style.configure('Status.TLabel', font=('Arial', 10), foreground='#ffffff')
        style.configure('Accent.TButton', font=('Arial', 9, 'bold'))
        style.configure('Record.TButton', font=('Arial', 10, 'bold'))
        
        main_frame = tk.Frame(self.root, bg='#2b2b2b', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="PokeMMO Overlay", 
                              font=('Arial', 14, 'bold'), 
                              fg='#4a9eff', bg='#2b2b2b')
        title_label.pack(pady=(0, 15))
        
        # Status section
        status_frame = tk.LabelFrame(main_frame, text="Status", 
                                   font=('Arial', 10, 'bold'),
                                   fg='#ffffff', bg='#3c3c3c', 
                                   relief=tk.RAISED, bd=2)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(status_frame, text="Initializing...", 
                                   font=('Arial', 10), 
                                   fg='#ffffff', bg='#3c3c3c')
        self.status_label.pack(pady=8)
        
        # Recording section
        record_frame = tk.LabelFrame(main_frame, text="Recording", 
                                   font=('Arial', 10, 'bold'),
                                   fg='#ffffff', bg='#3c3c3c', 
                                   relief=tk.RAISED, bd=2)
        record_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.record_button = tk.Button(record_frame, text="🔴 Record", 
                                     command=self.toggle_recording,
                                     font=('Arial', 11, 'bold'),
                                     fg='#ffffff', bg='#ff4444',
                                     activeforeground='#ffffff', activebackground='#ff6666',
                                     relief=tk.RAISED, bd=2, pady=8)
        self.record_button.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.record_status = tk.Label(record_frame, text="Ready to record",
                                    font=('Arial', 9), 
                                    fg='#cccccc', bg='#3c3c3c')
        self.record_status.pack(pady=(0, 10))
        
        # Macro save section
        save_frame = tk.LabelFrame(main_frame, text="Save Macro", 
                                 font=('Arial', 10, 'bold'),
                                 fg='#ffffff', bg='#3c3c3c', 
                                 relief=tk.RAISED, bd=2)
        save_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Name entry
        name_frame = tk.Frame(save_frame, bg='#3c3c3c')
        name_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        tk.Label(name_frame, text="Name:", font=('Arial', 9), 
                fg='#ffffff', bg='#3c3c3c').pack(side=tk.LEFT)
        self.macro_name_entry = tk.Entry(name_frame, font=('Arial', 9),
                                       bg='#4a4a4a', fg='#ffffff', 
                                       insertbackground='#ffffff')
        self.macro_name_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Category selection
        cat_frame = tk.Frame(save_frame, bg='#3c3c3c')
        cat_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(cat_frame, text="Category:", font=('Arial', 9), 
                fg='#ffffff', bg='#3c3c3c').pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(cat_frame, values=list(MACRO_CATEGORIES.keys()),
                                         font=('Arial', 9))
        self.category_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        self.category_combo.set("General")
        
        self.save_button = tk.Button(save_frame, text="💾 Save Macro", 
                                   command=self.save_macro, state='disabled',
                                   font=('Arial', 10, 'bold'),
                                   fg='#ffffff', bg='#4a9eff',
                                   activeforeground='#ffffff', activebackground='#6bb6ff',
                                   disabledforeground='#888888', 
                                   relief=tk.RAISED, bd=2, pady=6)
        self.save_button.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        # Macro management section
        macro_frame = ttk.LabelFrame(main_frame, text="Saved Macros", padding="5")
        macro_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Category filter
        ttk.Label(macro_frame, text="Filter:").grid(row=0, column=0, sticky=tk.W)
        self.filter_combo = ttk.Combobox(macro_frame, values=["All"] + list(MACRO_CATEGORIES.keys()), width=18)
        self.filter_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.filter_combo.set("All")
        self.filter_combo.bind('<<ComboboxSelected>>', self.update_macro_list)
        
        # Macro list
        self.macro_listbox = tk.Listbox(macro_frame, height=8)
        self.macro_listbox.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        
        # Playback controls
        playback_frame = ttk.Frame(macro_frame)
        playback_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Loop controls
        loop_frame = ttk.Frame(playback_frame)
        loop_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(loop_frame, text="Loops:").grid(row=0, column=0, sticky=tk.W)
        self.loop_entry = ttk.Entry(loop_frame, width=5)
        self.loop_entry.grid(row=0, column=1, padx=(5, 5))
        self.loop_entry.insert(0, "1")
        
        self.infinite_loop_var = tk.BooleanVar()
        self.infinite_loop_cb = ttk.Checkbutton(loop_frame, text="Infinite", variable=self.infinite_loop_var)
        self.infinite_loop_cb.grid(row=0, column=2, padx=(5, 0))
        
        # Playback buttons
        self.play_button = ttk.Button(playback_frame, text="▶️ Play", command=self.play_macro)
        self.play_button.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(0, 2))
        
        self.loop_button = ttk.Button(playback_frame, text="🔄 Loop", command=self.loop_macro)
        self.loop_button.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(2, 2))
        
        self.delete_button = ttk.Button(playback_frame, text="🗑️ Delete", command=self.delete_macro)
        self.delete_button.grid(row=1, column=2, sticky=(tk.W, tk.E), padx=(2, 0))
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        macro_frame.columnconfigure(1, weight=1)
        macro_frame.rowconfigure(1, weight=1)
        
        # Initialize macro list
        self.update_macro_list()
    
    def toggle_recording(self):
        """Toggle macro recording"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """Start recording macro"""
        if not self.window_manager.is_game_running():
            messagebox.showwarning("Game Not Found", "Please start PokeMMO first!")
            return
        
        if self.input_manager.start_recording():
            self.is_recording = True
            self.record_button.config(text="⏹️ Stop")
            self.record_status.config(text="Recording... (Click to stop)")
    
    def stop_recording(self):
        """Stop recording macro"""
        if self.is_recording:
            self.current_events = self.input_manager.stop_recording()
            self.is_recording = False
            self.record_button.config(text="🔴 Record")
            
            if self.current_events:
                self.record_status.config(text=f"Recorded {len(self.current_events)} events")
                self.save_button.config(state='normal')
            else:
                self.record_status.config(text="No events recorded")
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
        
        if self.macro_manager.save_macro(name, self.current_events, category):
            messagebox.showinfo("Success", f"Macro '{name}' saved successfully!")
            self.macro_name_entry.delete(0, tk.END)
            self.current_events = []
            self.save_button.config(state='disabled')
            self.record_status.config(text="Ready to record")
            self.update_macro_list()
        else:
            messagebox.showerror("Error", "Failed to save macro!")
    
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
        if self.window_manager.is_game_running():
            if self.window_manager.is_game_active():
                status = "Game: Active ✓"
            else:
                status = "Game: Running (Inactive)"
        else:
            status = "Game: Not Found ❌"
        
        self.status_label.config(text=status)
        
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
    print("=" * 50)
    print("    PokeMMO Overlay - Macro System")
    print("=" * 50)
    print("Features:")
    print("  • Record keyboard and mouse actions")
    print("  • Play back saved macros")
    print("  • Organize macros by category")
    print("  • Always-on-top overlay window")
    print("  • Automatic PokeMMO detection")
    print("")
    print("Instructions:")
    print("  1. Start PokeMMO")
    print("  2. Click 'Record' to start recording")
    print("  3. Perform actions in PokeMMO")
    print("  4. Click 'Record' again to stop")
    print("  5. Save your macro with a name")
    print("  6. Use 'Play' to replay macros")
    print("")
    print("Safety:")
    print("  • Press ESC to emergency stop any macro")
    print("  • Only works when PokeMMO is active")
    print("  • Coordinates are game-window relative")
    print("")
    print("WARNING: Use responsibly and check PokeMMO ToS!")
    print("=" * 50)

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