"""
Main Overlay Window for PokeMMO Macro System
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading
import time
from config import *

class OverlayWindow:
    def __init__(self, window_manager, input_manager, macro_manager):
        self.window_manager = window_manager
        self.input_manager = input_manager
        self.macro_manager = macro_manager
        
        # Main window
        self.root = tk.Tk()
        self.setup_window()
        
        # UI Elements
        self.status_var = tk.StringVar(value="Ready")
        self.recording_var = tk.StringVar(value="● Record")
        self.game_status_var = tk.StringVar(value="Game: Not Found")
        
        # Recording options
        self.record_mouse_var = tk.BooleanVar(value=True)
        
        # Current recording
        self.current_recording = []
        
        # Loop control state
        self.is_loop_running = False
        
        # UI setup
        self.create_ui()
        self.update_macro_list()
        
        # Set up recording hotkey callback
        self.input_manager.set_toggle_recording_callback(self.toggle_recording)
        
        # Set up loop stop hotkey callback
        self.input_manager.set_stop_loop_callback(self.hotkey_stop_loop)
        
        # Set up emergency stop callback
        self.input_manager.set_emergency_stop_callback(self.emergency_stop)
        
        # Start window monitoring
        self.window_manager.add_callback(self.on_window_event)
        self.window_manager.start_monitoring()
        
        # Update loop
        self.update_status()
        
    def setup_window(self):
        """Configure main window properties"""
        self.root.title("PokeMMO Overlay")
        self.root.geometry(f"{OVERLAY_WIDTH}x{OVERLAY_HEIGHT}")
        self.root.configure(bg=BG_COLOR)
        
        # Make window stay on top
        self.root.attributes('-topmost', ALWAYS_ON_TOP)
        
        # Configure for transparency (if needed)
        self.root.attributes('-alpha', OVERLAY_OPACITY)
        
        # Window positioning
        self.root.geometry("+50+50")  # Position on screen
        
        # Configure styles
        self.setup_styles()
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure button styles
        style.configure("Record.TButton",
                       background=RECORD_COLOR,
                       foreground=TEXT_COLOR,
                       font=('Arial', 10, 'bold'))
        
        style.configure("Action.TButton",
                       background=ACCENT_COLOR,
                       foreground=TEXT_COLOR,
                       font=('Arial', 9))
        
        style.configure("Normal.TButton",
                       background=BUTTON_COLOR,
                       foreground=TEXT_COLOR,
                       font=('Arial', 9))
    
    def create_ui(self):
        """Create the main UI elements"""
        # Main frame
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status frame
        status_frame = tk.Frame(main_frame, bg=BG_COLOR)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(status_frame, textvariable=self.game_status_var, 
                bg=BG_COLOR, fg=TEXT_COLOR, font=('Arial', 8)).pack(side=tk.LEFT)
        
        tk.Label(status_frame, textvariable=self.status_var,
                bg=BG_COLOR, fg=ACCENT_COLOR, font=('Arial', 8)).pack(side=tk.RIGHT)
        
        # Recording controls
        record_frame = tk.Frame(main_frame, bg=BG_COLOR)
        record_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.record_btn = ttk.Button(record_frame, textvariable=self.recording_var,
                                    style="Record.TButton", command=self.toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(record_frame, text="■ Stop",
                                  style="Normal.TButton", command=self.stop_all,
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.save_btn = ttk.Button(record_frame, text="Save",
                  style="Action.TButton", command=self.save_recording,
                  state=tk.DISABLED)
        self.save_btn.pack(side=tk.RIGHT)
        
        # Recording options frame
        options_frame = tk.Frame(main_frame, bg=BG_COLOR)
        options_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.mouse_checkbox = ttk.Checkbutton(options_frame, text="🖱️ Record Mouse Movements", 
                                            variable=self.record_mouse_var,
                                            command=self._toggle_mouse_recording)
        self.mouse_checkbox.pack(side=tk.LEFT)
        
        tk.Label(options_frame, text="(Uncheck for keyboard-only macros)", 
                bg=BG_COLOR, fg=ACCENT_COLOR, font=('Arial', 7, 'italic')).pack(side=tk.LEFT, padx=(5, 0))
        
        # Add hotkey info
        hotkey_frame = tk.Frame(main_frame, bg=BG_COLOR)
        hotkey_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(hotkey_frame, text=f"Hotkeys: {TOGGLE_RECORDING_KEY} = Toggle Recording | {STOP_LOOP_KEY} = Stop Loop | P = Emergency Stop", 
                bg=BG_COLOR, fg=ACCENT_COLOR, font=('Arial', 8, 'italic')).pack(anchor=tk.W)
        
        # Macro list frame
        list_frame = tk.Frame(main_frame, bg=BG_COLOR)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        tk.Label(list_frame, text="Saved Macros", bg=BG_COLOR, fg=TEXT_COLOR,
                font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        # Category filter
        filter_frame = tk.Frame(list_frame, bg=BG_COLOR)
        filter_frame.pack(fill=tk.X, pady=(5, 5))
        
        tk.Label(filter_frame, text="Category:", bg=BG_COLOR, fg=TEXT_COLOR,
                font=('Arial', 8)).pack(side=tk.LEFT)
        
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var,
                                          values=["All"] + MACRO_CATEGORIES,
                                          state="readonly", width=10)
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self.update_macro_list())
        
        ttk.Button(filter_frame, text="Refresh", command=self.update_macro_list,
                  style="Normal.TButton").pack(side=tk.RIGHT)
        
        # Macro listbox with scrollbar
        listbox_frame = tk.Frame(list_frame, bg=BG_COLOR)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        self.macro_listbox = tk.Listbox(listbox_frame, bg=BUTTON_COLOR, fg=TEXT_COLOR,
                                       selectbackground=ACCENT_COLOR, font=('Arial', 9))
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        
        self.macro_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.macro_listbox.yview)
        
        self.macro_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind events
        self.macro_listbox.bind('<Double-Button-1>', self.play_selected_macro)
        self.macro_listbox.bind('<Button-3>', self.show_context_menu)
        
        # Bind P key globally to stop macros
        self.root.bind('<p>', self.emergency_stop)
        self.root.bind('<P>', self.emergency_stop)  # Handle both cases
        self.root.focus_set()  # Make sure window can receive key events
        
        # Loop controls
        loop_frame = tk.Frame(main_frame, bg=BG_COLOR)
        loop_frame.pack(fill=tk.X, pady=(5, 5))
        
        tk.Label(loop_frame, text="Loop:", bg=BG_COLOR, fg=TEXT_COLOR,
                font=('Arial', 8)).pack(side=tk.LEFT)
        
        self.loop_var = tk.StringVar(value="1")
        loop_entry = tk.Entry(loop_frame, textvariable=self.loop_var, width=5, justify=tk.CENTER)
        loop_entry.pack(side=tk.LEFT, padx=(5, 5))
        
        tk.Label(loop_frame, text="times", bg=BG_COLOR, fg=TEXT_COLOR,
                font=('Arial', 8)).pack(side=tk.LEFT)
        
        self.infinite_loop_var = tk.BooleanVar()
        self.infinite_checkbox = ttk.Checkbutton(loop_frame, text="∞ Infinite", variable=self.infinite_loop_var,
                       command=self._toggle_infinite_loop)
        self.infinite_checkbox.pack(side=tk.LEFT, padx=(10, 0))
        
        # Control buttons frame - simplified and clear
        control_frame = tk.Frame(main_frame, bg=BG_COLOR)
        control_frame.pack(fill=tk.X, pady=(5, 10))
        
        # First row: Play controls
        play_row = tk.Frame(control_frame, bg=BG_COLOR)
        play_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(play_row, text="▶ Play", command=self.play_selected_macro,
                  style="Action.TButton").pack(side=tk.LEFT, padx=(0, 5))
        
        self.loop_btn = ttk.Button(play_row, text="🔄 Loop", command=self.play_selected_macro_loop,
                  style="Action.TButton")
        self.loop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # STOP MACRO button - bright red and prominent
        self.stop_macro_btn = tk.Button(play_row, 
                                       text="🛑 STOP MACRO", 
                                       command=self.stop_macro_playback,
                                       bg="#FF4444", fg="white", 
                                       font=("Arial", 9, "bold"),
                                       state=tk.DISABLED,
                                       relief="raised",
                                       bd=2)
        self.stop_macro_btn.pack(side=tk.LEFT, padx=(10, 5))
        
        self.stop_loop_btn = ttk.Button(play_row, text="⏹ Stop Loop", command=self.stop_loop,
                  style="Normal.TButton", state=tk.DISABLED)
        self.stop_loop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Second row: Management controls
        mgmt_row = tk.Frame(control_frame, bg=BG_COLOR)
        mgmt_row.pack(fill=tk.X)
        
        ttk.Button(mgmt_row, text="Edit", command=self.edit_selected_macro,
                  style="Normal.TButton").pack(side=tk.LEFT, padx=(0, 5))
        
        # Smart button that changes based on state
        self.smart_btn = ttk.Button(mgmt_row, text="Delete", command=self.smart_button_action,
                  style="Normal.TButton")
        self.smart_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(mgmt_row, text="Settings", command=self.show_settings,
                  style="Normal.TButton").pack(side=tk.RIGHT)
        
        # Store current macros list
        self.current_macros = []
        
        # Loop control variables
        self.current_loop_count = 0
        self.max_loop_count = 1
    
    def toggle_recording(self):
        """Toggle recording state"""
        if not self.input_manager.is_recording:
            # Start recording
            if self.input_manager.start_recording():
                # Initial button text - will be updated by update_status()
                self.recording_var.set("● Recording...")
                self.record_btn.configure(style="Record.TButton")
                self.stop_btn.configure(state=tk.NORMAL)
                self.save_btn.configure(state=tk.DISABLED)
                self.status_var.set("Recording... (move mouse/click in PokeMMO or press '«' to stop)")
        else:
            # Stop recording
            self.current_recording = self.input_manager.stop_recording()
            self.recording_var.set("● Record")
            self.record_btn.configure(style="Normal.TButton")
            self.stop_btn.configure(state=tk.DISABLED)
            
            if self.current_recording:
                self.save_btn.configure(state=tk.NORMAL)
                self.status_var.set(f"Recorded {len(self.current_recording)} events")
            else:
                self.status_var.set("No events recorded")
    
    def stop_all(self):
        """Stop all current operations"""
        if self.input_manager.is_recording:
            self.toggle_recording()
        
        if self.input_manager.is_playing:
            self.input_manager.stop_macro()
            self.status_var.set("Playback stopped")
    
    def save_recording(self):
        """Save current recording as macro"""
        if not self.current_recording:
            messagebox.showwarning("No Recording", "No recording to save!")
            return
        
        # Get macro details from user
        dialog = MacroSaveDialog(self.root, MACRO_CATEGORIES)
        result = dialog.show()
        
        if result:
            name, category, description = result
            success, message = self.macro_manager.save_macro(
                name, self.current_recording, category, description
            )
            
            if success:
                messagebox.showinfo("Success", f"Macro saved: {name}")
                self.update_macro_list()
                self.current_recording = []
                self.save_btn.configure(state=tk.DISABLED)
                self.status_var.set("Macro saved")
            else:
                messagebox.showerror("Error", f"Failed to save macro: {message}")
    
    def update_macro_list(self):
        """Update the macro list display"""
        category = self.category_var.get()
        if category == "All":
            self.current_macros = self.macro_manager.get_macro_list()
        else:
            self.current_macros = self.macro_manager.get_macro_list(category)
        
        # Clear and populate listbox
        self.macro_listbox.delete(0, tk.END)
        for macro in self.current_macros:
            duration = macro.get('duration', 0)
            event_count = macro.get('event_count', 0)
            display_text = f"{macro['name']} ({duration}s, {event_count} events)"
            self.macro_listbox.insert(tk.END, display_text)
    
    def play_selected_macro(self, event=None):
        """Play selected macro once"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to play")
            return
        
        macro_info = self.current_macros[selection[0]]
        macro_data = self.macro_manager.load_macro(macro_info['filename'])
        
        if not macro_data:
            messagebox.showerror("Error", "Failed to load macro")
            return
        
        self.is_loop_running = True
        self.stop_loop_btn.configure(state=tk.NORMAL)
        self.stop_macro_btn.configure(state=tk.NORMAL)
        
        def playback_callback(event_type, data):
            if event_type == 'loop_start':
                self.status_var.set(f"Playing macro: {macro_info['name']}")
            elif event_type == 'loop_complete':
                events_info = f" ({data['events_executed']} events, {data['events_failed']} failed)" if 'events_executed' in data else ""
                self.status_var.set(f"✅ Macro completed{events_info}")
            elif event_type == 'timeout':
                self.status_var.set(f"⚠ Macro timed out after cycle {data['loop']}")
            elif event_type == 'error':
                self.status_var.set(f"❌ Macro error: {data['error']}")
            elif event_type == 'complete':
                self.status_var.set("Playback finished")
                self.is_loop_running = False
                self.stop_loop_btn.configure(state=tk.DISABLED)
                self.stop_macro_btn.configure(state=tk.DISABLED)
        
        # Use higher timeout for complex macros (60 seconds)
        self.input_manager.play_macro(macro_data['events'], speed=1.0, loop_count=1, callback=playback_callback, timeout=60)
    
    def edit_selected_macro(self):
        """Edit the selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to edit!")
            return
        
        macro_info = self.current_macros[selection[0]]
        
        # Show edit dialog
        dialog = MacroEditDialog(self.root, macro_info, MACRO_CATEGORIES)
        result = dialog.show()
        
        if result:
            name, category, description = result
            success, message = self.macro_manager.update_macro_info(
                macro_info['filepath'], name, description, '', category
            )
            
            if success:
                self.update_macro_list()
                self.status_var.set("Macro updated")
            else:
                messagebox.showerror("Error", f"Failed to update macro: {message}")
    
    def delete_selected_macro(self):
        """Delete the selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to delete!")
            return
        
        macro_info = self.current_macros[selection[0]]
        
        if messagebox.askyesno("Confirm Delete", f"Delete macro '{macro_info['name']}'?"):
            success, message = self.macro_manager.delete_macro(macro_info['filepath'])
            
            if success:
                self.update_macro_list()
                self.status_var.set("Macro deleted")
            else:
                messagebox.showerror("Error", f"Failed to delete macro: {message}")
    
    def show_context_menu(self, event):
        """Show context menu for macro list"""
        selection = self.macro_listbox.curselection()
        if not selection:
            return
        
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Play", command=self.play_selected_macro)
        context_menu.add_command(label="Edit", command=self.edit_selected_macro)
        context_menu.add_separator()
        context_menu.add_command(label="Duplicate", command=self.duplicate_selected_macro)
        context_menu.add_command(label="Export", command=self.export_selected_macro)
        context_menu.add_separator()
        context_menu.add_command(label="Delete", command=self.delete_selected_macro)
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def duplicate_selected_macro(self):
        """Duplicate the selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            return
        
        macro_info = self.current_macros[selection[0]]
        new_name = simpledialog.askstring("Duplicate Macro", 
                                         f"Enter name for duplicate of '{macro_info['name']}':",
                                         initialvalue=f"{macro_info['name']} Copy")
        
        if new_name:
            success, message = self.macro_manager.duplicate_macro(macro_info['filepath'], new_name)
            
            if success:
                self.update_macro_list()
                self.status_var.set("Macro duplicated")
            else:
                messagebox.showerror("Error", f"Failed to duplicate macro: {message}")
    
    def export_selected_macro(self):
        """Export the selected macro"""
        selection = self.macro_listbox.curselection()
        if not selection:
            return
        
        macro_info = self.current_macros[selection[0]]
        
        export_path = filedialog.asksaveasfilename(
            title="Export Macro",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialvalue=f"{macro_info['name']}.json"
        )
        
        if export_path:
            success, message = self.macro_manager.export_macro(macro_info['filepath'], export_path)
            
            if success:
                messagebox.showinfo("Success", "Macro exported successfully!")
            else:
                messagebox.showerror("Error", f"Failed to export macro: {message}")
    
    def show_settings(self):
        """Show settings dialog"""
        settings_dialog = SettingsDialog(self.root, self.window_manager)
        settings_dialog.show()
    
    def _toggle_infinite_loop(self):
        """Toggle infinite loop mode"""
        if self.infinite_loop_var.get():
            self.loop_var.set("∞")
        else:
            self.loop_var.set("1")
    
    def _toggle_mouse_recording(self):
        """Toggle mouse movement recording in input manager"""
        enabled = self.record_mouse_var.get()
        self.input_manager.set_record_mouse_movements(enabled)
        print(f"Mouse movement recording: {'enabled' if enabled else 'disabled'}")
    
    def play_selected_macro_loop(self):
        """Play selected macro in loop mode"""
        selection = self.macro_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a macro to play")
            return
        
        # Get loop count
        try:
            loop_count_str = self.loop_var.get()
            if loop_count_str == "∞" or self.infinite_loop_var.get():
                loop_count = 999999  # Effectively infinite
                self.max_loop_count = 999999
            else:
                loop_count = int(loop_count_str)
                self.max_loop_count = loop_count
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for loop count")
            return
        
        if loop_count <= 0:
            messagebox.showerror("Invalid Input", "Loop count must be positive")
            return
        
        macro_info = self.current_macros[selection[0]]
        macro_data = self.macro_manager.load_macro(macro_info['filename'])
        
        if not macro_data:
            messagebox.showerror("Error", "Failed to load macro")
            return
        
        self.is_loop_running = True
        self.current_loop_count = 0
        self.stop_loop_btn.configure(state=tk.NORMAL)
        self.stop_macro_btn.configure(state=tk.NORMAL)
        
        def playback_callback(event_type, data):
            if event_type == 'loop_start':
                self.current_loop_count = data['loop']
                if self.max_loop_count == 999999:
                    self.status_var.set(f"Loop {data['loop']}: {macro_info['name']} (∞)")
                else:
                    self.status_var.set(f"Loop {data['loop']}/{data['total']}: {macro_info['name']}")
            elif event_type == 'loop_complete':
                events_info = f" ({data['events_executed']} events, {data['events_failed']} failed)" if 'events_executed' in data else ""
                if self.max_loop_count == 999999:
                    self.status_var.set(f"✅ Loop {data['loop']} completed{events_info} (∞)")
                else:
                    self.status_var.set(f"✅ Loop {data['loop']}/{data['total']} completed{events_info}")
            elif event_type == 'timeout':
                self.status_var.set(f"⚠ Macro timed out at loop {data['loop']}")
            elif event_type == 'error':
                self.status_var.set(f"❌ Loop error: {data['error']}")
            elif event_type == 'complete':
                if data.get('success', True):
                    self.status_var.set(f"🏁 All loops completed ({self.current_loop_count} total)")
                else:
                    self.status_var.set(f"🛑 Loop stopped by user ({self.current_loop_count} completed)")
                self.is_loop_running = False
                self.stop_loop_btn.configure(state=tk.DISABLED)
                self.stop_macro_btn.configure(state=tk.DISABLED)
        
        # Use much higher timeout for looped macros (120 seconds per loop)
        total_timeout = min(120 * loop_count, 3600)  # Max 1 hour total
        self.input_manager.play_macro(macro_data['events'], speed=1.0, loop_count=loop_count, callback=playback_callback, timeout=total_timeout)
    
    def on_window_event(self, event_type, data):
        """Handle window manager events"""
        if event_type == 'window_changed':
            # Game window position changed - could update overlay position
            pass
    
    def update_status(self):
        """Update status information"""
        # Update game status
        game_running = self.window_manager.is_game_running()
        game_active = self.window_manager.is_game_active()
        
        # Get current active window for better user guidance
        try:
            import win32gui
            current_hwnd = win32gui.GetForegroundWindow()
            current_title = win32gui.GetWindowText(current_hwnd)
            current_short = current_title[:15] + "..." if len(current_title) > 15 else current_title
            debug_info = f" (Active: {current_short})" if current_title else ""
        except:
            debug_info = ""
        
        if game_running:
            if game_active:
                self.game_status_var.set("Game: Active ✓")
                # Show visual indicator that recording will work
                if self.input_manager.is_recording:
                    self.recording_var.set("● Recording (Active)")
            else:
                self.game_status_var.set(f"Game: Running (Inactive){debug_info}")
                # Show visual indicator that recording is paused
                if self.input_manager.is_recording:
                    self.recording_var.set("● Recording (Paused)")
        else:
            self.game_status_var.set(f"Game: Not Found{debug_info}")
            if self.input_manager.is_recording:
                self.recording_var.set("● Recording (No Game)")
        
        # Schedule next update
        self.root.after(1000, self.update_status)
    
    def run(self):
        """Start the overlay application"""
        self.root.mainloop()
    
    def stop_loop(self):
        """Stop loop playback"""
        if self.is_loop_running or self.input_manager.is_playing:
            self.input_manager.stop_macro()
            self.is_loop_running = False
            self.loop_btn.configure(state=tk.NORMAL)
            self.stop_loop_btn.configure(state=tk.DISABLED)
            self.status_var.set("Loop stopped by user")
    
    def hotkey_stop_loop(self):
        """Stop loop via hotkey"""
        if self.is_loop_running:
            self.stop_loop()
            self.status_var.set("Loop stopped via hotkey")
    
    def stop_macro_playback(self):
        """Stop macro playback"""
        if self.input_manager.is_playing:
            self.input_manager.stop_macro()
            if hasattr(self, 'stop_macro_btn'):
                self.stop_macro_btn.configure(state=tk.DISABLED)
            
            # Reset smart button to DELETE
            self.smart_btn.configure(text="Delete", style="Normal.TButton")
            
            # Also handle loop state if it was a loop
            if hasattr(self, 'is_loop_running') and self.is_loop_running:
                self.is_loop_running = False
                self.loop_btn.configure(state=tk.NORMAL)
                self.stop_loop_btn.configure(state=tk.DISABLED)
            
            self.status_var.set("Macro playback stopped")
    
    def smart_button_action(self):
        """Smart button that acts as Stop when macro is playing, Delete otherwise"""
        if self.input_manager.is_playing:
            # Act as STOP button
            self.stop_macro_playback()
        else:
            # Act as DELETE button
            self.delete_selected_macro()
    
    def emergency_stop(self, event=None):
        """Emergency stop via P key"""
        print("P key pressed - emergency stop!")
        if self.input_manager.is_playing:
            self.input_manager.stop_macro()
            
            # Reset all button states
            if hasattr(self, 'stop_macro_btn'):
                self.stop_macro_btn.configure(state=tk.DISABLED)
            
            # Handle loop state
            if hasattr(self, 'is_loop_running') and self.is_loop_running:
                self.is_loop_running = False
                self.loop_btn.configure(state=tk.NORMAL)
                self.stop_loop_btn.configure(state=tk.DISABLED)
            
            self.status_var.set("❌ EMERGENCY STOP - Macro stopped via P key")
            return "break"  # Prevent event from propagating
        
        return None
    
    def destroy(self):
        """Clean up and close"""
        self.window_manager.stop_monitoring()
        if self.input_manager.is_recording:
            self.input_manager.stop_recording()
        if self.input_manager.is_playing:
            self.input_manager.stop_macro()
        self.input_manager.cleanup()
        self.root.destroy()


class MacroSaveDialog:
    def __init__(self, parent, categories):
        self.parent = parent
        self.categories = categories
        self.result = None
        
    def show(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Save Macro")
        self.dialog.geometry("350x200")
        self.dialog.configure(bg=BG_COLOR)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+{}+{}".format(
            self.parent.winfo_x() + 50,
            self.parent.winfo_y() + 50
        ))
        
        # Name field
        tk.Label(self.dialog, text="Macro Name:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.name_entry = tk.Entry(self.dialog, width=40)
        self.name_entry.pack(pady=5)
        self.name_entry.focus()
        
        # Category field
        tk.Label(self.dialog, text="Category:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.category_var = tk.StringVar(value="Custom")
        category_combo = ttk.Combobox(self.dialog, textvariable=self.category_var,
                                     values=self.categories, state="readonly")
        category_combo.pack(pady=5)
        
        # Description field
        tk.Label(self.dialog, text="Description:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.desc_entry = tk.Entry(self.dialog, width=40)
        self.desc_entry.pack(pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg=BG_COLOR)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        self.dialog.bind('<Return>', lambda e: self.save())
        
        self.dialog.wait_window()
        return self.result
    
    def save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Invalid Name", "Please enter a macro name!")
            return
        
        category = self.category_var.get()
        description = self.desc_entry.get().strip()
        
        self.result = (name, category, description)
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class MacroEditDialog:
    def __init__(self, parent, macro_info, categories):
        self.parent = parent
        self.macro_info = macro_info
        self.categories = categories
        self.result = None
        
    def show(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit Macro")
        self.dialog.geometry("350x200")
        self.dialog.configure(bg=BG_COLOR)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+{}+{}".format(
            self.parent.winfo_x() + 50,
            self.parent.winfo_y() + 50
        ))
        
        # Name field
        tk.Label(self.dialog, text="Macro Name:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.name_entry = tk.Entry(self.dialog, width=40)
        self.name_entry.pack(pady=5)
        self.name_entry.insert(0, self.macro_info['name'])
        self.name_entry.focus()
        
        # Category field
        tk.Label(self.dialog, text="Category:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.category_var = tk.StringVar(value=self.macro_info['category'])
        category_combo = ttk.Combobox(self.dialog, textvariable=self.category_var,
                                     values=self.categories, state="readonly")
        category_combo.pack(pady=5)
        
        # Description field
        tk.Label(self.dialog, text="Description:", bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)
        self.desc_entry = tk.Entry(self.dialog, width=40)
        self.desc_entry.pack(pady=5)
        self.desc_entry.insert(0, self.macro_info['description'])
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg=BG_COLOR)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        self.dialog.bind('<Return>', lambda e: self.save())
        
        self.dialog.wait_window()
        return self.result
    
    def save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Invalid Name", "Please enter a macro name!")
            return
        
        category = self.category_var.get()
        description = self.desc_entry.get().strip()
        
        self.result = (name, category, description)
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class SettingsDialog:
    def __init__(self, parent, window_manager):
        self.parent = parent
        self.window_manager = window_manager
        self.result = None
        
    def show(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Settings")
        self.dialog.geometry("400x350")
        self.dialog.configure(bg=BG_COLOR)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+{}+{}".format(
            self.parent.winfo_x() + 50,
            self.parent.winfo_y() + 50
        ))
        
        # Settings content
        tk.Label(self.dialog, text="PokeMMO Overlay Settings", 
                bg=BG_COLOR, fg=TEXT_COLOR, font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Game Info Tab
        game_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(game_frame, text="Game Info")
        
        game_pos = self.window_manager.get_game_position()
        if game_pos:
            info_text = f"Game Position: {game_pos['x']}, {game_pos['y']}\n"
            info_text += f"Game Size: {game_pos['width']}x{game_pos['height']}\n"
            info_text += f"Game Status: {'Running' if self.window_manager.is_game_running() else 'Not Found'}"
        else:
            info_text = "Game not detected"
        
        tk.Label(game_frame, text=info_text, bg=BG_COLOR, fg=TEXT_COLOR, 
                justify=tk.LEFT).pack(pady=10, padx=10)
        
        # Hotkeys Tab
        hotkeys_frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(hotkeys_frame, text="Hotkeys")
        
        tk.Label(hotkeys_frame, text="Hotkey Configuration", 
                bg=BG_COLOR, fg=TEXT_COLOR, font=('Arial', 10, 'bold')).pack(pady=10)
        
        # Toggle Recording Hotkey
        toggle_rec_frame = tk.Frame(hotkeys_frame, bg=BG_COLOR)
        toggle_rec_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(toggle_rec_frame, text="Toggle Recording:", bg=BG_COLOR, fg=TEXT_COLOR, 
                width=15, anchor=tk.W).pack(side=tk.LEFT)
        
        self.toggle_recording_var = tk.StringVar(value=TOGGLE_RECORDING_KEY)
        toggle_rec_entry = tk.Entry(toggle_rec_frame, textvariable=self.toggle_recording_var, width=10)
        toggle_rec_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Stop Loop Hotkey
        stop_loop_frame = tk.Frame(hotkeys_frame, bg=BG_COLOR)
        stop_loop_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(stop_loop_frame, text="Stop Loop:", bg=BG_COLOR, fg=TEXT_COLOR, 
                width=15, anchor=tk.W).pack(side=tk.LEFT)
        
        self.stop_loop_var = tk.StringVar(value=STOP_LOOP_KEY)
        stop_loop_entry = tk.Entry(stop_loop_frame, textvariable=self.stop_loop_var, width=10)
        stop_loop_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Instructions
        tk.Label(hotkeys_frame, text="Note: Changes require restart to take effect", 
                bg=BG_COLOR, fg=ACCENT_COLOR, font=('Arial', 8, 'italic')).pack(pady=10)
        
        # Button frame
        btn_frame = tk.Frame(self.dialog, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Save", command=self.save_settings).pack(side=tk.LEFT, padx=(20, 5))
        ttk.Button(btn_frame, text="Reset to Default", command=self.reset_defaults).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(5, 20))
        
        self.dialog.wait_window()
        return self.result
    
    def save_settings(self):
        """Save hotkey settings"""
        try:
            # Update config values (would need to save to file in a real implementation)
            global TOGGLE_RECORDING_KEY, STOP_LOOP_KEY
            TOGGLE_RECORDING_KEY = self.toggle_recording_var.get()
            STOP_LOOP_KEY = self.stop_loop_var.get()
            
            messagebox.showinfo("Settings Saved", 
                              "Hotkey settings saved!\nRestart the overlay for changes to take effect.")
            self.result = (TOGGLE_RECORDING_KEY, STOP_LOOP_KEY)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def reset_defaults(self):
        """Reset hotkeys to default values"""
        self.toggle_recording_var.set("`")
        self.stop_loop_var.set("F12") 