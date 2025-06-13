"""
Macro Manager for saving, loading, and organizing macros
"""
import os
import json
import time
from datetime import datetime
from config import MACROS_DIR, MACRO_CATEGORIES

class MacroManager:
    def __init__(self):
        self.macros_dir = MACROS_DIR
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create macro directories if they don't exist"""
        if not os.path.exists(self.macros_dir):
            os.makedirs(self.macros_dir)
        
        for category in MACRO_CATEGORIES:
            category_path = os.path.join(self.macros_dir, category.lower())
            if not os.path.exists(category_path):
                os.makedirs(category_path)
    
    def save_macro(self, name, events, category="Custom", description="", hotkey=""):
        """Save a macro to file"""
        if not events:
            return False, "No events to save"
        
        # Clean up name for filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_name:
            safe_name = f"macro_{int(time.time())}"
        
        # Create macro data
        macro_data = {
            'name': name,
            'description': description,
            'category': category,
            'hotkey': hotkey,
            'created_date': datetime.now().isoformat(),
            'duration': self._calculate_duration(events),
            'event_count': len(events),
            'events': events
        }
        
        # Save to appropriate category folder
        category_path = os.path.join(self.macros_dir, category.lower())
        filename = f"{safe_name}.json"
        filepath = os.path.join(category_path, filename)
        
        # Handle duplicate filenames
        counter = 1
        while os.path.exists(filepath):
            filename = f"{safe_name}_{counter}.json"
            filepath = os.path.join(category_path, filename)
            counter += 1
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(macro_data, f, indent=2, ensure_ascii=False)
            return True, filepath
        except Exception as e:
            return False, f"Error saving macro: {str(e)}"
    
    def load_macro(self, filepath):
        """Load a macro from file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                macro_data = json.load(f)
            return True, macro_data
        except Exception as e:
            return False, f"Error loading macro: {str(e)}"
    
    def get_macro_list(self, category=None):
        """Get list of available macros"""
        macros = []
        
        if category:
            # Get macros from specific category
            category_path = os.path.join(self.macros_dir, category.lower())
            if os.path.exists(category_path):
                macros.extend(self._scan_directory(category_path, category))
        else:
            # Get macros from all categories
            for cat in MACRO_CATEGORIES:
                category_path = os.path.join(self.macros_dir, cat.lower())
                if os.path.exists(category_path):
                    macros.extend(self._scan_directory(category_path, cat))
        
        return macros
    
    def get_macros(self, category=None):
        """Alias for get_macro_list for compatibility"""
        macro_list = self.get_macro_list(category)
        
        # Convert to format expected by main.py
        result = []
        for macro_info in macro_list:
            # Load the full macro data including events
            success, macro_data = self.load_macro(macro_info['filepath'])
            if success:
                result.append({
                    'name': macro_info['name'],
                    'category': macro_info['category'],
                    'description': macro_info.get('description', ''),
                    'events': macro_data.get('events', []),
                    'filepath': macro_info['filepath']
                })
        
        return result
    
    def _scan_directory(self, directory, category):
        """Scan directory for macro files"""
        macros = []
        
        try:
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(directory, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            macro_data = json.load(f)
                        
                        # Add file info
                        macro_info = {
                            'filepath': filepath,
                            'filename': filename,
                            'name': macro_data.get('name', filename[:-5]),
                            'description': macro_data.get('description', ''),
                            'category': macro_data.get('category', category),
                            'hotkey': macro_data.get('hotkey', ''),
                            'created_date': macro_data.get('created_date', ''),
                            'duration': macro_data.get('duration', 0),
                            'event_count': macro_data.get('event_count', 0)
                        }
                        
                        macros.append(macro_info)
                    
                    except Exception as e:
                        print(f"Error reading macro {filepath}: {e}")
        
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
        
        return macros
    
    def delete_macro(self, name_or_filepath):
        """Delete a macro file by name or filepath"""
        try:
            # If it's a filepath, use it directly
            if os.path.exists(name_or_filepath) and name_or_filepath.endswith('.json'):
                filepath = name_or_filepath
            else:
                # Search for macro by name
                filepath = None
                for macro_info in self.get_macro_list():
                    if macro_info['name'] == name_or_filepath:
                        filepath = macro_info['filepath']
                        break
                
                if not filepath:
                    return False
            
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            else:
                return False
        except Exception as e:
            return False
    
    def duplicate_macro(self, filepath, new_name):
        """Create a copy of an existing macro"""
        success, macro_data = self.load_macro(filepath)
        if not success:
            return False, macro_data
        
        # Update macro data
        macro_data['name'] = new_name
        macro_data['created_date'] = datetime.now().isoformat()
        
        # Save as new macro
        return self.save_macro(
            new_name,
            macro_data['events'],
            macro_data.get('category', 'Custom'),
            macro_data.get('description', ''),
            ''  # Clear hotkey for duplicate
        )
    
    def update_macro_info(self, filepath, name=None, description=None, hotkey=None, category=None):
        """Update macro metadata without changing events"""
        success, macro_data = self.load_macro(filepath)
        if not success:
            return False, macro_data
        
        # Update provided fields
        if name is not None:
            macro_data['name'] = name
        if description is not None:
            macro_data['description'] = description
        if hotkey is not None:
            macro_data['hotkey'] = hotkey
        if category is not None:
            macro_data['category'] = category
        
        # Save updated macro
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(macro_data, f, indent=2, ensure_ascii=False)
            
            # If category changed, move file
            if category and category != os.path.basename(os.path.dirname(filepath)).title():
                new_category_path = os.path.join(self.macros_dir, category.lower())
                new_filepath = os.path.join(new_category_path, os.path.basename(filepath))
                
                try:
                    os.rename(filepath, new_filepath)
                    return True, new_filepath
                except:
                    pass  # Keep in original location if move fails
            
            return True, filepath
        except Exception as e:
            return False, f"Error updating macro: {str(e)}"
    
    def _calculate_duration(self, events):
        """Calculate macro duration in seconds"""
        if not events:
            return 0
        
        first_timestamp = events[0]['timestamp']
        last_timestamp = events[-1]['timestamp']
        return round(last_timestamp - first_timestamp, 2)
    
    def get_macro_stats(self):
        """Get statistics about saved macros"""
        all_macros = self.get_macro_list()
        
        stats = {
            'total_macros': len(all_macros),
            'categories': {},
            'total_duration': 0,
            'total_events': 0
        }
        
        for macro in all_macros:
            category = macro['category']
            if category not in stats['categories']:
                stats['categories'][category] = 0
            
            stats['categories'][category] += 1
            stats['total_duration'] += macro.get('duration', 0)
            stats['total_events'] += macro.get('event_count', 0)
        
        return stats
    
    def export_macro(self, filepath, export_path):
        """Export macro to a different location"""
        try:
            success, macro_data = self.load_macro(filepath)
            if not success:
                return False, macro_data
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(macro_data, f, indent=2, ensure_ascii=False)
            
            return True, "Macro exported successfully"
        except Exception as e:
            return False, f"Error exporting macro: {str(e)}"
    
    def import_macro(self, import_path, category="Custom"):
        """Import macro from external file"""
        try:
            success, macro_data = self.load_macro(import_path)
            if not success:
                return False, macro_data
            
            # Validate macro data
            if 'events' not in macro_data or not macro_data['events']:
                return False, "Invalid macro file - no events found"
            
            # Save to local macros
            name = macro_data.get('name', 'Imported Macro')
            description = macro_data.get('description', 'Imported from external file')
            
            return self.save_macro(
                name,
                macro_data['events'],
                category,
                description,
                ''  # Clear hotkey for imported macro
            )
        except Exception as e:
            return False, f"Error importing macro: {str(e)}" 