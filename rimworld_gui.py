#!/usr/bin/env python3
"""
RimConvert GUI v1.0
===================

Modern GUI interface for RimWorld texture conversion using RimPy's proven approach.
Features dark theme, progress tracking, and user-friendly operation.

Key improvements from v1.0:
- Uses texconv.exe instead of nvcompress (matches RimPy's approach)
- BC7 compression with proper alpha channel handling
- No longer renames original PNGs (allows game fallback)
- Enhanced progress tracking with ETA calculations
- Background processing with cancel capability

Author: AI Assistant
Date: June 6, 2025
"""

import os
import sys
import json
import time
import threading
import subprocess
import shutil # Added import
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import StringVar, BooleanVar, IntVar, Tk, END, NORMAL, DISABLED, LEFT, RIGHT, TOP, BOTTOM, N, S, E, W, FLAT
import concurrent.futures # Added for ThreadPoolExecutor
import os # ensure os is imported if not already explicitly at top level for some reason

try:
    from PIL import Image as PILImage # Use PILImage alias
    PILLOW_AVAILABLE = True
except ImportError:
    PILImage = None
    PILLOW_AVAILABLE = False

# Configuration
CONFIG_FILE = "rimworld_optimizer_config.json"
# DEFAULT_TEXCONV_PATH is used as fallback - now uses relative path
script_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEXCONV_PATH = os.path.join(script_dir, "compressors", "texconv.exe")

