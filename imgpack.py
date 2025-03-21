#!/usr/bin/env python3

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
import mimetypes
import urllib.request
import base64
import argparse
import webbrowser
import platform
import subprocess
import time
import zipfile
import json

def parse_args():
    parser = argparse.ArgumentParser(description='Create an image gallery from the current directory.')
    parser.add_argument('--no-browser', action='store_true', help='Do not automatically open the gallery in a browser')
    parser.add_argument('--tabs', nargs='+', help='Create tabs based on patterns (e.g., --tabs lora banny .mp4)')
    parser.add_argument('--zip', action='store_true', help='Create a ZIP archive of the gallery')
    parser.add_argument('-r', '--recursive', action='store_true', help='Search recursively in subdirectories')
    parser.add_argument('--depth', type=int, help='Maximum directory depth to search (default: 1, or unlimited if recursive)')
    return parser.parse_args()

def is_wsl():
    """Check if running under Windows Subsystem for Linux"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False

def convert_wsl_path_to_windows(path):
    """Convert a WSL path to a Windows path, handling symlinks"""
    try:
        # Use wslpath -wa to get the absolute Windows path, resolving symlinks
        result = subprocess.run(['wslpath', '-wa', str(path)], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        windows_path = result.stdout.strip()
        
        # Ensure the path exists before returning
        if os.path.exists(path):
            return windows_path
        return None
    except Exception as e:
        print(f"\nDebug: WSL path conversion failed: {e}")
        return None

def download_file(url):
    """Download a file from URL and return its contents as string."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}  # Some CDNs require a user agent
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Warning: Failed to download {url}: {e}")
        return None

# Download PhotoSwipe scripts
PHOTOSWIPE_CSS = download_file('https://cdnjs.cloudflare.com/ajax/libs/photoswipe/5.4.4/photoswipe.min.css')
PHOTOSWIPE_JS = download_file('https://cdnjs.cloudflare.com/ajax/libs/photoswipe/5.4.4/umd/photoswipe.umd.min.js')
PHOTOSWIPE_LIGHTBOX_JS = download_file('https://cdnjs.cloudflare.com/ajax/libs/photoswipe/5.4.4/umd/photoswipe-lightbox.umd.min.js')

if not all([PHOTOSWIPE_CSS, PHOTOSWIPE_JS, PHOTOSWIPE_LIGHTBOX_JS]):
    print("Error: Failed to download one or more required PhotoSwipe files.")
    print("Using fallback version...")
    # Fallback to basic gallery without PhotoSwipe
    PHOTOSWIPE_CSS = ""
    PHOTOSWIPE_JS = ""
    PHOTOSWIPE_LIGHTBOX_JS = ""

def matches_pattern(filename, pattern):
    """Check if filename matches the pattern case-insensitively"""
    return pattern.lower() in filename.lower()

def organize_files_by_tabs(directory, patterns, recursive=False, max_depth=1):
    """Organize files into tabs based on patterns"""
    tab_files = {'all': []}  # Always include 'all' tab
    
    def process_directory(dir_path, current_depth=1):
        try:
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    if entry.is_file():
                        if not is_media_file(entry.name):
                            continue
                            
                        # Add to 'all' tab first
                        tab_files['all'].append(entry.path)
                        
                        # Then check patterns
                        matched = False
                        for pattern in patterns:
                            if matches_pattern(entry.name, pattern):
                                if pattern not in tab_files:
                                    tab_files[pattern] = []
                                tab_files[pattern].append(entry.path)
                                matched = True
                        
                        if not matched:
                            if 'other' not in tab_files:
                                tab_files['other'] = []
                            tab_files['other'].append(entry.path)
                    
                    elif entry.is_dir() and (recursive or current_depth < max_depth):
                        if recursive or current_depth < max_depth:
                            process_directory(entry.path, current_depth + 1)
        except PermissionError:
            print(f"Warning: Permission denied accessing {dir_path}")
        except Exception as e:
            print(f"Warning: Error processing {dir_path}: {e}")
    
    process_directory(directory)
    # Only return tabs that have files, but always include 'all'
    return {k: v for k, v in tab_files.items() if v or k == 'all'}

