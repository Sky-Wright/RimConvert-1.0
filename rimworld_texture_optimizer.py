#!/usr/bin/env python3
"""
RimWorld Texture Optimizer v2.0
================================

A comprehensive texture conversion tool for RimWorld mods using RimPy's proven approach.
Uses Microsoft's texconv.exe with BC7 compression for optimal results.

Key improvements from v1.0:
- Uses texconv.exe instead of nvcompress (matches RimPy's approach)
- BC7 compression with proper alpha channel handling
- No longer renames original PNGs (allows game fallback)
- Proper texture flipping to match RimWorld's expectations
- Enhanced virtual environment management
- GUI and CLI modes available
- Parallel processing for faster conversions

Author: AI Assistant
Date: June 7, 2025
"""

import os
import sys
import subprocess
import shutil
import argparse
import json
import time
from pathlib import Path
from datetime import datetime
import concurrent.futures # Added for ThreadPoolExecutor

try:
    from PIL import Image as PILImage # Import PIL.Image as PILImage
    PILLOW_AVAILABLE = True
except ImportError:
    PILImage = None # If import fails, PILImage is None
    PILLOW_AVAILABLE = False

# ============================================================================
# CONFIGURATION VARIABLES
# ============================================================================

# Default paths - automatically detect relative to script location
def get_default_paths():
    """Get default paths relative to the script location."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return {
        'mods': os.path.join(script_dir, "LiveTest", "Mods"),
        'texconv': os.path.join(script_dir, "compressors", "texconv.exe"),
        'bc7enc': os.path.join(script_dir, "compressors", "bc7enc.exe")
    }

defaults = get_default_paths()
RIMWORLD_MODS_PATH = defaults['mods']
TEXCONV_PATH = defaults['texconv']
BC7ENC_PATH = defaults['bc7enc']

# Conversion settings
MIN_UPSCALING_DIM = 256  # Minimum dimension for upscaling (either width or height)
DEFAULT_COMPRESSION_FORMAT = "BC7_UNORM"  # BC7 for best quality with alpha support
ALTERNATIVE_FORMAT = "BC3_UNORM"  # DXT5 fallback for compatibility
GENERATE_MIPMAPS = True  # Generate mipmaps for better performance
ENABLE_UPSCALING = True  # Enable AI upscaling for small textures
ENABLE_GPU = True # Added for GPU acceleration

# Skip these folders during processing
SKIP_FOLDERS = {
    'About', 'Assemblies', 'Defs', 'Languages', 'Patches', 
    'Sounds', 'Source', '.git', '.svn', '__pycache__',
    'Common', 'v1.4', 'v1.5'  # Version-specific folders
}

# Skip these file patterns
SKIP_PATTERNS = {
    '_preview.png', '_thumb.png', 'preview.png', 'thumbnail.png',
    'icon.png', 'logo.png'
}

# Configuration file for persistent settings
CONFIG_FILE = "rimworld_optimizer_config.json"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_banner():
    """Print the application banner."""
    print("=" * 70)
    print("🚀 RimWorld Texture Optimizer v2.0 - RimPy Edition")
    print("   Using Microsoft texconv.exe with BC7 compression")
    print("=" * 70)
    print()

def print_error(message):
    """Print an error message."""
    print(f"❌ ERROR: {message}")

def print_warning(message):
    """Print a warning message."""
    print(f"⚠️  WARNING: {message}")

def print_success(message):
    """Print a success message."""
    print(f"✅ {message}")

def print_info(message):
    """Print an info message."""
    print(f"ℹ️  {message}")

def load_config():
    """Load configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print_warning(f"Could not load config file: {e}")
    return {}

def save_config(config):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print_warning(f"Could not save config file: {e}")

def check_virtual_environment():
    """Check if we're running in a virtual environment with required packages."""
    print_info("Checking virtual environment and dependencies...")
    
    # Check if we're in a virtual environment
    in_venv = sys.prefix != sys.base_prefix
    
    # Check if required packages are available
    missing_packages = []
    
    if not PILLOW_AVAILABLE:
        missing_packages.append("Pillow")
    
    try:
        import tkinter
    except ImportError:
        missing_packages.append("tkinter (usually comes with Python)")
    
    if not in_venv or missing_packages:
        print_error("Virtual environment setup required!")
        print()
        print("🔧 SETUP INSTRUCTIONS:")
        print("=" * 50)
        print("1. Create virtual environment:")
        print("   python -m venv .venv")
        print()
        print("2. Activate virtual environment:")
        print("   Windows PowerShell: .venv\\Scripts\\Activate.ps1")
        print("   Windows CMD:        .venv\\Scripts\\activate.bat")
        print("   Linux/macOS:        source .venv/bin/activate")
        print()
        print("3. Install required packages:")
        print("   pip install Pillow")
        print()
        print("4. Re-run this script from the activated virtual environment")
        print("=" * 50)
        return False
    
    print_success("Virtual environment and dependencies OK!")
    return True

