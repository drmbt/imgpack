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
        
        .controls button {
            background: #444;
            border: 1px solid #555;
            color: #fff;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .controls button:hover {
            background: #555;
        }

        .controls .selection-info {
            font-size: 0.9em;
            color: #aaa;
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
            display: block;
            cursor: zoom-in;
            transition: transform 0.2s;
        }
        
        .gallery .item video, 
        .gallery .item audio {
            width: 100%;
            height: auto;
            display: block;
            cursor: pointer;
            transition: transform 0.2s;
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

        .item-checkbox {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 2;
            width: 20px;
            height: 20px;
            cursor: pointer;
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
    </style>
</head>
<body>
    <div class="controls">
        <label>
            Columns: <span id="columns-value">2</span>
            <input type="range" min="1" max="8" value="2" id="columns">
        </label>
        <input type="text" id="search" placeholder="Search files...">
        <button id="sort-toggle">Sort: Newest First</button>
        <button id="select-all">Select All</button>
        <div class="selection-info">Selected: <span id="selected-count">0</span> of <span id="total-count">0</span></div>
    </div>

    <div class="gallery" id="gallery"></div>

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
        // The file list will be replaced by the Python script
        const files = [
/*FILES_PLACEHOLDER*/
        ];

        function initGallery() {
            try {
                console.log('Starting gallery initialization...');
                
                // Initialize PhotoSwipe if available
                if (typeof PhotoSwipe !== 'undefined' && typeof PhotoSwipeLightbox !== 'undefined') {
                    console.log('PhotoSwipe is available, initializing lightbox...');
                    const lightbox = new PhotoSwipeLightbox({
                        gallery: '#gallery',
                        children: 'a',
                        pswpModule: PhotoSwipe,
                        wheelToZoom: true,
                        padding: { top: 30, bottom: 30, left: 0, right: 0 }
                    });
                    lightbox.init();
                    console.log('Lightbox initialized');
                } else {
                    console.log('PhotoSwipe not available, using basic gallery');
                }

                // Handle column changes
                const columnsSlider = document.getElementById('columns');
                const columnsValue = document.getElementById('columns-value');
                const searchInput = document.getElementById('search');
                const selectAllBtn = document.getElementById('select-all');
                const selectedCountSpan = document.getElementById('selected-count');
                const totalCountSpan = document.getElementById('total-count');
                
                columnsSlider.addEventListener('input', function(e) {
                    const value = e.target.value;
                    columnsValue.textContent = value;
                    document.querySelector('.gallery').style.gridTemplateColumns = 
                        `repeat(${value}, 1fr)`;
                });

                // Handle sort toggle
                let sortNewestFirst = true;
                const sortButton = document.getElementById('sort-toggle');
                const sortedFiles = [...files];

                // Fuzzy search function
                function fuzzyMatch(str, pattern) {
                    pattern = pattern.toLowerCase();
                    str = str.toLowerCase();
                    
                    let patternIdx = 0;
                    let strIdx = 0;
                    
                    while (patternIdx < pattern.length && strIdx < str.length) {
                        if (pattern[patternIdx] === str[strIdx]) {
                            patternIdx++;
                        }
                        strIdx++;
                    }
                    
                    return patternIdx === pattern.length;
                }

                function updateSelectionCount() {
                    const selected = document.querySelectorAll('.item-checkbox:checked').length;
                    const total = files.length;
                    selectedCountSpan.textContent = selected;
                    totalCountSpan.textContent = total;
                    selectAllBtn.textContent = selected === total ? 'Deselect All' : 'Select All';
                }

                function updateGallery() {
                    const gallery = document.getElementById('gallery');
                    gallery.innerHTML = '';
                    
                    const searchTerm = searchInput.value.trim();
                    
                    sortedFiles.forEach((file, index) => {
                        // Apply search filter
                        if (searchTerm && !fuzzyMatch(file.name, searchTerm)) {
                            return;
                        }
                        
                        const itemDiv = document.createElement('div');
                        itemDiv.className = 'item';
                        
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.className = 'item-checkbox';
                        checkbox.dataset.index = index;
                        checkbox.addEventListener('change', updateSelectionCount);
                        
                        const link = document.createElement('a');
                        link.href = file.path;
                        
                        let element;
                        if (file.type.startsWith('video/')) {
                            element = document.createElement('video');
                            element.controls = true;
                            element.preload = 'metadata';
                        } else if (file.type.startsWith('audio/')) {
                            element = document.createElement('audio');
                            element.controls = true;
                            element.preload = 'metadata';
                        } else {
                            element = document.createElement('img');
                        }
                        
                        element.src = file.path;
                        element.alt = file.name;
                        
                        const typeLabel = document.createElement('div');
                        typeLabel.className = 'media-type';
                        typeLabel.textContent = file.type.split('/')[0].toUpperCase();
                        
                        const tooltip = document.createElement('div');
                        tooltip.className = 'filename-tooltip';
                        tooltip.textContent = file.name;
                        
                        itemDiv.appendChild(checkbox);
                        link.appendChild(element);
                        itemDiv.appendChild(link);
                        itemDiv.appendChild(typeLabel);
                        itemDiv.appendChild(tooltip);
                        gallery.appendChild(itemDiv);
                        
                        if (file.type.startsWith('image/')) {
                            link.dataset.pswpWidth = 1200;
                            link.dataset.pswpHeight = 800;
                            
                            element.onload = function() {
                                link.dataset.pswpWidth = this.naturalWidth;
                                link.dataset.pswpHeight = this.naturalHeight;
                            };
                        }
                    });

                    updateSelectionCount();
                }

                // Handle search input
                searchInput.addEventListener('input', updateGallery);

                // Handle select all
                selectAllBtn.addEventListener('click', function() {
                    const checkboxes = document.querySelectorAll('.item-checkbox');
                    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                    checkboxes.forEach(cb => cb.checked = !allChecked);
                    updateSelectionCount();
                });

                sortButton.addEventListener('click', function() {
                    sortNewestFirst = !sortNewestFirst;
                    sortButton.textContent = `Sort: ${sortNewestFirst ? 'Newest' : 'Oldest'} First`;
                    
                    sortedFiles.sort((a, b) => {
                        return sortNewestFirst ? 
                            b.mtime - a.mtime : 
                            a.mtime - b.mtime;
                    });
                    
                    updateGallery();
                });

                // Initial gallery setup
                updateGallery();

                // Set initial column count
                document.querySelector('.gallery').style.gridTemplateColumns = 'repeat(2, 1fr)';

                console.log('Gallery initialization complete');
            } catch (error) {
                console.error('Error initializing gallery:', error);
                document.body.innerHTML += `
                    <div style="color: red; padding: 20px; background: rgba(255,0,0,0.1); border: 1px solid red; margin: 20px;">
                        <h3>Error loading gallery</h3>
                        <pre>${error.stack || error.message}</pre>
                    </div>`;
            }
        }

        // Initialize gallery when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initGallery);
        } else {
            initGallery();
        }
    </script>
</body>
</html>
'''

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

def create_download_handler(media_dir):
    """Create a download handler for selected files"""
    def download_handler(environ, start_response):
        try:
            # Get the POST data
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = environ['wsgi.input'].read(content_length).decode('utf-8')
            
            # Parse the form data
            import urllib.parse
            post_dict = urllib.parse.parse_qs(post_data)
            selected_files = json.loads(post_dict['files'][0])
            
            # Create a temporary ZIP file
            zip_path = media_dir / 'selected_files.zip'
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for file in selected_files:
                    file_path = media_dir / file['name']
                    if file_path.exists():
                        zf.write(file_path, file['name'])
            
            # Send the ZIP file
            with open(zip_path, 'rb') as f:
                file_content = f.read()
            
            headers = [
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', 'attachment; filename="selected_files.zip"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            start_response('200 OK', headers)
            return [file_content]
            
        except Exception as e:
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [str(e).encode()]
        
        finally:
            # Clean up the temporary ZIP file
            if zip_path.exists():
                zip_path.unlink()
    
    return download_handler

def serve_gallery(gallery_dir):
    """Serve the gallery using a simple HTTP server"""
    from wsgiref.simple_server import make_server
    import urllib.parse
    
    def application(environ, start_response):
        path = environ.get('PATH_INFO', '').lstrip('/')
        
        if environ['REQUEST_METHOD'] == 'POST' and path == 'download':
            return download_handler(environ, start_response)
        
        if not path or path == 'index.html':
            file_path = gallery_dir / 'index.html'
        else:
            file_path = gallery_dir / path
        
        if not file_path.exists():
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'File not found']
        
        content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        start_response('200 OK', [('Content-Type', content_type)])
        return [file_content]
    
    port = 8000
    httpd = make_server('', port, application)
    print(f"\nServing gallery at http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    
    return httpd

def main():
    args = parse_args()
    
    # Initialize mimetypes
    mimetypes.init()
    
    # Get current directory and resolve any symlinks
    current_dir = Path.cwd().resolve()
    print("Creating gallery...")
    
    # Create timestamp for new directory
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
    new_dir_name = f'imgshare_{timestamp}'
    new_dir = current_dir / new_dir_name
    media_dir = new_dir / 'media'
    
    # Create directories
    media_dir.mkdir(parents=True, exist_ok=True)
    
    # Find and process media files
    media_files = []
    for file in current_dir.iterdir():
        if file.is_file() and is_media_file(str(file)):
            # Copy file to media directory
            shutil.copy2(file, media_dir)
            
            # Get mime type and file stats
            mime_type, _ = mimetypes.guess_type(str(file))
            mime_type = mime_type or 'application/octet-stream'
            mtime = os.path.getmtime(file)
            
            # Add to media files list with relative path
            media_files.append({
                'name': file.name,
                'type': mime_type,
                'path': f'media/{file.name}',  # Relative path from index.html
                'mtime': mtime  # Add modification time for sorting
            })
    
    if not media_files:
        print("No media files found in current directory!")
        sys.exit(1)
    
    # Sort files by modification time (newest first)
    media_files.sort(key=lambda x: x['mtime'], reverse=True)
    
    # Generate the files list for HTML
    files_json = ',\n        '.join(
        f"{{ name: '{f['name'].replace("'", "\\'")}', type: '{f['type']}', path: '{f['path']}', mtime: {f['mtime']} }}"
        for f in media_files
    )
    
    # Create index.html
    html_content = HTML_TEMPLATE.replace('/*FILES_PLACEHOLDER*/', files_json)
    index_path = new_dir / 'index.html'
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Count media types
    media_types = {}
    for f in media_files:
        media_type = f['type'].split('/')[0]
        media_types[media_type] = media_types.get(media_type, 0) + 1
    
    # Print summary
    print("\nGallery created successfully!")
    print(f"Location: {new_dir}")
    print(f"Total files: {len(media_files)}")
    print("Media types:")
    for media_type, count in media_types.items():
        print(f"  - {media_type}: {count}")
    
    if not args.no_browser:
        # Handle path conversion for WSL
        if is_wsl():
            # Wait a moment for files to be written
            time.sleep(0.5)
            
            windows_path = convert_wsl_path_to_windows(index_path)
            if windows_path:
                print("\nOpening gallery in Windows Explorer...")
                try:
                    # Use explorer.exe to open the file in Windows
                    subprocess.run(['explorer.exe', windows_path], check=True)
                except Exception as e:
                    print(f"\nFailed to open Windows Explorer: {e}")
                    print(f"Please manually open this file: {windows_path}")
            else:
                print("\nWarning: Could not convert WSL path to Windows path.")
                print(f"Please manually open: {index_path}")
        else:
            print("\nOpening gallery in your default browser...")
            file_url = index_path.absolute().as_uri()
            webbrowser.open(file_url)
    else:
        print("\nUse --no-browser flag to prevent automatic browser opening")

if __name__ == '__main__':
    main() 