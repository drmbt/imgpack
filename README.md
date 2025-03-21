# imgpack

A powerful media organization and sharing tool that creates beautiful web galleries from your media files.

![imgpack gallery screenshot](/assets/screenshot.png)

## Key Features

### 🗂️ Smart Media Organization
- **Automatic Sorting**: Organizes your media files into clean, categorized folders
- **Pattern Filtering**: Create custom tabs based on file patterns (e.g., `--tabs mp3 wav` for audio)
- **Flexible Collection**: Use `--all` to include everything, or filter for specific media types

### 🌐 Web Gallery Generation
- Generates a responsive, dark-themed web gallery
- PhotoSwipe integration for smooth image viewing
- Audio and video playback support
- Mobile-friendly interface

### 🗜️ Media Optimization
- **Smart Compression**: Optimize media files for web with `--compress`:
  - Images: Resized and optimized while maintaining quality
  - Video: H.264 encoding with quality-size balance
  - Audio: AAC encoding for efficient streaming
- **Archive Creation**: Package galleries into ZIP files with `--zip` for easy sharing

## Quick Start

```bash
# Basic usage - creates gallery from current directory
./imgpack.sh

# Create organized gallery with specific media types
./imgpack.sh --tabs mp3 wav mp4

# Include all media files, but create pattern-based tabs
./imgpack.sh --tabs mp3 wav mp4 --all

# Create optimized gallery with compressed media
./imgpack.sh --compress

# Create organized gallery and package it for sharing
./imgpack.sh --tabs mp3 wav mp4 --compress --zip
```

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR-USERNAME/imgpack.git

# Make the script executable
chmod +x imgpack.sh
```

## Advanced Usage

### Directory Scanning
```bash
# Scan recursively
./imgpack.sh -r

# Limit recursive depth
./imgpack.sh -r --depth 3
```

### Media Organization Examples
```bash
# Create tabs for different media types
./imgpack.sh --tabs jpg mp4 mp3

# Create tabs for specific content
./imgpack.sh --tabs wallpaper screenshot meme

# Include everything but organize specific types
./imgpack.sh --tabs wallpaper screenshot --all
```

## Requirements

- Python 3.x
- Optional dependencies for compression:
  - Pillow (for image compression)
  - ffmpeg-python (for audio/video compression)

## Output Structure

```
imgshare_YYYYMMDD_HHMM/
├── index.html           # Web gallery
├── media/              # Organized media folders
│   ├── all/           # All collected media
│   ├── mp3/           # Audio files
│   ├── mp4/           # Video files
│   └── jpg/           # Image files
└── imgshare_YYYYMMDD_HHMM.zip  # (if --zip used)
```

## License

MIT License - see [LICENSE](LICENSE) for details. 