def check_tools():
    """Check if required external tools are available."""
    print_info("Checking external tools...")
    
    # Check texconv.exe
    if not os.path.exists(TEXCONV_PATH):
        print_error(f"texconv.exe not found at: {TEXCONV_PATH}")
        print("Please ensure RimPy's compressor tools are available.")
        return False
    
    # Test texconv.exe
    try:
        result = subprocess.run([TEXCONV_PATH], capture_output=True, text=True, timeout=10)
        print_success("texconv.exe is available and working")
    except Exception as e:
        print_error(f"texconv.exe test failed: {e}")
        return False
    
    # Check bc7enc.exe (optional, for advanced compression)
    if os.path.exists(BC7ENC_PATH):
        print_success("bc7enc.exe is available (optional tool)")
    else:
        print_warning("bc7enc.exe not found (optional tool)")
    
    return True

def should_skip_file(file_path):
    """Check if a file should be skipped based on patterns."""
    filename = os.path.basename(file_path).lower()
    return any(pattern in filename for pattern in SKIP_PATTERNS)

def should_skip_folder(folder_path):
    """Check if a folder should be skipped."""
    folder_name = os.path.basename(folder_path)
    return folder_name in SKIP_FOLDERS

def get_image_info(image_path):
    """Get image dimensions and format info."""
    if not PILLOW_AVAILABLE or PILImage is None: # Check both
        print_warning(f"Pillow not available, cannot get image info for {image_path}")
        return None
    try:
        with PILImage.open(image_path) as img: # Use PILImage directly
            return {
                'width': img.width,
                'height': img.height,
                'mode': img.mode,
                'has_alpha': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
            }
    except Exception as e:
        print_warning(f"Could not read image info for {image_path}: {e}")
        return None

def needs_upscaling(width, height):
    """Determine if image needs upscaling. Upscales if either dimension is less than MIN_UPSCALING_DIM."""
    return ENABLE_UPSCALING and (width < MIN_UPSCALING_DIM or height < MIN_UPSCALING_DIM)

def upscale_image(image_path, output_path, target_width, target_height):
    """Upscale image using Pillow's high-quality resampling."""
    if not PILLOW_AVAILABLE or PILImage is None: # Check both
        print_error(f"Pillow not available, cannot upscale {image_path}")
        return False
    try:
        with PILImage.open(image_path) as img: # Use PILImage directly
            # Use LANCZOS for high-quality upscaling
            upscaled = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS) # Use PILImage directly
            upscaled.save(output_path, 'PNG', optimize=True)
            return True
    except Exception as e:
        print_error(f"Failed to upscale image {image_path}: {e}")
        return False

