"""Frame extraction from video files using FFmpeg."""

import subprocess
import shutil
from pathlib import Path
import logging
from typing import Optional
import json

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extract frames from video at specified FPS."""
    
    def __init__(self, frames_dir: str = "frames"):
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(exist_ok=True)
        
    def extract(
        self, 
        video_path: Path, 
        fps: float = 3.0,
        height: int = 720,
        clean_existing: bool = True
    ) -> Path:
        """
        Extract frames from video.
        
        Args:
            video_path: Path to input video
            fps: Frames per second to extract
            height: Target height for frames (width scales proportionally)
            clean_existing: Remove existing frames before extraction
            
        Returns:
            Path to directory containing extracted frames
        """
        video_path = Path(video_path)
        output_dir = self.frames_dir / video_path.stem
        
        if clean_existing and output_dir.exists():
            logger.info(f"Cleaning existing frames in {output_dir}")
            shutil.rmtree(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build FFmpeg command
        output_pattern = output_dir / "frame_%06d.jpg"
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps={fps},scale=-2:{height}",
            "-q:v", "2",  # High quality JPEG
            "-loglevel", "error",
            "-stats",
            str(output_pattern)
        ]
        
        logger.info(f"Extracting frames at {fps} FPS, {height}p height")
        logger.info(f"Output directory: {output_dir}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stderr:
                logger.warning(f"FFmpeg warnings: {result.stderr}")
                
            # Count extracted frames
            frame_count = len(list(output_dir.glob("frame_*.jpg")))
            logger.info(f"Extracted {frame_count} frames")
            
            # Save metadata
            metadata = {
                "video_path": str(video_path.absolute()),
                "fps": fps,
                "height": height,
                "frame_count": frame_count
            }
            
            with open(output_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
                
            return output_dir
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise RuntimeError(f"Frame extraction failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please install: sudo pacman -S ffmpeg")
    
    def get_frame_paths(self, frames_dir: Path) -> list[Path]:
        """Get sorted list of frame paths."""
        frames = sorted(frames_dir.glob("frame_*.jpg"))
        return frames
    
    def get_frame_timestamps(self, frames_dir: Path) -> list[float]:
        """Get timestamp for each frame based on extraction FPS."""
        metadata_path = frames_dir / "metadata.json"
        
        if not metadata_path.exists():
            raise ValueError(f"No metadata found in {frames_dir}")
            
        with open(metadata_path) as f:
            metadata = json.load(f)
            
        fps = metadata["fps"]
        frame_count = metadata["frame_count"]
        
        # Calculate timestamp for each frame
        timestamps = [i / fps for i in range(frame_count)]
        return timestamps
    
    def cleanup(self, video_stem: Optional[str] = None):
        """Clean up extracted frames."""
        if video_stem:
            target_dir = self.frames_dir / video_stem
            if target_dir.exists():
                shutil.rmtree(target_dir)
                logger.info(f"Cleaned up frames for {video_stem}")
        else:
            # Clean all
            for subdir in self.frames_dir.iterdir():
                if subdir.is_dir():
                    shutil.rmtree(subdir)
            logger.info("Cleaned up all frames")