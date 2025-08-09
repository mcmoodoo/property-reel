"""Video utility functions."""

import subprocess
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def get_video_info(video_path: Path) -> dict:
    """
    Get video metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video information
    """
    video_path = Path(video_path)
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Extract relevant information
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
        
        if not video_stream:
            raise ValueError("No video stream found")
        
        # Parse frame rate
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den != 0 else 30
        else:
            fps = float(fps_str)
        
        info = {
            "duration": float(data["format"].get("duration", 0)),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": fps,
            "codec": video_stream.get("codec_name", "unknown"),
            "bitrate": int(data["format"].get("bit_rate", 0)),
            "size_bytes": int(data["format"].get("size", 0)),
            "filename": data["format"].get("filename", str(video_path))
        }
        
        # Calculate total frames
        info["total_frames"] = int(info["duration"] * info["fps"])
        
        return info
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed: {e}")
        # Return minimal info
        return {
            "duration": 0,
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "codec": "unknown",
            "bitrate": 0,
            "size_bytes": 0,
            "filename": str(video_path),
            "total_frames": 0
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse ffprobe output: {e}")
        return {
            "duration": 0,
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "codec": "unknown",
            "bitrate": 0,
            "size_bytes": 0,
            "filename": str(video_path),
            "total_frames": 0
        }


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS.ms.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    else:
        return f"{minutes:02d}:{secs:05.2f}"