def convert_png_to_dds(png_path, dds_path, has_alpha=True, use_gpu=False):
    """
    Convert PNG to DDS using texconv.exe (RimPy's approach).
    
    Key parameters based on RimPy's successful approach:
    - BC7_UNORM for best quality with alpha support
    - Generate mipmaps for performance
    - Proper handling of alpha channels
    - FLIPPED INPUT: Pre-flip PNG before conversion to correct in-game orientation
    - Optional GPU acceleration.
    """
    temp_flipped_path = None
    try:
        # Pre-flip the PNG to correct in-game orientation issues
        # Based on runtime testing, RimWorld displays textures upside down when converted normally
        if PILLOW_AVAILABLE:
            temp_flipped_path = os.path.splitext(png_path)[0] + f"_temp_flipped_{int(time.time()*1000)}.png"
            
            try:
                with PILImage.open(png_path) as img:
                    # Flip vertically to correct in-game orientation
                    flipped_img = img.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)
                    flipped_img.save(temp_flipped_path)
                    
                # Use the flipped image for conversion
                input_path = temp_flipped_path
                print_info(f"Pre-flipped texture for correct orientation: {os.path.basename(png_path)}")
                
            except Exception as e:
                print_warning(f"Failed to flip texture {os.path.basename(png_path)}: {e}")
                print_warning("Proceeding with original texture (may appear upside down in-game)")
                input_path = png_path
        else:
            print_warning("Pillow not available - textures may appear upside down in-game")
            input_path = png_path
        
        # Build texconv command
        cmd = [
            TEXCONV_PATH,
            "-f", DEFAULT_COMPRESSION_FORMAT,  # BC7_UNORM
            "-o", os.path.dirname(dds_path),   # Output directory
            "-y",                              # Overwrite existing files
            "-ft", "dds",                      # Output DDS format
        ]
        
        if GENERATE_MIPMAPS:
            cmd.extend(["-m", "0"])  # Generate all mipmap levels
        
        if has_alpha:
            cmd.append("-pmalpha")  # Convert to premultiplied alpha for better quality

        if use_gpu:
            cmd.extend(["-gpu", "0"]) # Add GPU flag
        
        cmd.append(input_path)
        
        print_info(f"Converting: {os.path.basename(png_path)} -> {os.path.basename(dds_path)}")
        
        # Execute conversion with no visible window
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode == 0:
            # texconv creates files with original name + .dds, need to rename if different
            generated_dds = os.path.join(os.path.dirname(dds_path), 
                                       os.path.splitext(os.path.basename(input_path))[0] + ".dds")
            
            if generated_dds != dds_path and os.path.exists(generated_dds):
                shutil.move(generated_dds, dds_path)
            return True
        else:
            print_error(f"texconv failed for {png_path}")
            print(f"Command: {' '.join(cmd)}")
            print(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print_error(f"Conversion timeout for {png_path}")
        return False
    except Exception as e:
        print_error(f"Conversion failed for {png_path}: {e}")
        return False
    finally:
        # Clean up temporary flipped file
        if temp_flipped_path and os.path.exists(temp_flipped_path):
            try:
                os.remove(temp_flipped_path)
            except Exception as e_cleanup:
                print_warning(f"Could not remove temporary flipped file {temp_flipped_path}: {e_cleanup}")

# ============================================================================
# WORKER FUNCTION FOR PARALLEL PROCESSING
# ============================================================================

def _process_file_task(png_path, enable_gpu_cli_arg):
    """Processes a single PNG file: upscale, convert to DDS (GPU/CPU), skip logic."""
    file_stats = {
        'converted': 0, 'upscaled': 0, 'skipped': 0, 'errors': 0,
        'gpu_conversions': 0, 'cpu_conversions': 0
    }
    temp_path = None  # For temporary upscaled image

    try:
        # Generate DDS path (same location, different extension)
        dds_path = os.path.splitext(png_path)[0] + '.dds'
        
        # Skip if DDS already exists and is newer than PNG
        if os.path.exists(dds_path):
            try:
                png_mtime = os.path.getmtime(png_path)
                dds_mtime = os.path.getmtime(dds_path)
                if dds_mtime > png_mtime:
                    print_info(f"Skipping (DDS newer): {os.path.basename(png_path)}")
                    file_stats['skipped'] = 1
                    return file_stats
            except FileNotFoundError:
                # This can happen if a file is deleted between os.path.exists and os.path.getmtime
                print_warning(f"File not found during mtime check for {png_path} or {dds_path}. Will attempt processing.")
            except Exception as e:
                print_warning(f"Error checking mtime for {png_path} or {dds_path}: {e}. Will attempt processing.")

        # Get image information
        img_info = get_image_info(png_path)
        if not img_info:
            file_stats['errors'] = 1
            return file_stats
        
        current_path = png_path
        
        if ENABLE_UPSCALING and needs_upscaling(img_info['width'], img_info['height']):
            # Calculate new dimensions (2x original size)
            new_width = img_info['width'] * 2
            new_height = img_info['height'] * 2
            
            # Ensure dimensions are at least 1 (though 2x should prevent this unless original was 0)
            new_width = max(1, new_width)
            new_height = max(1, new_height)

            # Create temporary upscaled image path
            # Using a more unique temp name to avoid potential collisions in rapid parallel processing
            temp_filename = f"temp_upscaled_{os.path.splitext(os.path.basename(png_path))[0]}_{int(time.time()*1000)}_{os.urandom(4).hex()}.png"
            temp_path = os.path.join(os.path.dirname(png_path), temp_filename)
            
            print_info(f"Upscaling {os.path.basename(png_path)} from {img_info['width']}x{img_info['height']} to {new_width}x{new_height}")
            
            if upscale_image(png_path, temp_path, new_width, new_height):
                current_path = temp_path
                file_stats['upscaled'] = 1
            else:
                # Upscaling failed, error already printed by upscale_image
                file_stats['errors'] = 1
                return file_stats # Don't proceed if upscaling failed
        
        # Convert to DDS
        conversion_successful = False
        
        if enable_gpu_cli_arg:
            # Try GPU conversion
            if convert_png_to_dds(current_path, dds_path, img_info['has_alpha'], use_gpu=True):
                conversion_successful = True
                file_stats['gpu_conversions'] = 1
            else:
                # GPU conversion failed, texconv.exe already printed error
                print_warning(f"GPU conversion failed for {os.path.basename(current_path)}. Trying CPU.")
        
        if not conversion_successful:
            # Try CPU conversion (either GPU not enabled, or GPU failed)
            if convert_png_to_dds(current_path, dds_path, img_info['has_alpha'], use_gpu=False):
                conversion_successful = True
                file_stats['cpu_conversions'] = 1
            else:
                # CPU conversion also failed, error already printed by convert_png_to_dds
                print_error(f"CPU conversion also failed for {os.path.basename(current_path)}. Skipping this file.")
                file_stats['errors'] = 1
        
        if conversion_successful:
            file_stats['converted'] = 1
            
        return file_stats

    except Exception as e:
        print_error(f"Unexpected error processing {os.path.basename(png_path)}: {e}")
        file_stats['errors'] = 1
        return file_stats
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                # print_info(f"Cleaned up temporary upscaled file: {os.path.basename(temp_path)}") # Too verbose
            except Exception as e_remove:
                print_warning(f"Could not remove temporary file {temp_path}: {e_remove}")

# ============================================================================
# MAIN CONVERSION LOGIC
# ============================================================================

def convert_textures(args):
    """Main texture conversion function."""
    print("🚨 CRITICAL WARNING 🚨")
    print("=" * 50)
    print("This will process textures DIRECTLY in your original mod folders!")
    print("DDS files will be created alongside existing PNG files.")
    print("Original PNG files will NOT be modified or renamed.")
    print("This allows the game to fall back to PNGs if DDS files have issues.")
    print("=" * 50)
    print()
    
    response = input("Press ENTER to continue or Ctrl+C to cancel: ")
    print()
    
    if not os.path.exists(RIMWORLD_MODS_PATH):
        print_error(f"RimWorld mods path not found: {RIMWORLD_MODS_PATH}")
        print("Please update RIMWORLD_MODS_PATH in the script configuration.")
        return
    
    print_info(f"Scanning mods in: {RIMWORLD_MODS_PATH}")
    
    # Statistics
    stats = {
        'mods_processed': 0,
        'files_converted': 0,
        'files_upscaled': 0,
        'files_skipped': 0,
        'errors': 0,
        'gpu_conversions': 0, 
        'cpu_conversions': 0 
    }
    
    start_time = time.time()
    
    # Process each mod folder
    for mod_folder in os.listdir(RIMWORLD_MODS_PATH):
        mod_path = os.path.join(RIMWORLD_MODS_PATH, mod_folder)
        
        if not os.path.isdir(mod_path) or should_skip_folder(mod_path):
            continue
        
        print_info(f"Processing mod: {mod_folder}")
        stats['mods_processed'] += 1
        
        # Find all PNG files in the mod
        png_files_to_process = []
        for root, dirs, files in os.walk(mod_path):
            # Skip certain directories
            dirs[:] = [d for d in dirs if not should_skip_folder(os.path.join(root, d))]
            
            for file in files:
                if file.lower().endswith('.png'):
                    file_path = os.path.join(root, file)
                    if not should_skip_file(file_path):
                        png_files_to_process.append(file_path)
        
        if not png_files_to_process:
            print_info(f"No PNG files to process in mod: {mod_folder}")
            continue

        num_files_in_mod = len(png_files_to_process)
        print_info(f"Found {num_files_in_mod} PNGs in {mod_folder}. Processing in parallel...")

        # Determine number of workers
        num_workers = os.cpu_count() or 1 # Default to 1 if os.cpu_count() is None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_png = {
                executor.submit(_process_file_task, png_file, args.enable_gpu): png_file 
                for png_file in png_files_to_process
            }
            
            processed_count_in_mod = 0
            for future in concurrent.futures.as_completed(future_to_png):
                png_filename_for_log = os.path.basename(future_to_png[future])
                try:
                    result_stats = future.result()
                    # Aggregate stats
                    stats['files_converted'] += result_stats['converted']
                    stats['files_upscaled'] += result_stats['upscaled']
                    stats['files_skipped'] += result_stats['skipped']
                    stats['errors'] += result_stats['errors']
                    stats['gpu_conversions'] += result_stats['gpu_conversions']
                    stats['cpu_conversions'] += result_stats['cpu_conversions']
                except Exception as exc:
                    print_error(f'{png_filename_for_log} generated an unexpected exception in thread: {exc}')
                    stats['errors'] += 1
                
                processed_count_in_mod +=1
                # Simple progress, can be made more sophisticated if needed
                if processed_count_in_mod % 10 == 0 or processed_count_in_mod == num_files_in_mod :
                     print_info(f"Progress for {mod_folder}: {processed_count_in_mod}/{num_files_in_mod} files handled.")


    # Final summary
    end_time = time.time()
    total_time = end_time - start_time
    print()
    print_success("Texture conversion process completed!")
    print("=" * 30 + " SUMMARY " + "=" * 30)
    print(f"Mods processed:         {stats['mods_processed']}")
    print(f"Files converted:        {stats['files_converted']}")
    print(f"  - GPU conversions:    {stats['gpu_conversions']}")
    print(f"  - CPU conversions:    {stats['cpu_conversions']}")
    print(f"Files upscaled:         {stats['files_upscaled']}")
    print(f"Files skipped (DDS newer): {stats['files_skipped']}")
    print(f"Errors encountered:     {stats['errors']}")
    print(f"Total processing time:  {total_time:.2f} seconds")
    print("=" * 70)