def generate_gallery_html(directory, tab_name, is_all_tab=False):
    """Generate HTML for a gallery of media files in the given directory"""
    html = []
    
    files_to_process = []
    if is_all_tab:
        # For 'all' tab, look in all subdirectories
        for subdir in os.scandir(directory):
            if subdir.is_dir():
                for file in os.scandir(subdir):
                    if file.is_file() and is_media_file(file.name):
                        files_to_process.append((file.name, subdir.name))
    else:
        # For other tabs, just look in their directory
        for file in os.scandir(directory):
            if file.is_file() and is_media_file(file.name):
                files_to_process.append((file.name, tab_name))
    
    # Sort files by name
    files_to_process.sort(key=lambda x: x[0])
    
    for file_name, source_tab in files_to_process:
        mime_type, _ = mimetypes.guess_type(file_name)
        mime_type = mime_type or 'application/octet-stream'
        media_type = mime_type.split('/')[0]
        
        # Use relative path from index.html to the file in the media/tab subdirectory
        relative_path = f'media/{source_tab}/{file_name}'
        
        item_html = f'''
        <div class="item" data-filename="{file_name}">'''
            
        if media_type == 'image':
            item_html += f'''
            <a href="{relative_path}" 
               class="gallery-image"
               data-pswp-src="{relative_path}">
                <img src="{relative_path}" alt="{file_name}">
            </a>'''
        elif media_type == 'video':
            item_html += f'''
            <video controls preload="metadata">
                <source src="{relative_path}" type="{mime_type}">
            </video>'''
        elif media_type == 'audio':
            item_html += f'''
            <audio controls preload="metadata">
                <source src="{relative_path}" type="{mime_type}">
            </audio>'''
            
        item_html += f'''
            <div class="media-type">{media_type.upper()}</div>
            <div class="filename-tooltip">{file_name}</div>
        </div>'''
        
        html.append(item_html)
    
    return '\n'.join(html)

