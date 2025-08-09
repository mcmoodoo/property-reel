"""Visualization utilities for scores and clips."""

import numpy as np
from pathlib import Path
import logging
from typing import List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

# Optional imports for visualization
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not available, visualization features disabled")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available, contact sheet generation disabled")


def create_score_plot(
    scores: np.ndarray,
    smoothed_scores: Optional[np.ndarray] = None,
    peaks: Optional[List[Tuple[int, float]]] = None,
    fps: float = 3.0,
    output_path: Optional[Path] = None
) -> Optional[Path]:
    """
    Create a plot of scores over time.
    
    Args:
        scores: Original scores
        smoothed_scores: Smoothed scores (optional)
        peaks: List of (frame_index, score) peaks
        fps: Frames per second
        output_path: Where to save the plot
        
    Returns:
        Path to saved plot or None if matplotlib not available
    """
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("Cannot create plot: matplotlib not installed")
        return None
    
    # Create time axis
    time_axis = np.arange(len(scores)) / fps
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot original scores
    ax.plot(time_axis, scores, 'b-', alpha=0.3, label='Original scores')
    
    # Plot smoothed scores
    if smoothed_scores is not None:
        ax.plot(time_axis, smoothed_scores, 'b-', linewidth=2, label='Smoothed scores')
    
    # Mark peaks
    if peaks:
        peak_times = [idx / fps for idx, _ in peaks]
        peak_scores = [score for _, score in peaks]
        ax.scatter(peak_times, peak_scores, c='red', s=100, zorder=5, label='Selected peaks')
        
        # Add vertical lines at peaks
        for t, s in zip(peak_times, peak_scores):
            ax.axvline(x=t, color='red', alpha=0.2, linestyle='--')
            ax.annotate(f'{s:.2f}', xy=(t, s), xytext=(t, s + 0.05),
                       ha='center', fontsize=8)
    
    # Labels and formatting
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_ylabel('Score', fontsize=12)
    ax.set_title('Frame Scores Over Time', fontsize=14)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        logger.info(f"Saved score plot to {output_path}")
        plt.close()
        return output_path
    else:
        plt.show()
        return None


def create_contact_sheet(
    frame_paths: List[Path],
    output_path: Path,
    columns: int = 4,
    thumb_size: Tuple[int, int] = (320, 180),
    labels: Optional[List[str]] = None
) -> Optional[Path]:
    """
    Create a contact sheet of frames.
    
    Args:
        frame_paths: List of frame image paths
        output_path: Where to save the contact sheet
        columns: Number of columns in grid
        thumb_size: Size of each thumbnail (width, height)
        labels: Optional labels for each frame
        
    Returns:
        Path to saved contact sheet or None if PIL not available
    """
    if not PIL_AVAILABLE:
        logger.warning("Cannot create contact sheet: PIL not installed")
        return None
    
    if not frame_paths:
        logger.warning("No frames provided for contact sheet")
        return None
    
    # Calculate grid dimensions
    num_frames = len(frame_paths)
    rows = (num_frames + columns - 1) // columns
    
    # Create blank canvas
    sheet_width = columns * thumb_size[0]
    sheet_height = rows * thumb_size[1]
    
    if labels:
        # Add space for labels
        label_height = 20
        sheet_height += rows * label_height
    else:
        label_height = 0
    
    contact_sheet = Image.new('RGB', (sheet_width, sheet_height), 'black')
    
    # Place thumbnails
    for i, frame_path in enumerate(frame_paths):
        try:
            # Load and resize image
            img = Image.open(frame_path)
            img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            
            # Calculate position
            col = i % columns
            row = i // columns
            x = col * thumb_size[0] + (thumb_size[0] - img.width) // 2
            y = row * (thumb_size[1] + label_height) + (thumb_size[1] - img.height) // 2
            
            # Paste thumbnail
            contact_sheet.paste(img, (x, y))
            
            # Add label if provided
            if labels and i < len(labels):
                # Would need ImageDraw for text, skipping for simplicity
                pass
                
        except Exception as e:
            logger.warning(f"Failed to add frame {frame_path} to contact sheet: {e}")
    
    # Save contact sheet
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contact_sheet.save(output_path)
    logger.info(f"Saved contact sheet to {output_path}")
    
    return output_path


def save_pipeline_report(
    output_dir: Path,
    video_info: dict,
    scores_stats: dict,
    peaks: List[Tuple[int, float]],
    clips_metadata: List[dict],
    diversity_stats: Optional[dict] = None
):
    """
    Save a comprehensive pipeline report.
    
    Args:
        output_dir: Output directory
        video_info: Video metadata
        scores_stats: Scoring statistics
        peaks: Detected peaks
        clips_metadata: Extracted clips metadata
        diversity_stats: Diversity analysis results
    """
    report = {
        "video_info": video_info,
        "scores_statistics": scores_stats,
        "peaks_detected": len(peaks),
        "clips_extracted": len(clips_metadata),
        "clips": clips_metadata
    }
    
    if diversity_stats:
        report["diversity_analysis"] = diversity_stats
    
    # Save report
    report_path = output_dir / "pipeline_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Saved pipeline report to {report_path}")