def get_texconv_path():
    """Determine the path to texconv.exe, assuming it's in a 'compressors' subdirectory
    relative to the executable or script."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        app_dir = Path(sys.executable).parent
    else:
        # Running as script
        app_dir = Path(__file__).parent
    
    expected_texconv_path = app_dir / "compressors" / "texconv.exe"
    if expected_texconv_path.exists():
        return str(expected_texconv_path)
    return "" # Not found in the expected location

class RimWorldOptimizerGUI:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config() # Load config first to get geometry

        # Set window geometry
        saved_geometry = self.config.get('window_geometry')
        if saved_geometry:
            try:
                # Validate geometry string format (e.g., "800x600+100+100")
                if isinstance(saved_geometry, str) and 'x' in saved_geometry and '+' in saved_geometry:
                    self.root.geometry(saved_geometry)
                else:
                    self.root.geometry("800x650") # Default if format is invalid
                    self.log_message(f"Invalid window geometry format in config: {saved_geometry}. Using default.", "warning") # Log if possible, or print
            except tk.TclError: # Catch errors if Tkinter can't parse the geometry
                self.root.geometry("800x650") # Default on error
                self.log_message(f"Error applying window geometry: {saved_geometry}. Using default.", "warning")
        else:
            self.root.geometry("800x650") # Default if not found

        self.root.title("RimConvert") # UPDATED default window title
        # self.root.geometry("800x650") # Moved up
        self.root.resizable(True, True)
        
        # Configuration
        # self.config = self.load_config() # Moved up
        self.processing = False
        self.cancel_requested = False
        
        # Thread-safe variables
        self.progress_var = IntVar()
        self.status_var = StringVar(value="Initializing...") # Initial status
        self.eta_var = StringVar(value="")
        self.mods_path_var = StringVar() # Moved initialization here
        self.texconv_path_var = StringVar() # Moved initialization here
        
        # Setup GUI
        self.setup_style()
        self.create_widgets()
        self.load_settings() 
        self._reset_ui_state() 
        
        # Protocol handler for window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        """Handle window closing: save config (including geometry) and destroy window."""
        # Save current geometry
        self.config['window_geometry'] = self.root.geometry()
        self.save_config()
        self.root.destroy()

    def setup_style(self):
        """Setup dark theme styling to mimic Windows Dark Mode."""
        self.style = ttk.Style()

        # Windows Dark Mode-inspired colors
        self.win_bg_color = "#202020"      # Overall window/frame background (dark gray)
        self.win_fg_color = "#FFFFFF"      # General text (pure white for better contrast)
        
        self.ctrl_bg_color = "#2D2D2D"     # Background for buttons, entries (medium dark gray)
        self.ctrl_fg_color = "#FFFFFF"     # Text on controls (pure white)
        
        self.ctrl_hover_bg_color = "#3E3E3E" # Button hover (slightly lighter gray)
        self.ctrl_active_bg_color = "#4A4A4A" # Button pressed (even lighter)
        
        self.entry_field_bg_color = "#252525" # Background of text input area (very dark gray)
        
        self.accent_color = "#0078D4"      # Accent for progress bar, selections (Windows blue)
        self.accent_fg_color = "#FFFFFF"   # Text on accent background (white)

        self.disabled_fg_color = "#6B6B6B" # Disabled text color (medium gray)
        self.log_bg_color = "#1E1E1E"      # Log area background (very dark, like VS Code terminal)
        self.border_color = "#3C3C3C"      # Subtle border color for controls
        self.labelframe_bg_color = "#202020"  # Explicit background for label frames

        self.root.configure(bg=self.win_bg_color)
        
        self.style.theme_use('clam') 

        # Configure the theme to use our dark colors as defaults
        self.style.configure('.', 
                             background=self.win_bg_color,
                             foreground=self.win_fg_color,
                             bordercolor=self.border_color,
                             focuscolor=self.accent_color)

        # General Frame and Label
        self.style.configure('TFrame', 
                             background=self.win_bg_color,
                             borderwidth=0,
                             relief='flat')
        
        self.style.configure('TLabel', 
                             background=self.win_bg_color, 
                             foreground=self.win_fg_color, 
                             padding=2,
                             font=('Segoe UI Variable Text', 9))
        
        self.style.configure('Header.TLabel', 
                             background=self.win_bg_color,
                             foreground=self.win_fg_color,
                             font=('Segoe UI Variable Text', 16, 'bold')) 
        
        self.style.configure('Subtitle.TLabel', 
                             background=self.win_bg_color,
                             foreground=self.win_fg_color,
                             font=('Segoe UI Variable Text', 10))

        # Button
        self.style.configure('TButton', 
                             background=self.ctrl_bg_color, 
                             foreground=self.ctrl_fg_color,
                             bordercolor=self.border_color, 
                             lightcolor=self.ctrl_bg_color,
                             darkcolor=self.ctrl_bg_color,
                             font=('Segoe UI Variable Text', 9),
                             padding=(8, 5),
                             relief='flat',
                             borderwidth=1)
        self.style.map('TButton',
                       background=[('active', self.ctrl_active_bg_color), 
                                   ('hover', self.ctrl_hover_bg_color),
                                   ('disabled', self.ctrl_bg_color)],
                       foreground=[('disabled', self.disabled_fg_color),
                                   ('active', self.ctrl_fg_color),
                                   ('hover', self.ctrl_fg_color)],
                       bordercolor=[('disabled', self.disabled_fg_color)])

        # Entry
        self.style.configure('TEntry', 
                             fieldbackground=self.entry_field_bg_color, 
                             foreground=self.ctrl_fg_color, 
                             insertcolor=self.ctrl_fg_color, 
                             bordercolor=self.border_color, 
                             lightcolor=self.entry_field_bg_color,
                             darkcolor=self.entry_field_bg_color,
                             padding=5,
                             relief='flat',
                             borderwidth=1)
        self.style.map('TEntry',
                       foreground=[('disabled', self.disabled_fg_color)],
                       fieldbackground=[('disabled', self.ctrl_bg_color)],
                       bordercolor=[('focus', self.accent_color), ('disabled', self.disabled_fg_color)])

        # Progressbar
        self.style.configure('TProgressbar', 
                             background=self.accent_color, 
                             troughcolor=self.ctrl_bg_color,
                             bordercolor=self.border_color,
                             lightcolor=self.ctrl_bg_color,
                             darkcolor=self.ctrl_bg_color,
                             thickness=12,
                             relief='flat',
                             borderwidth=1)

        # Checkbutton
        self.style.configure('TCheckbutton', 
                             background=self.win_bg_color, 
                             foreground=self.win_fg_color,
                             focuscolor=self.accent_color,
                             indicatorbackground=self.entry_field_bg_color,
                             indicatorforeground=self.accent_color,
                             indicatormargin=5,
                             font=('Segoe UI Variable Text', 9),
                             padding=(5,5)) 
        self.style.map('TCheckbutton',
                       background=[('active', self.win_bg_color), ('hover', self.win_bg_color)],
                       foreground=[('disabled', self.disabled_fg_color)],
                       indicatorbackground=[('selected', self.accent_color),('active', self.ctrl_hover_bg_color)],
                       indicatorforeground=[('selected', self.accent_fg_color), ('pressed', self.accent_fg_color)])

        # Combobox
        self.style.configure('TCombobox', 
                             fieldbackground=self.entry_field_bg_color,
                             background=self.ctrl_bg_color, 
                             foreground=self.ctrl_fg_color,
                             arrowcolor=self.win_fg_color,
                             insertcolor=self.ctrl_fg_color, 
                             bordercolor=self.border_color,
                             lightcolor=self.ctrl_bg_color,
                             darkcolor=self.ctrl_bg_color,
                             padding=5,
                             relief='flat',
                             borderwidth=1)
        self.style.map('TCombobox',
            selectbackground=[('readonly', self.entry_field_bg_color)], 
            foreground=[('disabled', self.disabled_fg_color)],
            fieldbackground=[('disabled', self.ctrl_bg_color), ('focus', self.entry_field_bg_color)],
            bordercolor=[('focus', self.accent_color), ('disabled', self.disabled_fg_color)],
            arrowcolor=[('disabled', self.disabled_fg_color)])
        
        # Combobox dropdown styling
        self.root.option_add('*TCombobox*Listbox.background', self.entry_field_bg_color)
        self.root.option_add('*TCombobox*Listbox.foreground', self.win_fg_color)
        self.root.option_add('*TCombobox*Listbox.selectBackground', self.accent_color)
        self.root.option_add('*TCombobox*Listbox.selectForeground', self.accent_fg_color)
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI Variable Text', 9))
        self.root.option_add('*TCombobox*Listbox.borderWidth', 1)
        self.root.option_add('*TCombobox*Listbox.relief', 'solid')

        # LabelFrame - This is the key fix for the white boxes
        self.style.configure('TLabelframe', 
                             background=self.win_bg_color,
                             bordercolor=self.border_color,
                             relief='flat',
                             borderwidth=1)
        
        self.style.configure('TLabelframe.Label', 
                             background=self.win_bg_color, 
                             foreground=self.win_fg_color,
                             font=('Segoe UI Variable Text', 9, 'bold'))
        
        # Also configure the internal frame of LabelFrame
        self.style.map('TLabelframe',
                       background=[('active', self.win_bg_color), ('!active', self.win_bg_color)])
        
        # Scrollbar
        self.style.configure('TScrollbar', 
                             background=self.ctrl_bg_color,
                             troughcolor=self.win_bg_color,
                             bordercolor=self.border_color,
                             arrowcolor=self.win_fg_color,
                             gripcount=0,
                             relief='flat',
                             borderwidth=1)
        self.style.map('TScrollbar',
                       background=[('active', self.ctrl_active_bg_color),
                                   ('hover', self.ctrl_hover_bg_color),
                                   ('!active', self.ctrl_bg_color)],
                       arrowcolor=[('pressed', self.accent_color), 
                                   ('hover', self.accent_color),
                                   ('disabled', self.disabled_fg_color)],
                       troughcolor=[('disabled', self.win_bg_color)])

        # ScrolledText styling
        self.log_text_font = ('Consolas', 10) # Using a common monospace font
        # self.log_text styling is handled during its creation for bg/fg

    def create_widgets(self):
        """Create and layout GUI widgets."""
        # Main container with explicit dark styling
        main_frame = ttk.Frame(self.root, padding="10", style="TFrame")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1) # Ensure column 1 (entry) can expand
        main_frame.columnconfigure(0, weight=0) # Keep column 0 (labels) fixed
        main_frame.columnconfigure(2, weight=0) # Keep column 2 (buttons) fixed
        
        # Title
        title_label = ttk.Label(main_frame, text="RimConvert",
                               style='Header.TLabel', anchor=tk.CENTER) # UPDATED text, added anchor
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 5), sticky="ew") # Added sticky="ew" for centering
        
        subtitle_text = "A modern Rimworld texture optimization tool.\nMade for the community, by Sky"
        subtitle_label = ttk.Label(main_frame, text=subtitle_text, 
                                  style='Subtitle.TLabel', justify=tk.CENTER, anchor=tk.CENTER) # UPDATED text, added justify and anchor
        subtitle_label.grid(row=1, column=0, columnspan=3, pady=(0, 15), sticky="ew") # Added sticky="ew" for centering
        
        # Mods folder selection
        mods_label = ttk.Label(main_frame, text="RimWorld Mods Folder:")
        mods_label.grid(row=2, column=0, sticky=W, pady=(5,10))
        
        mods_entry = ttk.Entry(main_frame, textvariable=self.mods_path_var, width=50)
        mods_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(5,10))
        
        browse_button = ttk.Button(main_frame, text="Browse...", command=self.browse_mods_folder)
        browse_button.grid(row=2, column=2, padx=(10, 0), pady=(5,10))
        
        # Settings frame - explicitly use TLabelframe style
        settings_frame = ttk.LabelFrame(main_frame, text="Conversion Settings", padding="15", style="TLabelframe")
        settings_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)
        settings_frame.columnconfigure(1, weight=1)
        
        # Upscaling options
        self.enable_upscaling_var = BooleanVar(value=True)
        upscale_check = ttk.Checkbutton(settings_frame, text="Enable 2x upscaling for images smaller than 256x256 pixels", 
                                       variable=self.enable_upscaling_var)
        upscale_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=3)
        
        # Mipmap option (UI Hidden, forced to True)
        self.generate_mipmaps_var = BooleanVar(value=True) # Keep var, ensure it's True
        # mipmap_check = ttk.Checkbutton(settings_frame, text="Generate mipmaps (recommended for performance)", 
        #                               variable=self.generate_mipmaps_var)
        # mipmap_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=3) # UI element commented out
        
        # GPU acceleration toggle
        self.enable_gpu_var = BooleanVar(value=True)
        gpu_check = ttk.Checkbutton(settings_frame, text="Use GPU acceleration", 
                                   variable=self.enable_gpu_var)
        # gpu_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=3) # Original position commented out
        gpu_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=3) # New position (row 1, as mipmap_check is removed)
        
        # Compression format (UI Hidden, forced to BC7_UNORM)
        # compression_label = ttk.Label(settings_frame, text="Compression format:") # UI element commented out
        # compression_label.grid(row=3, column=0, sticky="w", pady=(8,5)) # UI element commented out
        
        self.compression_var = StringVar(value="BC7_UNORM") # Keep var, ensure it's BC7_UNORM
        # compression_combo = ttk.Combobox(settings_frame, textvariable=self.compression_var, 
        #                                values=["BC7_UNORM", "BC3_UNORM", "BC1_UNORM"], state="readonly",
        #                                font=('Segoe UI Variable Text', 9))
        # compression_combo.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(8,5)) # UI element commented out
        
        # Action buttons frame
        buttons_frame = ttk.Frame(main_frame, style="TFrame")
        buttons_frame.grid(row=5, column=0, columnspan=3, pady=15)
        
        self.convert_button = ttk.Button(buttons_frame, text="🔄 Convert Textures", 
                                        command=self.start_conversion)
        self.convert_button.pack(side=LEFT, padx=5)
        
        self.restore_button = ttk.Button(buttons_frame, text="🔙 Restore PNGs", 
                                        command=self.restore_pngs)
        self.restore_button.pack(side=LEFT, padx=5)
        
        self.cancel_button = ttk.Button(buttons_frame, text="❌ Cancel", 
                                       command=self.cancel_operation, state=DISABLED)
        self.cancel_button.pack(side=LEFT, padx=5)
        
        # Progress frame - explicitly use TLabelframe style
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="15", style="TLabelframe")
        progress_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10,5))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=5)
        
        # Status and ETA labels
        status_frame = ttk.Frame(progress_frame, style="TFrame")
        status_frame.grid(row=1, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, sticky=W)
        
        self.eta_label = ttk.Label(status_frame, textvariable=self.eta_var)
        self.eta_label.grid(row=0, column=1, sticky=E)
        
        # Log area - explicitly use TLabelframe style
        log_frame = ttk.LabelFrame(main_frame, text="Conversion Log", padding="15", style="TLabelframe")
        log_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, 
                                                 bg=self.log_bg_color, fg=self.win_fg_color,
                                                 insertbackground=self.win_fg_color,
                                                 relief='flat',
                                                 borderwidth=0,
                                                 font=self.log_text_font,
                                                 selectbackground=self.accent_color,
                                                 selectforeground=self.accent_fg_color)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        # Configure text tags for colored output
        self.log_text.tag_configure("info", foreground="#87ceeb")
        self.log_text.tag_configure("success", foreground="#90ee90")
        self.log_text.tag_configure("warning", foreground="#ffa500")
        self.log_text.tag_configure("error", foreground="#ff6b6b")
        
        # Tip label REMOVED
        # tip_label = ttk.Label(main_frame, 
        #                      text="💡 Tip: You can minimize this window and continue other work during conversion", 
        #                      font=("Segoe UI Variable Text", 9))
        # tip_label.grid(row=8, column=0, columnspan=3, pady=(10,5))
    
    def _reset_ui_state(self):
        """Helper to reset UI elements to their default state (must be called from main thread)."""
        texconv_ok = bool(self.texconv_path_var.get() and os.path.exists(self.texconv_path_var.get()))

        if texconv_ok:
            self.convert_button.config(state=NORMAL)
            if hasattr(self, 'status_var'): 
                 self.status_var.set("Ready")
        else:
            self.convert_button.config(state=DISABLED)
            if hasattr(self, 'status_var'): 
                 self.status_var.set("texconv.exe not found. Conversion disabled.")
        
        self.restore_button.config(state=NORMAL) # Restore doesn't depend on texconv
        self.cancel_button.config(state=DISABLED)
        self.root.title("RimConvert") # UPDATED reset window title
        self.processing = False # Ensure processing flag is reset

    def load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                # If loading fails, return an empty dict
                self.log_message(f"Error loading config file {CONFIG_FILE}. Using defaults.", "warning")
                return {}
        return {} # If file doesn't exist, return an empty dict

    def save_config(self):
        """Save configuration to JSON file."""
        config = {
            'mods_path': self.mods_path_var.get(),
            'enable_upscaling': self.enable_upscaling_var.get(),
            'enable_gpu': self.enable_gpu_var.get(),
            # 'generate_mipmaps': self.generate_mipmaps_var.get(), # Option removed from UI and config
            # 'compression_format': self.compression_var.get(),   # Option removed from UI and config
            'window_geometry': self.root.geometry() if hasattr(self.root, 'geometry') else None 
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log_message(f"Could not save config: {e}", "warning")

    def load_settings(self):
        """Load settings from config."""
        self.mods_path_var.set(self.config.get('mods_path', r"C:\\Steam\\steamapps\\common\\RimWorld\\Mods"))
        
        detected_texconv_path = get_texconv_path()
        self.texconv_path_var.set(detected_texconv_path)
        if not detected_texconv_path:
            self.log_message("texconv.exe not found in the 'compressors' subdirectory next to the application. Conversion features will be disabled.", "error")
        else:
            self.log_message(f"Found texconv.exe at: {detected_texconv_path}", "info")
            
        self.enable_upscaling_var.set(self.config.get('enable_upscaling', True))
        self.enable_gpu_var.set(self.config.get('enable_gpu', True))
        
        # Force mipmaps and compression format, ignore any saved config values for these
        self.generate_mipmaps_var.set(True)     # Forced True
        self.compression_var.set("BC7_UNORM")   # Forced BC7_UNORM
    
    def browse_mods_folder(self):
        """Browse for RimWorld mods folder."""
        folder = filedialog.askdirectory(title="Select RimWorld Mods Folder",
                                        initialdir=self.mods_path_var.get())
        if folder:
            self.mods_path_var.set(folder)
    
    def log_message(self, message, level="info"):
        """Add message to log with timestamp and coloring."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        # Thread-safe GUI update
        self.root.after(0, self._update_log, formatted_message, level)
    
    def _update_log(self, message, level):
        """Update log text widget (must be called from main thread)."""
        self.log_text.insert(END, message, level)
        self.log_text.see(END)
        self.root.update_idletasks()
    
    def update_progress(self, value, status="", eta=""):
        """Update progress bar and status (thread-safe)."""
        self.root.after(0, self._update_progress_gui, value, status, eta)
    
    def _update_progress_gui(self, value, status, eta):
        """Update progress GUI elements (must be called from main thread)."""
        self.progress_var.set(value)
        if status:
            self.status_var.set(status)
        if eta:
            self.eta_var.set(eta)
        
        # Update window title with progress
        if self.processing and value > 0:
            self.root.title(f"RimConvert - {value}% Complete") # UPDATED Title during processing
        elif not self.processing:
            self.root.title("RimConvert") # UPDATED default/idle window title
        
        self.root.update_idletasks()
          
    def validate_settings(self):
        """Validate current settings."""
        if not os.path.exists(self.mods_path_var.get()):
            messagebox.showerror("Error", "RimWorld mods folder does not exist!")
            return False
        
        # Validate auto-detected texconv.exe path
        current_texconv_path = self.texconv_path_var.get()
        if not current_texconv_path or not os.path.exists(current_texconv_path):
            # Attempt to re-detect, in case it was placed there after app start (unlikely for exe)
            # but more for robustness during script development.
            # For a running .exe, this re-check might not be as useful if it failed initially.
            refreshed_texconv_path = get_texconv_path()
            if refreshed_texconv_path and os.path.exists(refreshed_texconv_path):
                self.texconv_path_var.set(refreshed_texconv_path)
                self.log_message(f"Re-detected texconv.exe at: {refreshed_texconv_path}", "info")
                # Update UI state if it was previously disabled
                self._reset_ui_state() # This will re-evaluate button states
            else:
                messagebox.showerror("Error", "texconv.exe was not found in the 'compressors' subdirectory next to the application. Please ensure it is correctly placed and restart the application if necessary.")
                return False
        
        return True
    
    def _get_image_info_gui(self, image_path):
        """GUI version of get_image_info, logs errors via self.log_message."""
        if not PILLOW_AVAILABLE or PILImage is None:
            self.log_message(f"Pillow not available, cannot get image info for {os.path.basename(image_path)}", "error")
            return None
        try:
            with PILImage.open(image_path) as img:                return {
                    'width': img.width,
                    'height': img.height,
                    'mode': img.mode,
                    'has_alpha': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
        except Exception as e:
            self.log_message(f"Could not read image info for {os.path.basename(image_path)}: {e}", "warning")
            return None

    def _upscale_image_gui(self, image_path, output_path, target_width, target_height):
        """GUI version of upscale_image, logs errors via self.log_message."""
        if not PILLOW_AVAILABLE or PILImage is None:
            self.log_message(f"Pillow not available, cannot upscale {os.path.basename(image_path)}", "error")
            return False
        try:
            with PILImage.open(image_path) as img:
                upscaled_img = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)
                upscaled_img.save(output_path, 'PNG', optimize=True)
                return True
        except Exception as e:
            self.log_message(f"Failed to upscale image {os.path.basename(image_path)}: {e}", "error")
            return False

    def _convert_png_to_dds_gui(self, png_path_to_convert, dds_output_path, has_alpha, use_gpu, texconv_path, compression_format, generate_mipmaps):
        """
        GUI version of convert_png_to_dds, logs messages via self.log_message.
        
        Key parameters based on RimPy's successful approach:
        - BC7_UNORM for best quality with alpha support
        - Generate mipmaps for performance
        - Proper handling of alpha channels
        - FLIPPED INPUT: Pre-flip PNG before conversion to correct in-game orientation
        - Optional GPU acceleration.
        """
        temp_flipped_path = None
        input_path = png_path_to_convert # Default to original path

        try:
            # Pre-flip the PNG to correct in-game orientation issues
            if PILImage is not None: # Check if PILImage module is loaded
                temp_flipped_path = os.path.splitext(png_path_to_convert)[0] + f"_temp_flipped_gui_{int(time.time()*1000)}.png"
                
                try:
                    with PILImage.open(png_path_to_convert) as img:
                        flipped_img = img.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)
                        flipped_img.save(temp_flipped_path)
                        
                    input_path = temp_flipped_path # Use the flipped image for conversion
                    self.log_message(f"Pre-flipped texture for correct orientation: {os.path.basename(png_path_to_convert)}", "info")
                    
                except Exception as e:
                    self.log_message(f"Failed to flip texture {os.path.basename(png_path_to_convert)}: {e}", "warning")
                    self.log_message("Proceeding with original texture (may appear upside down in-game)", "warning")
                    # input_path remains png_path_to_convert
            else:
                self.log_message("Pillow (PIL) module not loaded. Cannot pre-flip. Textures might appear upside down.", "warning")
                # input_path remains png_path_to_convert

            base_cmd = [
                texconv_path,
                "-f", compression_format,
                "-o", os.path.dirname(dds_output_path),
                "-y",
                "-ft", "dds"
            ]
            if generate_mipmaps:
                base_cmd.extend(["-m", "0"])
            if has_alpha:
                base_cmd.append("-pmalpha")

            cmd_to_run = list(base_cmd) # Make a copy
            if use_gpu:
                cmd_to_run.extend(["-gpu", "0"])
            cmd_to_run.append(input_path)

            # self.log_message(f"Converting ({'GPU' if use_gpu else 'CPU'}): {os.path.basename(png_path_to_convert)} -> {os.path.basename(dds_output_path)}", "info")
            
            result = subprocess.run(
                cmd_to_run, 
                capture_output=True, 
                text=True, 
                timeout=120, # Increased timeout for potentially slower individual conversions
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                # texconv creates files with original name + .dds, need to rename if output path is different
                # This logic might be simplified if dds_output_path is always derived correctly.
                generated_dds_by_texconv = os.path.join(os.path.dirname(dds_output_path),
                                           os.path.splitext(os.path.basename(input_path))[0] + ".dds")
                
                if generated_dds_by_texconv != dds_output_path and os.path.exists(generated_dds_by_texconv):
                    shutil.move(generated_dds_by_texconv, dds_output_path)
                elif not os.path.exists(dds_output_path):
                    # This case implies texconv might have failed silently or output name mismatch
                    self.log_message(f"texconv reported success for {os.path.basename(png_path_to_convert)} but output DDS {os.path.basename(dds_output_path)} not found. Generated: {generated_dds_by_texconv}", "error")
                    # self.log_message(f"texconv stdout: {result.stdout}", "error")
                    # self.log_message(f"texconv stderr: {result.stderr}", "error")
                    return False
                return True
            else:
                self.log_message(f"texconv failed for {os.path.basename(png_path_to_convert)} ({'GPU' if use_gpu else 'CPU'} attempt).", "error")
                # self.log_message(f"Command: {' '.join(cmd_to_run)}", "error") # Can be too verbose
                # self.log_message(f"Error output: {result.stderr}", "error")
                return False
        except subprocess.TimeoutExpired:
            self.log_message(f"Conversion timeout for {os.path.basename(png_path_to_convert)} ({'GPU' if use_gpu else 'CPU'} attempt).", "error")
            return False
        except Exception as e:
            self.log_message(f"Conversion failed for {os.path.basename(png_path_to_convert)}: {e}", "error")
            return False
        finally:
            # Clean up temporary flipped file
            if temp_flipped_path and os.path.exists(temp_flipped_path):
                try:
                    os.remove(temp_flipped_path)
                except Exception as e_cleanup:
                    self.log_message(f"Could not remove temporary flipped file {os.path.basename(temp_flipped_path)}: {e_cleanup}", "warning")

    def _process_single_file_gui_task(self, png_path, texconv_path, compression_format, 
                                    enable_upscaling, generate_mipmaps, enable_gpu_preference, 
                                    target_upscale_min_dim=256): # Added target_upscale_min_dim
        task_stats = {'status': 'unknown', 'upscaled': False, 'original_path': png_path}
        temp_path = None # Initialize temp_path for robustness in finally block
        try:
            dds_path = Path(png_path).with_suffix('.dds')

            if self.cancel_requested:
                task_stats['status'] = 'cancelled'
                return task_stats

            # DDS Skipping Logic
            if dds_path.exists():
                try:
                    png_mtime = os.path.getmtime(png_path)
                    dds_mtime = os.path.getmtime(dds_path)
                    if dds_mtime > png_mtime:
                        self.log_message(f"Skipping (DDS newer): {os.path.basename(png_path)}", "info")
                        task_stats['status'] = 'skipped_newer'
                        return task_stats
                except FileNotFoundError:
                    self.log_message(f"File not found during mtime check for {os.path.basename(png_path)}. Processing.", "warning")
                except Exception as e_mtime:
                    self.log_message(f"Error checking mtime for {os.path.basename(png_path)}: {e_mtime}. Processing.", "warning")
            
            img_info = self._get_image_info_gui(png_path)
            if not img_info:
                task_stats['status'] = 'error_img_info'
                return task_stats

            current_path_for_conversion = png_path
            
            if enable_upscaling and (img_info['width'] < target_upscale_min_dim or img_info['height'] < target_upscale_min_dim):
                if self.cancel_requested: return {**task_stats, 'status': 'cancelled'}
                
                # Upscale by 2x
                new_width = img_info['width'] * 2
                new_height = img_info['height'] * 2
                new_width = max(1, new_width) # Ensure dimensions are at least 1
                new_height = max(1, new_height)

                # Using a more unique temp name
                temp_filename = f"temp_gui_upscaled_{os.path.splitext(os.path.basename(png_path))[0]}_{int(time.time()*1000)}_{os.urandom(4).hex()}.png"
                temp_path = os.path.join(os.path.dirname(png_path), temp_filename)

                self.log_message(f"Upscaling {os.path.basename(png_path)} from {img_info['width']}x{img_info['height']} to {new_width}x{new_height}", "info")
                if self._upscale_image_gui(png_path, temp_path, new_width, new_height):
                    current_path_for_conversion = temp_path
                    task_stats['upscaled'] = True
                else:
                    task_stats['status'] = 'error_upscale'
                    # Error already logged by _upscale_image_gui
                    return task_stats
            
            if self.cancel_requested: return {**task_stats, 'status': 'cancelled'}

            conversion_successful = False
            # Attempt GPU conversion if preferred
            if enable_gpu_preference:
                self.log_message(f"Converting (GPU): {os.path.basename(current_path_for_conversion)} -> {dds_path.name}", "info")
                if self._convert_png_to_dds_gui(current_path_for_conversion, str(dds_path), img_info['has_alpha'], True, texconv_path, compression_format, generate_mipmaps):
                    conversion_successful = True
                    task_stats['status'] = 'gpu_converted'
                else:
                    self.log_message(f"GPU conversion failed for {os.path.basename(current_path_for_conversion)}. Trying CPU.", "warning")
            
            # If GPU not preferred, or if GPU failed, try CPU
            if not conversion_successful:
                if self.cancel_requested: return {**task_stats, 'status': 'cancelled'}
                self.log_message(f"Converting (CPU): {os.path.basename(current_path_for_conversion)} -> {dds_path.name}", "info")
                if self._convert_png_to_dds_gui(current_path_for_conversion, str(dds_path), img_info['has_alpha'], False, texconv_path, compression_format, generate_mipmaps):
                    conversion_successful = True
                    task_stats['status'] = 'cpu_converted'
                else:
                    # Error already logged by _convert_png_to_dds_gui
                    task_stats['status'] = 'error_cpu_conversion'
            
            if conversion_successful and task_stats['status'] not in ['gpu_converted', 'cpu_converted']:
                 # Should not happen if logic is correct, but as a fallback
                 task_stats['status'] = 'error_unknown_conversion_state'
            elif not conversion_successful and task_stats['status'] == 'unknown':
                 task_stats['status'] = 'error_conversion_failed_completely'

            return task_stats

        except Exception as e_task:
            self.log_message(f"Unexpected error processing {os.path.basename(png_path)} in task: {e_task}", "error")
            task_stats['status'] = 'error_unexpected'
            return task_stats
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e_remove_temp:
                    self.log_message(f"Could not remove temp upscaled file {os.path.basename(temp_path)}: {e_remove_temp}", "warning")

    def conversion_worker(self):
        """Background worker for texture conversion, now using ThreadPoolExecutor."""
        progress_percent = 0 # Initialize progress_percent
        final_stats = {'success': 0, 'fail': 0, 'skipped': 0, 'upscaled': 0, 'total_processed_in_loop': 0} # Initialize final_stats
        self.last_progress_percent = 0 # Track last progress percent for final update
        worker_start_time = time.time() # Track overall worker start time
        try:
            self.log_message("🚀 Starting texture conversion (GUI Parallel)...")
            mods_path_str = self.mods_path_var.get()
            texconv_path_str = self.texconv_path_var.get()
            
            # Force compression format and mipmap generation for GUI operations
            compression_format_str = "BC7_UNORM" 
            generate_mipmaps_bool = True
            
            enable_upscaling_bool = self.enable_upscaling_var.get()
            enable_gpu_preference_bool = self.enable_gpu_var.get()

            if not PILLOW_AVAILABLE:
                # This check should ideally be before starting the worker or disable button
                # but for now, ensure it logs and exits gracefully if worker somehow starts.
                self.log_message("Pillow library not available. Conversion cannot proceed.", "error")
                # Since this is a worker thread, messagebox might not be ideal here.
                # Consider disabling button if Pillow not found at startup.
                return
            
            # Find all PNG files
            png_files = []
            for root, _, files in os.walk(mods_path_str):
                for file in files:
                    if file.lower().endswith('.png'):
                        png_files.append(os.path.join(root, file))
            
            total_files = len(png_files)
            # Storing total_files in final_stats for summary
            final_stats['total_files_discovered'] = total_files

            if not png_files:
                self.log_message("No PNG files found in the specified mods folder.", "info")
                self.update_progress(100, "No PNG files found.", "") 
                # No return here; let it fall through to the finally block to reset UI
            else:
                self.log_message(f"Found {total_files} PNG files to process.")
                self.update_progress(0, f"Preparing to process {total_files} files...", "ETA: Calculating...")

                loop_processed_count = 0
                # loop_success_count, fail_count etc. are accumulated in final_stats
                loop_start_time = time.time()

                num_workers = min(8, os.cpu_count() + 4 if os.cpu_count() else 8) 

                with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                    future_to_png = {executor.submit(self._process_single_file_gui_task, 
                                                     png_file, 
                                                     texconv_path_str, 
                                                     compression_format_str, 
                                                     enable_upscaling_bool, 
                                                     generate_mipmaps_bool, 
                                                     enable_gpu_preference_bool):
                                     png_file for png_file in png_files}
                    
                    for future in concurrent.futures.as_completed(future_to_png):
                        if self.cancel_requested:
                            for f_pending in future_to_png:
                                if not f_pending.done():
                                    f_pending.cancel()
                            self.log_message("Conversion cancellation initiated by user.", "warning")
                            break 
                        
                        png_file_path = future_to_png[future]
                        try:
                            result_stats = future.result() 
                            loop_processed_count += 1
                            final_stats['total_processed_in_loop'] += 1
                            
                            if result_stats['status'] in ['gpu_converted', 'cpu_converted']:
                                final_stats['success'] += 1
                                if result_stats['upscaled']:
                                    final_stats['upscaled'] += 1
                            elif result_stats['status'] == 'skipped_newer':
                                final_stats['skipped'] += 1
                            elif result_stats['status'] == 'cancelled':
                                final_stats['fail'] +=1 
                            else: 
                                final_stats['fail'] += 1

                        except concurrent.futures.CancelledError:
                            self.log_message(f"Task for {os.path.basename(png_file_path)} was cancelled during execution.", "info")
                            final_stats['fail'] += 1 
                        except Exception as exc:
                            self.log_message(f"Error processing {os.path.basename(png_file_path)} in worker future: {exc}", "error")
                            final_stats['fail'] += 1
                        
                        current_progress_percent = int((loop_processed_count / total_files) * 100) if total_files > 0 else 0
                        self.last_progress_percent = current_progress_percent
                        
                        elapsed_time = time.time() - loop_start_time
                        eta_str = ""
                        if loop_processed_count > 0 and elapsed_time > 0:
                            time_per_file = elapsed_time / loop_processed_count
                            remaining_files = total_files - loop_processed_count
                            eta_seconds = remaining_files * time_per_file
                            eta_str = f"ETA: {int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                        
                        status_msg = f"Processed: {loop_processed_count}/{total_files} (S: {final_stats['success']}, F: {final_stats['fail']}, Sk: {final_stats['skipped']}, Up: {final_stats['upscaled']})"
                        self.update_progress(current_progress_percent, status_msg, eta_str)
                # End of 'with executor' and 'for future' loop

            # After processing all files or if no files were found (and not returned early)
            if not self.cancel_requested and total_files > 0 : # Only log summary if files were processed
                total_conversion_time = time.time() - worker_start_time
                summary_msg = (f"✅ Conversion complete! "
                               f"Files: {total_files}, Success: {final_stats['success']}, "
                               f"Failed: {final_stats['fail']}, Skipped: {final_stats['skipped']}, "
                               f"Upscaled: {final_stats['upscaled']}. "
                               f"Time: {total_conversion_time:.2f}s.")
                self.log_message(summary_msg, "info")
                # Ensure progress bar is at 100% if all tasks completed without cancellation
                if final_stats['total_processed_in_loop'] == total_files:
                     self.update_progress(100, "Conversion finished.", summary_msg)
                else: # Should not happen if not cancelled, but as a fallback
                     self.update_progress(self.last_progress_percent, "Conversion ended (some files may not have processed).", summary_msg)

            elif self.cancel_requested:
                processed_before_stop = final_stats['total_processed_in_loop']
                self.log_message(f"🛑 Conversion process stopped by user. Processed {processed_before_stop}/{total_files if total_files else 'N/A'} before stopping.", "warning")
                self.update_progress(self.last_progress_percent, f"Cancelled. Processed {processed_before_stop}/{total_files if total_files else 'N/A'}.", "Stopped.")
            # If total_files was 0, the "No PNG files found" message is already on progress.

        except Exception as e_worker:
            self.log_message(f"💥 Critical error in conversion worker: {e_worker}", "error")
            import traceback
            self.log_message(traceback.format_exc(), "debug")
            self.update_progress(self.last_progress_percent, "Error during conversion.", "Check logs.")
        finally:
            self.convert_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
            self.log_message("ℹ️ Conversion worker finished and UI reset.", "info")

    def start_conversion(self):
        """Start texture conversion in background thread."""
        if not self.validate_settings():
            return
        
        if not PILLOW_AVAILABLE:
            messagebox.showerror("Error", "Pillow (PIL) library is not installed or failed to load. Please install it: pip install Pillow. Upscaling and pre-flipping will not work.")
            # Decide if you want to allow conversion at all without Pillow, or just return.
            # For now, we'll show the error and let the user decide if they see the log messages about it.
            # The worker itself also has a check.
            # return # Uncomment to prevent conversion if Pillow is missing

        # Confirm operation
        result = messagebox.askyesno(
            "Confirm Conversion",
            "This will create DDS files alongside your PNG files in the original mod folders.\n\n"
            "Original PNG files will NOT be modified or renamed.\n"
            "This allows the game to fall back to PNGs if needed.\n\n"
            "Continue with conversion?"
        )
        
        if not result:
            self.log_message("Conversion cancelled by user before starting.", "info")
            return
        
        # Save current settings
        self.save_config()
        
        # Update UI state
        self.processing = True
        self.cancel_requested = False
        self.convert_button.config(state=DISABLED)
        self.restore_button.config(state=DISABLED)
        self.cancel_button.config(state=NORMAL)
        
        # Clear log
        self.log_text.delete(1.0, END)
        
        # Start conversion thread
        # Pass necessary parameters to the worker method if it's not a class method or if it needs them directly
        # In this case, conversion_worker is a method and can access self
        threading.Thread(target=self.conversion_worker, daemon=True).start()
    
    def restore_pngs(self):
        """Start PNG restoration (DDS deletion) in background thread."""
        if not self.validate_settings(): # Basic validation for paths
            return

        result = messagebox.askyesno(
            "Confirm PNG Restoration",
            "This will scan your RimWorld mods folder and DELETE .dds files "
            "IF a corresponding .png file exists in the same directory.\\n\\n"
            "This effectively reverts textures to their original PNG versions.\\n\\n"
            "This operation cannot be easily undone for the deleted DDS files.\\n\\n"
            "Continue with PNG restoration?"
        )
        if not result:
            return

        self.save_config()

        self.processing = True
        self.cancel_requested = False
        self.convert_button.config(state=DISABLED)
        self.restore_button.config(state=DISABLED)
        self.cancel_button.config(state=NORMAL)
        
        self.log_text.delete(1.0, END)
        
        threading.Thread(target=self.restore_worker, daemon=True).start()

    def restore_worker(self):
        """Background worker for PNG restoration (DDS deletion)."""
        try:
            self.log_message("🔙 Starting PNG restoration (deleting DDS files)...", "info")
            mods_path = self.mods_path_var.get()
            
            # Define skip_folders, similar to conversion_worker
            # Ideally, this should be a class or module-level constant
            skip_folders_config = { 
                'About', 'Assemblies', 'Defs', 'Languages', 'Patches', 
                'Sounds', 'Source', '.git', '.svn', '__pycache__',
                'Common', 'v1.0', 'v1.1', 'v1.2', 'v1.3', 'v1.4', 'v1.5' # Common game version folders
            }

            self.log_message(f"Scanning for DDS files in: {mods_path}", "info")

            dds_files_to_check = []
            self.log_message("Phase 1: Scanning all directories for DDS files...", "info")
            # Scan for DDS files
            for mod_folder_name in os.listdir(mods_path):
                if self.cancel_requested: break
                current_mod_path = os.path.join(mods_path, mod_folder_name)
                if not os.path.isdir(current_mod_path) or mod_folder_name in skip_folders_config:
                    continue
                
                for root, dirs, files in os.walk(current_mod_path):
                    if self.cancel_requested: break
                    dirs[:] = [d for d in dirs if d not in skip_folders_config] # Prune recursion
                    for file_name in files:
                        if file_name.lower().endswith('.dds'):
                            dds_files_to_check.append(os.path.join(root, file_name))
                if self.cancel_requested: break
            
            total_files = len(dds_files_to_check)
            if self.cancel_requested:
                 self.log_message("Scan cancelled by user during file collection.", "warning")
                 self.update_progress(0, "Scan Cancelled", "")
                 return


            if total_files == 0:
                self.log_message("No DDS files found to process for restoration.", "info")
                self.update_progress(100, "No DDS files found.", "Done")
                return

            self.log_message(f"Found {total_files} DDS files. Phase 2: Processing files...", "info")

            deleted_count = 0
            skipped_count = 0
            errors = 0
            start_time = time.time()

            for i, dds_path in enumerate(dds_files_to_check):
                if self.cancel_requested:
                    self.log_message("Restoration cancelled by user during processing.", "warning")
                    break

                progress = int(((i + 1) / total_files) * 100) # i+1 for current item
                elapsed_time = time.time() - start_time
                eta_str = "Calculating..."
                if i > 0: # Avoid division by zero for the first item
                    time_per_file = elapsed_time / (i + 1)
                    eta_seconds = time_per_file * (total_files - (i + 1))
                    eta_str = f"ETA: {int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                
                self.update_progress(progress, f"Processing {i+1}/{total_files}: {os.path.basename(dds_path)}", eta_str)

                png_path = os.path.splitext(dds_path)[0] + '.png'

                try:
                    if os.path.exists(png_path):
                        os.remove(dds_path)
                        deleted_count += 1
                        self.log_message(f"Deleted: {os.path.relpath(dds_path, mods_path)} (PNG companion exists)", "success")
                    else:
                        skipped_count += 1
                        # self.log_message(f"Skipped: {os.path.relpath(dds_path, mods_path)} (No PNG companion found)", "info") # reduce log spam
                except Exception as e:
                    errors += 1
                    self.log_message(f"Error deleting {os.path.relpath(dds_path, mods_path)}: {e}", "error")
            
            final_elapsed_time = time.time() - start_time
            if self.cancel_requested:
                self.log_message("Restoration process was cancelled.", "warning")
            else:
                self.log_message("🎉 PNG Restoration Complete!", "success")
            
            self.log_message(f"DDS files deleted: {deleted_count}", "info")
            self.log_message(f"DDS files skipped (no PNG companion): {skipped_count}", "info")
            self.log_message(f"Errors during deletion: {errors}", "error" if errors > 0 else "info")
            self.log_message(f"Total time: {final_elapsed_time:.1f} seconds", "info")
            self.update_progress(100, "Restoration Finished" if not self.cancel_requested else "Restoration Cancelled", f"{final_elapsed_time:.1f}s")

        except Exception as e:
            self.log_message(f"An unexpected error occurred during restoration: {e}", "error")
            self.update_progress(100, "Error during restoration", "")
        finally:
            self.processing = False # Ensure processing flag is reset
            self.root.after(0, self._reset_ui_state) # UI updates on main thread

    def cancel_operation(self):
        """Request cancellation of the current operation."""
        if self.processing:
            self.cancel_requested = True
            self.log_message("Cancel request received. Attempting to stop...", "warning")
            self.status_var.set("Cancelling...")
            # Disable cancel button to prevent multiple clicks, re-enabled when process fully stops
            self.cancel_button.config(state=DISABLED) 

def main():
    """Main function to run the GUI."""
    # Check if Pillow is available
    if not PILLOW_AVAILABLE:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "Pillow library is required but not installed.\n\n"
            "Please install it using:\npip install Pillow\n\n"
            "Then restart this application."
        )
        return
    
    # Create and run GUI
    root = Tk()
    app = RimWorldOptimizerGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