# HTML template for the gallery
HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Image Gallery</title>
    <style>
        /* PhotoSwipe styles */
        ''' + PHOTOSWIPE_CSS + '''

        /* Gallery styles */
        body { 
            margin: 0; 
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #1a1a1a;
            color: #fff;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            position: sticky;
            top: 0;
            background: #1a1a1a;
            padding: 10px 0;
            z-index: 1000;
        }
        
        .tab {
            padding: 8px 16px;
            background: #333;
            border: none;
            border-radius: 4px;
            color: #fff;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .tab:hover {
            background: #444;
        }
        
        .tab.active {
            background: #555;
        }
        
        .gallery-container {
            display: none;
        }
        
        .gallery-container.active {
            display: block;
        }
        
        .controls {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #333;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1000;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
            max-width: 600px;
        }
        
        .controls label {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .controls input[type="range"] {
            width: 100px;
            background: #444;
            height: 6px;
            -webkit-appearance: none;
            border-radius: 3px;
        }
        
        .controls input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 15px;
            height: 15px;
            background: #fff;
            border-radius: 50%;
            cursor: pointer;
        }

        .controls input[type="text"] {
            padding: 5px 10px;
            border: 1px solid #555;
            border-radius: 3px;
            background: #444;
            color: #fff;
            width: 150px;
        }
        
        .gallery {
            display: grid;
            gap: 10px;
            margin-top: 60px;
        }
        
        .gallery .item {
            display: block;
            position: relative;
            overflow: hidden;
            background: #333;
            border-radius: 5px;
            line-height: 0;
        }
        
        .gallery .item img {
            width: 100%;
            height: auto;
            min-height: 150px; /* Minimum height to ensure visibility */
            display: block;
            cursor: zoom-in;
            transition: transform 0.2s;
            object-fit: contain;
        }
        
        .gallery .item video, 
        .gallery .item audio {
            width: 100%;
            height: auto;
            min-height: 150px; /* Minimum height for videos */
            display: block;
            cursor: pointer;
            transition: transform 0.2s;
            object-fit: contain;
        }
        
        .gallery .item audio {
            min-height: 50px; /* Smaller minimum height for audio controls */
            padding: 30px;
            box-sizing: border-box;
        }
        
        .gallery .item:hover img,
        .gallery .item:hover video {
            transform: scale(1.03);
        }

        .media-type {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 12px;
            z-index: 1;
        }

        .filename-tooltip {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 8px;
            font-size: 12px;
            transform: translateY(100%);
            transition: transform 0.2s;
        }

        .item:hover .filename-tooltip {
            transform: translateY(0);
        }

        .hidden {
            display: none !important;
        }

        .pswp {
            --pswp-bg: #000;
        }

        .search-container {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .clear-button {
            background: #444;
            border: 1px solid #555;
            color: #fff;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .clear-button:hover {
            background: #555;
        }
    </style>
</head>
<body>
    <div class="tabs">
        {% for tab in tabs %}
        <button class="tab" onclick="showTab('{{ tab }}')">{{ tab }} ({{ tab_counts[tab] }})</button>
        {% endfor %}
    </div>
    
    {% for tab in tabs %}
    <div id="{{ tab }}-gallery" class="gallery-container {% if loop.first %}active{% endif %}">
        <div class="controls">
            <label>
                Columns: <span id="{{ tab }}-columns-value">2</span>
                <input type="range" min="1" max="8" value="2" id="{{ tab }}-columns" onchange="updateColumns('{{ tab }}')">
            </label>
            <div class="search-container">
                <input type="text" id="{{ tab }}-search" placeholder="Search files..." onkeyup="filterItems('{{ tab }}')">
                <button class="clear-button" onclick="clearSearch('{{ tab }}')">Clear</button>
            </div>
        </div>
        <div class="gallery" id="{{ tab }}-grid">
            {{ galleries[tab] }}
        </div>
    </div>
    {% endfor %}

    <!-- PhotoSwipe template -->
    <div class="pswp" tabindex="-1" role="dialog" aria-hidden="true">
        <div class="pswp__bg"></div>
        <div class="pswp__scroll-wrap">
            <div class="pswp__container">
                <div class="pswp__item"></div>
                <div class="pswp__item"></div>
                <div class="pswp__item"></div>
            </div>
            <div class="pswp__ui pswp__ui--hidden">
                <div class="pswp__top-bar">
                    <div class="pswp__counter"></div>
                    <button class="pswp__button pswp__button--close" title="Close (Esc)"></button>
                    <button class="pswp__button pswp__button--share" title="Share"></button>
                    <button class="pswp__button pswp__button--fs" title="Toggle fullscreen"></button>
                    <button class="pswp__button pswp__button--zoom" title="Zoom in/out"></button>
                    <div class="pswp__preloader">
                        <div class="pswp__preloader__icn">
                            <div class="pswp__preloader__cut">
                                <div class="pswp__preloader__donut"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="pswp__share-modal pswp__share-modal--hidden pswp__single-tap">
                    <div class="pswp__share-tooltip"></div>
                </div>
                <button class="pswp__button pswp__button--arrow--left" title="Previous (arrow left)"></button>
                <button class="pswp__button pswp__button--arrow--right" title="Next (arrow right)"></button>
                <div class="pswp__caption">
                    <div class="pswp__caption__center"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- PhotoSwipe scripts -->
    <script>''' + PHOTOSWIPE_JS + '''</script>
    <script>''' + PHOTOSWIPE_LIGHTBOX_JS + '''</script>

    <script>
        function showTab(tabName) {
            // Hide all galleries
            document.querySelectorAll('.gallery-container').forEach(container => {
                container.classList.remove('active');
            });
            
            // Show selected gallery
            document.getElementById(tabName + '-gallery').classList.add('active');
            
            // Update tab buttons
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
        }
        
        function updateColumns(tabName) {
            const columnsInput = document.getElementById(tabName + '-columns');
            const columnsValue = document.getElementById(tabName + '-columns-value');
            const gallery = document.getElementById(tabName + '-grid');
            
            columnsValue.textContent = columnsInput.value;
            gallery.style.gridTemplateColumns = `repeat(${columnsInput.value}, 1fr)`;
        }
        
        function clearSearch(tabName) {
            const searchInput = document.getElementById(tabName + '-search');
            searchInput.value = '';
            filterItems(tabName);
        }
        
        function filterItems(tabName) {
            const searchInput = document.getElementById(tabName + '-search');
            const items = document.querySelectorAll(`#${tabName}-grid .item`);
            const searchText = searchInput.value.toLowerCase();
            
            items.forEach(item => {
                const filename = item.getAttribute('data-filename').toLowerCase();
                const tooltip = item.querySelector('.filename-tooltip').textContent.toLowerCase();
                const mediaType = item.querySelector('.media-type').textContent.toLowerCase();
                const shouldShow = filename.includes(searchText) || 
                                 tooltip.includes(searchText) || 
                                 mediaType.includes(searchText);
                item.classList.toggle('hidden', !shouldShow);
            });
        }
        
        // Function to get image dimensions
        function getImageDimensions(src) {
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = function() {
                    resolve({
                        width: this.naturalWidth,
                        height: this.naturalHeight
                    });
                };
                img.src = src;
            });
        }

        // Initialize PhotoSwipe
        document.addEventListener('DOMContentLoaded', () => {
            const lightbox = new PhotoSwipeLightbox({
                gallery: '.gallery',
                children: '.gallery-image',
                pswpModule: PhotoSwipe,
                wheelToZoom: true,
                padding: { top: 30, bottom: 30, left: 0, right: 0 },
                bgOpacity: 0.9,
                imageClickAction: 'zoom',
                tapAction: 'zoom',
                showHideAnimationType: 'fade'
            });

            // Set up image dimensions before opening
            lightbox.on('uiRegister', function() {
                lightbox.pswp.options.preload = [1, 2];
            });

            // Handle image loading
            lightbox.on('beforeOpen', async () => {
                const items = lightbox.pswp.options.dataSource;
                
                // Get dimensions for all images in the gallery
                await Promise.all(items.map(async (item) => {
                    if (!item.width || !item.height) {
                        const dimensions = await getImageDimensions(item.src);
                        item.width = dimensions.width;
                        item.height = dimensions.height;
                    }
                }));
            });

            lightbox.init();
            
            // Initialize columns for each tab
            {% for tab in tabs %}
            updateColumns('{{ tab }}');
            {% endfor %}
        });
    </script>
