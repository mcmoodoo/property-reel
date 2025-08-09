"""Extract video clips around peak moments."""

import subprocess
from pathlib import Path
import logging
from typing import List, Tuple, Dict, Optional
import json

logger = logging.getLogger(__name__)


class ClipExtractor:
    """Extract video clips using FFmpeg."""
    
    def __init__(
        self,
        pre_roll_seconds: float = 1.0,
        post_roll_seconds: float = 2.0,
        video_codec: str = "libx264",
        crf: int = 18,
        preset: str = "veryfast"
    ):
        """
        Initialize clip extractor.
        
        Args:
            pre_roll_seconds: Seconds before peak to include
            post_roll_seconds: Seconds after peak to include
            video_codec: Video codec for encoding
            crf: Constant Rate Factor for quality (lower = better)
            preset: Encoding preset (ultrafast, veryfast, fast, medium, slow)
        """
        self.pre_roll = pre_roll_seconds
        self.post_roll = post_roll_seconds
        self.video_codec = video_codec
        self.crf = crf
        self.preset = preset
        
        logger.info(f"Clip extractor initialized: "
                   f"duration={pre_roll_seconds + post_roll_seconds}s "
                   f"({pre_roll_seconds}s + {post_roll_seconds}s)")
    
    def extract_clip(
        self,
        video_path: Path,
        peak_time: float,
        output_path: Path,
        video_duration: Optional[float] = None,
        stabilize: bool = False
    ) -> Dict:
        """
        Extract a single clip around a peak moment.
        
        Args:
            video_path: Path to source video
            peak_time: Peak timestamp in seconds
            output_path: Path for output clip
            video_duration: Total video duration (auto-detect if None)
            stabilize: Apply video stabilization
            
        Returns:
            Dictionary with clip metadata
        """
        # Get video duration if not provided
        if video_duration is None:
            video_duration = self._get_video_duration(video_path)
        
        # Calculate clip boundaries
        start_time = max(0, peak_time - self.pre_roll)
        end_time = min(video_duration, peak_time + self.post_roll)
        duration = end_time - start_time
        
        logger.info(f"Extracting clip: {start_time:.1f}s - {end_time:.1f}s "
                   f"(peak at {peak_time:.1f}s)")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if stabilize:
            self._extract_with_stabilization(
                video_path, start_time, duration, output_path
            )
        else:
            self._extract_simple(
                video_path, start_time, duration, output_path
            )
        
        # Create metadata
        metadata = {
            "filename": output_path.name,
            "source_video": str(video_path),
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "peak_time": peak_time,
            "peak_time_in_clip": peak_time - start_time
        }
        
        return metadata
    
    def _extract_simple(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        output_path: Path
    ):
        """Extract clip without stabilization."""
        cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", self.video_codec,
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-c:a", "copy",  # Copy audio without re-encoding
            "-loglevel", "error",
            "-stats",
            "-y",  # Overwrite output
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"Extracted clip to {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr}")
            raise RuntimeError(f"Clip extraction failed: {e.stderr}")
    
    def _extract_with_stabilization(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        output_path: Path
    ):
        """Extract clip with video stabilization."""
        # First pass: detect motion
        temp_file = output_path.with_suffix('.trf')
        
        cmd1 = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duration),
            "-vf", f"vidstabdetect=stepsize=6:shakiness=8:result={temp_file}",
            "-f", "null",
            "-loglevel", "error",
            "-"
        ]
        
        try:
            subprocess.run(cmd1, check=True, capture_output=True, text=True)
            
            # Second pass: apply stabilization
            cmd2 = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", str(video_path),
                "-t", str(duration),
                "-vf", f"vidstabtransform=input={temp_file}:zoom=1:smoothing=30",
                "-c:v", self.video_codec,
                "-crf", str(self.crf),
                "-preset", self.preset,
                "-c:a", "copy",
                "-loglevel", "error",
                "-stats",
                "-y",
                str(output_path)
            ]
            
            subprocess.run(cmd2, check=True, capture_output=True, text=True)
            
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
                
            logger.debug(f"Extracted stabilized clip to {output_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Stabilization failed: {e.stderr}")
            # Fall back to simple extraction
            logger.warning("Falling back to non-stabilized extraction")
            self._extract_simple(video_path, start_time, duration, output_path)
    
    def extract_clips(
        self,
        video_path: Path,
        peaks: List[Tuple[int, float]],
        output_dir: Path,
        fps: float = 3.0,
        name_prefix: str = "clip"
    ) -> List[Dict]:
        """
        Extract multiple clips from peaks.
        
        Args:
            video_path: Path to source video
            peaks: List of (frame_index, score) tuples
            output_dir: Directory for output clips
            fps: Frame rate used for frame extraction
            name_prefix: Prefix for clip filenames
            
        Returns:
            List of clip metadata dictionaries
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        video_duration = self._get_video_duration(video_path)
        
        clips_metadata = []
        
        for i, (frame_idx, score) in enumerate(peaks, 1):
            # Convert frame index to timestamp
            peak_time = frame_idx / fps
            
            # Generate output filename
            output_path = output_dir / f"{name_prefix}_{i:03d}.mp4"
            
            # Extract clip
            metadata = self.extract_clip(
                video_path,
                peak_time,
                output_path,
                video_duration
            )
            
            # Add score to metadata
            metadata["score"] = score
            metadata["peak_frame"] = frame_idx
            
            clips_metadata.append(metadata)
            
            logger.info(f"Extracted clip {i}/{len(peaks)}: {output_path.name}")
        
        # Save metadata to JSON
        metadata_path = output_dir / "clips_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump({
                "source_video": str(video_path),
                "clips": clips_metadata,
                "extraction_params": {
                    "pre_roll": self.pre_roll,
                    "post_roll": self.post_roll,
                    "codec": self.video_codec,
                    "crf": self.crf,
                    "preset": self.preset
                }
            }, f, indent=2)
        
        logger.info(f"Saved metadata to {metadata_path}")
        
        return clips_metadata
    
    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get video duration: {e}")
            # Fallback: assume 60 seconds
            return 60.0