def restore_pngs(args):
    """Restore original PNGs by deleting DDS files."""
    print("🚨 CRITICAL WARNING 🚨")
    print("=" * 50)
    print("This will DELETE all DDS files in your mod folders!")
    print("The game will fall back to using the original PNG files.")
    print("This operation cannot be undone!")
    print("=" * 50)
    print()
    
    response = input("Press ENTER to continue or Ctrl+C to cancel: ")
    print()
    
    if not os.path.exists(RIMWORLD_MODS_PATH):
        print_error(f"RimWorld mods path not found: {RIMWORLD_MODS_PATH}")
        return
    
    print_info(f"Scanning for DDS files in: {RIMWORLD_MODS_PATH}")
    
    deleted_count = 0
    
    # Process each mod folder
    for mod_folder in os.listdir(RIMWORLD_MODS_PATH):
        mod_path = os.path.join(RIMWORLD_MODS_PATH, mod_folder)
        
        if not os.path.isdir(mod_path) or should_skip_folder(mod_path):
            continue
        
        print_info(f"Processing mod: {mod_folder}")
        
        # Find all DDS files in the mod
        for root, dirs, files in os.walk(mod_path):
            # Skip certain directories
            dirs[:] = [d for d in dirs if not should_skip_folder(os.path.join(root, d))]
            
            for file in files:
                if file.lower().endswith('.dds'):
                    dds_path = os.path.join(root, file)
                    try:
                        os.remove(dds_path)
                        deleted_count += 1
                        print_success(f"Deleted: {os.path.relpath(dds_path, RIMWORLD_MODS_PATH)}")
                    except Exception as e:
                        print_error(f"Could not delete {dds_path}: {e}")
    
    print()
    print("🎉 RESTORATION COMPLETE!")
    print(f"Deleted {deleted_count} DDS files.")
    print("Game will now use original PNG files.")