</body>
</html>'''

def is_media_file(file_path):
    """Check if file is an image, video, or audio file."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type.startswith(('image/', 'video/', 'audio/'))
    return False

def get_base64_data(file_path, mime_type):
    """Convert file to base64 data URL."""
    with open(file_path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    return f'data:{mime_type};base64,{data}'

def main():
    args = parse_args()
    
    # Create directory with timestamp (without seconds)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    gallery_dir = Path(f'imgshare_{timestamp}')
    gallery_dir.mkdir(parents=True, exist_ok=True)
    
    # Create media directory
    media_dir = gallery_dir / 'media'
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up search depth
    recursive = args.recursive
    max_depth = args.depth if args.depth is not None else (float('inf') if recursive else 1)
    
    # Organize files by tabs if patterns are provided
    if args.tabs:
        tab_files = organize_files_by_tabs(os.getcwd(), args.tabs, recursive, max_depth)
    else:
        # If no tabs specified, just use 'all' tab
        tab_files = {'all': []}
        
        def collect_files(dir_path, current_depth=1):
            try:
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        if entry.is_file() and is_media_file(entry.name):
                            tab_files['all'].append(entry.path)
                        elif entry.is_dir() and (recursive or current_depth < max_depth):
                            collect_files(entry.path, current_depth + 1)
            except PermissionError:
                print(f"Warning: Permission denied accessing {dir_path}")
            except Exception as e:
                print(f"Warning: Error processing {dir_path}: {e}")
        
        collect_files(os.getcwd())
    
    if not tab_files['all']:
        print("No media files found!")
        sys.exit(1)
    
    # Create subdirectories for each tab (except 'all') and copy files
    for tab_name, files in tab_files.items():
        if tab_name != 'all':  # Skip creating directory for 'all' tab
            tab_dir = media_dir / tab_name
            tab_dir.mkdir(parents=True, exist_ok=True)
            for file in files:
                dest = tab_dir / Path(file).name
                if os.path.exists(file) and not os.path.exists(dest):
                    shutil.copy2(file, dest)
    
    # Generate HTML for each tab
    galleries = {}
    tab_counts = {}
    for tab_name, files in tab_files.items():
        if tab_name == 'all':
            galleries[tab_name] = generate_gallery_html(media_dir, tab_name, is_all_tab=True)
        else:
            tab_dir = media_dir / tab_name
            galleries[tab_name] = generate_gallery_html(tab_dir, tab_name)
        tab_counts[tab_name] = len(files)
    
    # Create tab buttons HTML
    tab_buttons = []
    for tab in tab_files.keys():
        tab_buttons.append(f'<button class="tab" onclick="showTab(\'{tab}\')">{tab} ({tab_counts[tab]})</button>')
    
    # Create gallery containers HTML
    gallery_containers = []
    for tab in tab_files.keys():
        is_first = tab == list(tab_files.keys())[0]
        container = f'''
        <div id="{tab}-gallery" class="gallery-container{' active' if is_first else ''}">
            <div class="controls">
                <label>
                    Columns: <span id="{tab}-columns-value">2</span>
                    <input type="range" min="1" max="8" value="2" id="{tab}-columns" onchange="updateColumns(\'{tab}\')">
                </label>
                <div class="search-container">
                    <input type="text" id="{tab}-search" placeholder="Search files..." onkeyup="filterItems(\'{tab}\')">
                    <button class="clear-button" onclick="clearSearch(\'{tab}\')">Clear</button>
                </div>
            </div>
            <div class="gallery" id="{tab}-grid">
                {galleries[tab]}
            </div>
        </div>'''
        gallery_containers.append(container)
    
    # Initialize JavaScript for each tab
    init_js = []
    for tab in tab_files.keys():
        init_js.append(f'updateColumns(\'{tab}\');')
    
    # Create the gallery HTML
    gallery_html = HTML_TEMPLATE
    
    # Replace template variables
    replacements = {
        '<div class="tabs">\n        {% for tab in tabs %}\n        <button class="tab" onclick="showTab(\'{{ tab }}\')">{{ tab }} ({{ tab_counts[tab] }})</button>\n        {% endfor %}\n    </div>': 
            f'<div class="tabs">\n        {" ".join(tab_buttons)}\n    </div>',
        
        '{% for tab in tabs %}\n    <div id="{{ tab }}-gallery" class="gallery-container {% if loop.first %}active{% endif %}">\n        <div class="controls">\n            <label>\n                Columns: <span id="{{ tab }}-columns-value">2</span>\n                <input type="range" min="1" max="8" value="2" id="{{ tab }}-columns" onchange="updateColumns(\'{{ tab }}\')">\n            </label>\n            <div class="search-container">\n                <input type="text" id="{{ tab }}-search" placeholder="Search files..." onkeyup="filterItems(\'{{ tab }}\')">\n                <button class="clear-button" onclick="clearSearch(\'{{ tab }}\')">Clear</button>\n            </div>\n        </div>\n        <div class="gallery" id="{{ tab }}-grid">\n            {{ galleries[tab] }}\n        </div>\n    </div>\n    {% endfor %}':
            '\n'.join(gallery_containers),
        
        '{% for tab in tabs %}\n            updateColumns(\'{{ tab }}\');\n            {% endfor %}':
            '\n            '.join(init_js)
    }
    
    for template, replacement in replacements.items():
        gallery_html = gallery_html.replace(template, replacement)
    
    # Write the gallery HTML file
    gallery_path = gallery_dir / 'index.html'
    with open(gallery_path, 'w', encoding='utf-8') as f:
        f.write(gallery_html)
    
    # Count media types and unique files
    media_types = {}
    unique_files = set()  # Track unique files by their full path
    for tab_name, files in tab_files.items():
        if tab_name != 'all':  # Don't count 'all' tab to avoid double counting
            for f in files:
                unique_files.add(f)  # Add to set of unique files
                ext = Path(f).suffix.lower()[1:]  # Remove the dot
                if ext:
                    media_types[ext] = media_types.get(ext, 0) + 1
    
    # Print summary
    print("\nGallery created successfully!")
    print(f"Location: {gallery_dir}")
    print(f"Total unique files: {len(unique_files)}")
    print("Media types:")
    for media_type, count in media_types.items():
        print(f"  {media_type}: {count}")
    
    # Create ZIP archive if requested
    if args.zip:
        zip_path = gallery_dir.with_suffix('.zip')
        print(f"\nCreating ZIP archive: {zip_path}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(gallery_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(gallery_dir)
                    zipf.write(file_path, arcname)
        print("ZIP archive created successfully!")
    
    # Open in browser if requested
    if not args.no_browser:
        if is_wsl() or platform.system() == 'Windows':
            time.sleep(0.5)  # Small delay to ensure files are written
            
            if is_wsl():
                windows_path = convert_wsl_path_to_windows(gallery_path)
                if windows_path:
                    path_to_open = windows_path
                else:
                    print("\nWarning: Could not convert WSL path to Windows path.")
                    print(f"Please manually open: {gallery_path}")
                    return
            else:
                path_to_open = str(gallery_path.absolute())
            
            try:
                subprocess.run(['explorer.exe', path_to_open])
            except Exception as e:
                print(f"\nFailed to open Windows Explorer: {e}")
                print(f"Please manually open this file: {path_to_open}")
        else:
            # For non-Windows systems, use the default browser
            webbrowser.open(gallery_path.absolute().as_uri())

if __name__ == '__main__':
    main() 