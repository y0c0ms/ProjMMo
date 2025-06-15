"""
Window Manager for detecting and tracking PokeMMO game window
"""
import win32gui
import win32con
import threading
import time
from config import GAME_WINDOW_TITLE, DETECTION_INTERVAL

class WindowManager:
    def __init__(self):
        self.game_hwnd = None
        self.game_rect = None
        self.is_monitoring = False
        self.monitor_thread = None
        self.callbacks = []
        
    def find_game_window(self):
        """Find PokeMMO window handle - returns list of candidates but doesn't auto-select"""
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                
                # Skip our own overlay window
                if "PokeMMO Overlay" in window_title:
                    return True
                
                # Look for actual PokeMMO game window
                # The game window usually has titles like "PokeMMO" or contains location names
                title_lower = window_title.lower()
                
                # Skip browsers, YouTube, and other non-game windows
                skip_keywords = ["youtube", "chrome", "firefox", "edge", "browser", "thorium", "opera", "safari"]
                if any(skip in title_lower for skip in skip_keywords):
                    return True
                
                # Look for PokeMMO game indicators
                pokemmo_indicators = [
                    "pokemmo",  # Base game title
                    "route",    # Route names
                    "city",     # City names  
                    "town",     # Town names
                    "cave",     # Cave names
                    "forest",   # Forest names
                    "island",   # Island names
                    "meadow",   # Meadow names (like in your screenshot)
                    "gym",      # Gym names
                    "center",   # Pokemon Center
                    "isle",     # Isle names (like Five Isle Meadow)
                    "ch.",      # Chapter indicators
                    "lv."       # Level indicators in Pokemon names
                ]
                
                for indicator in pokemmo_indicators:
                    if indicator in title_lower:
                        # Additional validation: check window size (PokeMMO windows are typically reasonable sizes)
                        try:
                            rect = win32gui.GetWindowRect(hwnd)
                            width = rect[2] - rect[0]
                            height = rect[3] - rect[1]
                            
                            # PokeMMO windows should be reasonable sizes (not tiny, not huge multi-monitor spans)
                            if 400 < width < 2000 and 300 < height < 1200:
                                windows.append((hwnd, window_title, width, height))
                                print(f"   Found PokeMMO candidate: {window_title} | {width}x{height}")
                                break
                            else:
                                print(f"   Skipping window with unusual size: {width}x{height}")
                        except:
                            # If we can't get window rect, skip it
                            pass
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        
        print(f"🔍 Found {len(windows)} PokeMMO window candidates:")
        for hwnd, title, width, height in windows:
            print(f"  - {title} | {width}x{height} | Handle: {hwnd}")
        
        if not windows:
            print("❌ No PokeMMO windows found")
            print("💡 Make sure PokeMMO is running and visible")
            print("💡 Looking for windows containing: route, city, town, cave, forest, island, meadow, gym, center, pokemmo, isle, ch., lv.")
            
            # List all visible windows for debugging
            print("\n🔍 All visible windows:")
            self.list_all_windows()
        
        return windows
    
    def select_window_by_handle(self, hwnd):
        """Manually select a window by its handle"""
        try:
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                self.game_hwnd = hwnd
                self.update_game_rect()
                window_title = win32gui.GetWindowText(hwnd)
                print(f"✓ Selected PokeMMO window: {window_title} (Handle: {hwnd})")
                return True
            else:
                print(f"❌ Invalid window handle: {hwnd}")
                return False
        except Exception as e:
            print(f"❌ Error selecting window: {e}")
            return False
    
    def list_all_windows(self):
        """List all visible windows for debugging"""
        def enum_all_windows(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title.strip():  # Only show windows with titles
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        windows.append((hwnd, window_title, width, height, rect))
                except:
                    pass
            return True
        
        all_windows = []
        win32gui.EnumWindows(enum_all_windows, all_windows)
        
        # Sort by window size (larger windows first)
        all_windows.sort(key=lambda x: x[2] * x[3], reverse=True)
        
        for i, (hwnd, title, width, height, rect) in enumerate(all_windows[:15]):  # Show top 15
            print(f"  {i+1:2d}. {title[:60]:<60} | {width:4d}x{height:4d} | Handle: {hwnd}")
        
        if len(all_windows) > 15:
            print(f"     ... and {len(all_windows) - 15} more windows")
    
    def update_game_rect(self):
        """Update game window rectangle"""
        if self.game_hwnd:
            try:
                self.game_rect = win32gui.GetWindowRect(self.game_hwnd)
                return True
            except:
                self.game_hwnd = None
                self.game_rect = None
                return False
        return False
    
    def is_game_active(self):
        """Check if PokeMMO window is active/focused"""
        if not self.game_hwnd:
            # Try to find the game window if we don't have it
            self.find_game_window()
            if not self.game_hwnd:
                return False
        
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
            # Also check if the window is still valid
            if not win32gui.IsWindow(self.game_hwnd):
                # Window handle is invalid, try to find it again
                self.find_game_window()
                if not self.game_hwnd:
                    return False
                foreground_hwnd = win32gui.GetForegroundWindow()
            
            return foreground_hwnd == self.game_hwnd
        except:
            # If there's an error, try to re-find the window
            self.find_game_window()
            return False
    
    def is_game_running(self):
        """Check if PokeMMO is still running"""
        if not self.game_hwnd:
            return False
        
        try:
            return win32gui.IsWindow(self.game_hwnd)
        except:
            return False
    
    def get_game_position(self):
        """Get game window position and size"""
        if self.game_rect:
            x, y, right, bottom = self.game_rect
            return {
                'x': x,
                'y': y, 
                'width': right - x,
                'height': bottom - y
            }
        return None
    
    def screen_to_game_coords(self, screen_x, screen_y):
        """Convert screen coordinates to game window relative coordinates"""
        if not self.game_rect:
            return screen_x, screen_y
        
        game_x = screen_x - self.game_rect[0]
        game_y = screen_y - self.game_rect[1]
        return game_x, game_y
    
    def game_to_screen_coords(self, game_x, game_y):
        """Convert game window relative coordinates to screen coordinates"""
        if not self.game_rect:
            return game_x, game_y
        
        screen_x = game_x + self.game_rect[0]
        screen_y = game_y + self.game_rect[1]
        return screen_x, screen_y
    
    def add_callback(self, callback):
        """Add callback for window events"""
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """Start monitoring game window"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring game window"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_loop(self):
        """Monitor loop for tracking window changes"""
        while self.is_monitoring:
            old_rect = self.game_rect
            
            # Try to find game if not found
            if not self.game_hwnd:
                self.find_game_window()
            
            # Update rect if game exists
            if self.game_hwnd:
                self.update_game_rect()
            
            # Check if window moved/resized
            if old_rect != self.game_rect:
                for callback in self.callbacks:
                    try:
                        callback('window_changed', self.get_game_position())
                    except:
                        pass
            
            time.sleep(DETECTION_INTERVAL) 