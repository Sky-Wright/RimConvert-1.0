# RimConvert

A high-performance tool to optimize textures in your RimWorld mods, drastically improving loading times and VRAM usage for all GPUs.

## Platform Compatibility

**Primary Target: Windows 11 (64-bit)**

The tool works on Linux, but **is not recommended** due to RimWorld-specific DDS loading issues that can cause crashes (CTD) when loading 2x upscaled textures. If you want to use RimConvert on Linux, you'll need to troubleshoot these compatibility issues yourself.

## Why Use This Tool?
Large RimWorld mod lists often suffer from slow loading and high memory use due to unoptimized PNG textures. This tool converts them into a more efficient format (DDS), giving you:

* **Faster Loading:** Mods load 2-3 times quicker.
* **Less VRAM Usage:** Up to 60% reduction in memory use.
* **Better Performance:** Smoother gameplay and improved FPS.
* **Universal GPU Support:** Works seamlessly with Intel Arc, NVIDIA, and AMD graphics cards.
* **No Risk:** Your original mod files (PNGs) are left untouched.
* **Seamless Compatibility:** Works perfectly with mods like Graphics Settings+.

## Key Features
* **Lightning Fast:** Uses multi-threading and GPU acceleration for quick conversions (e.g., 79,000+ textures in under an hour).
* **Smart Upscaling:** Improves clarity for small textures by gently upscaling them.
* **Real-time Progress:** See exactly what's happening with live stats and estimated completion.
* **Easy to Use:** A simple, focused interface with essential options.

## Requirements
* **Windows 11 (64-bit)** (recommended)
* **Modern GPU** (Intel Arc, AMD, Nvidia) & **Multi-core CPU**
* **Graphics Settings+ mod** (or similar DDS texture loader for RimWorld)
* Sufficient disk space (DDS files are typically smaller than PNGs).

*All necessary tools are included—no extra downloads needed.*

## Quick Start Guide

### Option 1: Download & Run (Recommended)
1.  Download the zipped folder from the [Releases](../../releases) page.
2.  Extract the folder and run `RimConvert.exe`. No installation required.
3.  Select your RimWorld mod folder and start the conversion.
4.  Ensure you have the **Graphics Settings+** mod (or similar) installed in RimWorld.
5.  Launch RimWorld and enjoy the improved performance!

### Option 2: Run from Source
1.  Clone or download this repository.
2.  Run `Start.bat` to set up a local Python environment and launch the tool.

## In-Depth Guide

### 1. Launch the Application
Run `RimConvert.exe` or `python rimworld_gui.py`.

### 2. Configure Paths
* **Mods Folder:** Select your RimWorld mod directory (e.g., `C:\Steam\steamapps\common\RimWorld\Mods`).
* **Texconv Path:** This is usually auto-detected and included with the app.

### 3. Adjust Settings
* **Enable Upscaling:** Recommended for better quality on small textures.
* **Prefer GPU:** Recommended for the fastest conversion speeds.

### 4. Start the Process
* Click **"Convert Textures"**.
* Monitor the **real-time progress and statistics**. Conversions can take **45-90 minutes** for very large mod lists.

### 5. Enjoy Faster Performance
* Launch **RimWorld** to experience significantly **faster loading and better FPS**.
* Your original PNGs remain as a safe fallback; DDS files are automatically prioritized by Graphics Settings+.

## Technical Details

### Compression & Output
* **Format:** Uses **BC7_UNORM** for high-quality texture compression.
* **Mipmaps:** Automatically generated for optimal game performance.
* **Orientation:** Includes pre-flip logic to ensure textures display correctly in RimWorld.
* **Output:** Optimized `.dds` files are created alongside the original `.png` files.

### Processing Workflow
1.  **Discovery:** Scans mod folders for PNG textures.
2.  **Analysis:** Checks texture properties like dimensions.
3.  **Pre-processing:** Applies necessary flips and performs upscaling (if enabled).
4.  **Compression:** Utilizes GPU-accelerated DirectXTex to convert to BC7 DDS.

### Performance Optimizations
* **Multi-threading:** Processes multiple textures in parallel.
* **GPU Acceleration:** Leverages DirectXTex with compute shaders for speed.
* **Smart Batching:** Efficiently manages memory for large numbers of textures.
* **Live Updates:** UI remains responsive throughout the conversion.

## Performance Comparison

| Tool | GPU Support | 79,774 Textures | Quality | Notes |
| :------------------------------ | :---------- | :-------------- | :-------- | :------------------ |
| **RimConvert** | Universal | **59 minutes** | **BC7 (Excellent)** | Best speed |
| RimPy (GPU) | NVIDIA only | 2-4 hours | Default BC3 | CUDA required |
| RimPy (CPU) | Any | 6+ hours | Default BC3 | Slow fallback |

*Real-world test: **376 mods, with 79,774 PNG textures processed in 59 minutes** using **Intel Arc B580 (12GB) x i9-9900k***

## Troubleshooting

### Common Issues & Fixes
* **"texconv.exe not found"**: Ensure the `compressors` folder is with `RimConvert.exe` in the main app folder.
* **"No PNG files found"**: Double-check that your selected mod folder path is correct and contains PNG textures.
* **Conversion too slow?**: Make sure **"Prefer GPU"** is enabled and close other GPU-intensive apps.
* **Visual artifacts in game?**: Delete the problematic DDS file; RimWorld will automatically use the original PNG fallback.
* **Crashes on Linux?**: RimWorld on Linux may have issues loading 2x upscaled DDS textures. Use Windows 11 for best compatibility.

## License
CC0 - Public Domain – Free to use, modify, and distribute.

---

*Made for the RimWorld modding community, by Sky*