def build_exe():
    """Build standalone executable using PyInstaller."""
    print_info("Building standalone executable...")
    
    try:
        # Check if PyInstaller is available
        import PyInstaller
    except ImportError:
        print_error("PyInstaller not found. Please install it:")
        print("pip install PyInstaller")
        return
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", "RimWorldTextureOptimizer",
        "--distpath", "./dist",
        "--workpath", "./build",
        __file__
    ]
    
    print_info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print_success("Executable built successfully!")
        print_info("Find your executable in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print_error(f"Build failed: {e}")

def configure_paths():
    """Interactive configuration of paths."""
    global RIMWORLD_MODS_PATH, TEXCONV_PATH
    
    print("🔧 PATH CONFIGURATION")
    print("=" * 30)
    
    config = load_config()
    
    # Configure RimWorld mods path
    current_mods_path = config.get('rimworld_mods_path', RIMWORLD_MODS_PATH)
    print(f"Current RimWorld mods path: {current_mods_path}")
    new_mods_path = input("Enter new path (or press Enter to keep current): ").strip()
    if new_mods_path:
        config['rimworld_mods_path'] = new_mods_path
        RIMWORLD_MODS_PATH = new_mods_path
    
    # Configure texconv path
    current_texconv_path = config.get('texconv_path', TEXCONV_PATH)
    print(f"Current texconv.exe path: {current_texconv_path}")
    new_texconv_path = input("Enter new path (or press Enter to keep current): ").strip()
    if new_texconv_path:
        config['texconv_path'] = new_texconv_path
        TEXCONV_PATH = new_texconv_path
    
    save_config(config)
    print_success("Configuration saved!")

# ============================================================================
# MAIN FUNCTION AND CLI
# ============================================================================

def main():
    # Load existing config if any
    config = load_config()
    
    # Update global config from loaded file if values exist
    global RIMWORLD_MODS_PATH, TEXCONV_PATH, ENABLE_UPSCALING, GENERATE_MIPMAPS, DEFAULT_COMPRESSION_FORMAT, ENABLE_GPU
    RIMWORLD_MODS_PATH = config.get('rimworld_mods_path', RIMWORLD_MODS_PATH)
    TEXCONV_PATH = config.get('texconv_path', TEXCONV_PATH)
    ENABLE_UPSCALING = config.get('enable_upscaling', ENABLE_UPSCALING)
    GENERATE_MIPMAPS = config.get('generate_mipmaps', GENERATE_MIPMAPS)
    DEFAULT_COMPRESSION_FORMAT = config.get('compression_format', DEFAULT_COMPRESSION_FORMAT)
    ENABLE_GPU = config.get('enable_gpu', ENABLE_GPU) # Load global GPU default

    print_banner()
    
    # Check virtual environment first
    if not check_virtual_environment():
        return 1
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="RimWorld Texture Optimizer v2.0 - Using RimPy's proven approach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rimworld_texture_optimizer.py --convert        # Convert textures
  python rimworld_texture_optimizer.py --restore        # Remove DDS files
  python rimworld_texture_optimizer.py --build-exe      # Build executable
  python rimworld_texture_optimizer.py --configure      # Configure paths
        """
    )
    
    subparsers = parser.add_subparsers(dest='command')
    
    # --- Convert command ---
    parser_convert = subparsers.add_parser('convert', help='Convert textures to DDS format')
    parser_convert.add_argument(
        "--no-gpu", 
        action="store_false", 
        dest="enable_gpu", 
        help="Disable GPU acceleration for this run (overrides global config)"
    )
    parser_convert.set_defaults(func=convert_textures, enable_gpu=ENABLE_GPU) # Default for this run is global
    
    # --- Restore command ---
    parser_restore = subparsers.add_parser('restore', help='Restore original PNG files')
    parser_restore.set_defaults(func=restore_pngs)
    
    # --- Build EXE command ---
    parser_build_exe = subparsers.add_parser('build-exe', help='Build standalone executable')
    parser_build_exe.set_defaults(func=build_exe)
    
    # --- Configure command ---
    parser_configure = subparsers.add_parser('configure', help='Configure file paths')
    parser_configure.set_defaults(func=configure_paths)
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Check external tools
    if args.command in ['convert', 'restore']:
        if not check_tools():
            return 1
    
    # Execute requested action
    try:
        args.func(args)
        return 0
        
    except KeyboardInterrupt:
        print()
        print_warning("Operation cancelled by user")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    # Ensure Pillow is available before doing anything complex
    if not PILLOW_AVAILABLE or PILImage is None: # Check both
        print_error("Pillow library (PIL) is not installed. This script requires Pillow for image operations.")
        print_error("Please install it, e.g., by running: pip install Pillow")
        sys.exit(1)
        
    main()
