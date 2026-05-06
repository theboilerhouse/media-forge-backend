"""
Media Forge API Backend
Handles audio AND video extraction from URLs

Requirements:
- Python 3.8+
- Flask
- yt-dlp
- ffmpeg (system installation)

Install dependencies:
pip install flask flask-cors yt-dlp
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_DIR = tempfile.gettempdir()
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit for video

# Quality settings
AUDIO_QUALITY = {
    'high': '320',
    'medium': '192',
    'low': '128'
}

VIDEO_QUALITY = {
    '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
    '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
    '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]'
}


def get_media_info(url):
    """Extract metadata from URL without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'webpage_url': info.get('webpage_url', url)
            }
    except Exception as e:
        raise Exception(f"Failed to extract info: {str(e)}")


def download_audio(url, format_type='mp3', quality='high'):
    """Download and convert audio from URL"""
    
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")
    
    if format_type == 'mp3':
        bitrate = AUDIO_QUALITY.get(quality, '320')
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate,
            }],
            'quiet': True,
            'no_warnings': True,
        }
    elif format_type == 'wav':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'quiet': True,
            'no_warnings': True,
        }
    elif format_type == 'flac':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'flac',
            }],
            'quiet': True,
            'no_warnings': True,
        }
    else:
        raise Exception(f"Unsupported audio format: {format_type}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_file = os.path.join(DOWNLOAD_DIR, f"{file_id}.{format_type}")
            
            return {
                'file_path': final_file,
                'file_id': file_id,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'format': format_type,
                'size': os.path.getsize(final_file) if os.path.exists(final_file) else 0
            }
    except Exception as e:
        raise Exception(f"Audio download failed: {str(e)}")


def download_video(url, format_type='mp4', quality='1080p'):
    """Download video from URL"""
    
    file_id = str(uuid.uuid4())
    output_file = os.path.join(DOWNLOAD_DIR, f"{file_id}.{format_type}")
    
    format_string = VIDEO_QUALITY.get(quality, VIDEO_QUALITY['720p'])
    
    ydl_opts = {
        'format': format_string,
        'outtmpl': output_file,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': format_type,
    }
    
    # Special handling for webm
    if format_type == 'webm':
        ydl_opts['format'] = f'bestvideo[ext=webm][height<={quality.replace("p", "")}]+bestaudio[ext=webm]/best[ext=webm]'
        ydl_opts['merge_output_format'] = 'webm'
    
    # Special handling for mkv
    if format_type == 'mkv':
        ydl_opts['merge_output_format'] = 'mkv'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find the actual downloaded file
            actual_file = output_file
            if not os.path.exists(actual_file):
                # Try to find the file with correct extension
                for ext in [format_type, 'mp4', 'webm', 'mkv']:
                    test_file = os.path.join(DOWNLOAD_DIR, f"{file_id}.{ext}")
                    if os.path.exists(test_file):
                        actual_file = test_file
                        break
            
            # Get video resolution
            resolution = f"{info.get('height', 'Unknown')}p" if info.get('height') else quality
            
            return {
                'file_path': actual_file,
                'file_id': file_id,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'format': format_type,
                'resolution': resolution,
                'size': os.path.getsize(actual_file) if os.path.exists(actual_file) else 0
            }
    except Exception as e:
        raise Exception(f"Video download failed: {str(e)}")


@app.route('/api/info', methods=['POST'])
def get_info():
    """Get media information from URL"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        info = get_media_info(url)
        return jsonify(info), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extract', methods=['POST'])
def extract_media():
    """Extract audio or video from URL"""
    try:
        data = request.get_json()
        url = data.get('url')
        format_type = data.get('format', 'mp3').lower()
        quality = data.get('quality', 'high').lower()
        media_type = data.get('media_type', 'audio').lower()
        
        # Validation
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        audio_formats = ['mp3', 'wav', 'flac']
        video_formats = ['mp4', 'webm', 'mkv']
        
        if media_type == 'audio':
            if format_type not in audio_formats:
                return jsonify({'error': f'Invalid audio format. Choose: {", ".join(audio_formats)}'}), 400
            result = download_audio(url, format_type, quality)
            bitrate = f"{AUDIO_QUALITY.get(quality, '320')}kbps" if format_type == 'mp3' else "Lossless"
        else:
            if format_type not in video_formats:
                return jsonify({'error': f'Invalid video format. Choose: {", ".join(video_formats)}'}), 400
            result = download_video(url, format_type, quality)
            bitrate = result.get('resolution', quality)
        
        # Format file size
        size_bytes = result['size']
        if size_bytes >= 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif size_bytes >= 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size_bytes / 1024:.1f} KB"
        
        # Format duration
        duration = result['duration']
        if duration >= 3600:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}:{seconds:02d}"
        
        return jsonify({
            'success': True,
            'file_id': result['file_id'],
            'title': result['title'],
            'duration': duration_str,
            'bitrate': bitrate,
            'resolution': result.get('resolution', None),
            'size': size_str,
            'format': format_type,
            'media_type': media_type
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """Download the converted media file"""
    try:
        # Check all supported formats
        all_formats = ['mp3', 'wav', 'flac', 'mp4', 'webm', 'mkv']
        
        for ext in all_formats:
            file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.{ext}")
            if os.path.exists(file_path):
                mime_types = {
                    'mp3': 'audio/mpeg',
                    'wav': 'audio/wav',
                    'flac': 'audio/flac',
                    'mp4': 'video/mp4',
                    'webm': 'video/webm',
                    'mkv': 'video/x-matroska'
                }
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=f"media.{ext}",
                    mimetype=mime_types.get(ext, 'application/octet-stream')
                )
        
        return jsonify({'error': 'File not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cleanup/<file_id>', methods=['DELETE'])
def cleanup_file(file_id):
    """Clean up downloaded file"""
    try:
        deleted = False
        all_formats = ['mp3', 'wav', 'flac', 'mp4', 'webm', 'mkv']
        
        for ext in all_formats:
            file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True
        
        if deleted:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'File not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Media Forge API',
        'supported_audio': ['mp3', 'wav', 'flac'],
        'supported_video': ['mp4', 'webm', 'mkv']
    }), 200


if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get('PORT', 5000))
    
    print("🎬 Media Forge API Starting...")
    print(f"📡 Server running on http://localhost:{port}")
    print("\nSupported formats:")
    print("  Audio: MP3, WAV, FLAC")
    print("  Video: MP4, WebM, MKV")
    print("\nAvailable endpoints:")
    print("  POST   /api/info      - Get media information")
    print("  POST   /api/extract   - Extract audio or video")
    print("  GET    /api/download/<file_id> - Download file")
    print("  DELETE /api/cleanup/<file_id>  - Clean up file")
    print("  GET    /api/health    - Health check")
    
    app.run(debug=False, host='0.0.0.0', port=port)
