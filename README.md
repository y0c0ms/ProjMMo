# PokeMMO Overlay - Macro System

A Python-based overlay application for PokeMMO that allows you to record and replay keyboard/mouse macros.

## Features

- **🎥 Record & Replay**: Capture exact mouse movements, clicks, and keyboard inputs
- **📁 Macro Organization**: Save macros in categories (Movement, Battles, Inventory, etc.)
- **🎯 Game Detection**: Automatically detects PokeMMO window
- **📐 Relative Positioning**: Coordinates adapt to window position/size changes
- **⏱️ Precise Timing**: Maintains exact timing between recorded actions
- **🔄 Loop Support**: Repeat macros multiple times
- **🚫 Emergency Stop**: ESC key stops any running macro
- **💾 Import/Export**: Share macros with others

## Installation

### 1. Install Python Requirements

```bash
pip install -r requirements.txt
```

### 2. Install Required Packages

If you don't have pip, install these manually:
- `pynput` - For input capture and simulation
- `pywin32` - For Windows API access

### 3. Run the Application

```bash
python main.py
```

## How to Use

### Recording a Macro

1. **Start PokeMMO** first
2. **Click "● Record"** in the overlay
3. **Perform actions** in PokeMMO (move, click, type, etc.)
4. **Click "● Record"** again to stop
5. **Click "Save"** and give your macro a name
6. **Choose category** and add description (optional)

### Playing a Macro

1. **Select a macro** from the list
2. **Double-click** or press **"▶ Play"**
3. **Make sure PokeMMO is active** (the overlay will check)
4. **Press ESC** to emergency stop if needed

### Organizing Macros

- **Categories**: Movement, Battles, Inventory, Trading, Custom
- **Edit**: Right-click → Edit to change name/category/description
- **Duplicate**: Right-click → Duplicate to copy a macro
- **Export**: Right-click → Export to save macro file

## File Structure

```
pokemmo_overlay/
├── main.py              # Entry point
├── overlay.py           # Main UI window
├── input_manager.py     # Input capture/playback
├── window_manager.py    # Game window detection
├── macro_manager.py     # Save/load macros
├── config.py           # Settings
├── requirements.txt    # Dependencies
├── macros/             # Saved macro files
│   ├── movement/
│   ├── battles/
│   ├── inventory/
│   ├── trading/
│   └── custom/
└── README.md
```

## Macro Examples

### Movement Patterns
- **Route Grinding**: Record walking patterns for EV training
- **Repel Farming**: Automate repel usage while grinding
- **Daycare Routes**: Optimize egg hatching routes

### Battle Sequences
- **Move Combinations**: Record specific battle strategies
- **Item Usage**: Automate healing and item management
- **Pokemon Switching**: Complex battle rotations

### Menu Navigation
- **PC Organization**: Automate box management
- **Shop Purchases**: Bulk buying items
- **Trade Setups**: Prepare trades efficiently

## Technical Details

### Mouse Tracking
- **Pixel-perfect accuracy** with sub-pixel precision
- **Movement paths** recorded with natural curves
- **Click timing** maintains human-like patterns
- **Scroll wheel** support for menu navigation

### Coordinate System
- **Relative positioning** to PokeMMO window
- **Automatic adjustment** when window moves/resizes
- **Multi-monitor support** with correct coordinate translation

### Safety Features
- **Game detection** - only works when PokeMMO is active
- **Emergency stop** - ESC key immediately halts playback
- **Input validation** - prevents invalid macro execution
- **Window focus** - ensures inputs go to correct window

## Troubleshooting

### "Game: Not Found"
- Make sure PokeMMO is running
- Check that window title contains "PokeMMO"
- Try restarting the overlay

### Macro Not Playing
- Ensure PokeMMO window is active/focused
- Check that macro file exists and isn't corrupted
- Verify no other macro is currently running

### Recording Issues
- Run as Administrator if input capture fails
- Check antivirus isn't blocking pynput
- Ensure no other macro software is interfering

### Dependencies Missing
```bash
pip install pynput pywin32
```

## Configuration

Edit `config.py` to customize:
- Overlay window size and position
- Recording precision and thresholds
- Playback speed and safety delays
- UI colors and appearance

## Advanced Usage

### Macro Editing
- Macros are stored as JSON files
- Edit timing, coordinates, or actions manually
- Add conditional logic (advanced users)

### Sharing Macros
- Export macros to share with friends
- Import macros from others
- Backup your macro collection

## System Requirements

- **Windows 10/11** (Win32 API required)
- **Python 3.7+**
- **PokeMMO** (any version)
- **4GB RAM** minimum
- **Mouse/Keyboard** for recording

## License

This project is for educational purposes only. Use responsibly and in accordance with game terms of service.

## Support

If you encounter issues:
1. Check this README
2. Verify all dependencies are installed
3. Run as Administrator if needed
4. Check Windows permissions for input simulation

---

**Remember**: This tool automates game actions. Always use responsibly and respect the game's community and rules. 