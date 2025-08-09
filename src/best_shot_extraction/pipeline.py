"""Main pipeline orchestrator for best-shot extraction."""

import yaml
import time
from pathlib import Path
import logging
import json
from typing import Dict, List, Tuple, Optional
import shutil

from .frame_extractor import FrameExtractor
from .scorers import CompositeScorer
from .temporal import TemporalProcessor
from .clip_extractor import ClipExtractor
from .diversity import DiversityFilter
from .utils import get_video_info, create_score_plot, create_contact_sheet

logger = logging.getLogger(__name__)


class Pipeline:
    """Main orchestrator for the best-shot extraction pipeline."""
    
    def __init__(self, config_path: Optional[Path] = None, use_cache: bool = True):
        """
        Initialize pipeline with configuration.
        
        Args:
            config_path: Path to YAML configuration file
            use_cache: Whether to use cached embeddings
        """
        # Load configuration
        if config_path:
            config_path = Path(config_path)
            if not config_path.exists():
                logger.warning(f"Config file not found: {config_path}, using defaults")
                config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
        else:
            config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from {config_path}")
        
        # Override cache setting if specified
        if not use_cache:
            self.config['pipeline']['use_cache'] = False
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize pipeline components based on configuration."""
        # Frame extractor
        self.frame_extractor = FrameExtractor()
        
        # Composite scorer with weights from config
        self.scorer = CompositeScorer(
            weights=self.config['scoring']['weights'],
            use_cache=self.config['pipeline']['use_cache']
        )
        
        # Set saliency prompts if specified
        if 'saliency' in self.scorer.scorers and 'saliency_prompts' in self.config['scoring']:
            self.scorer.scorers['saliency'].set_prompts(
                self.config['scoring']['saliency_prompts']
            )
        
        # Temporal processor
        self.temporal_processor = TemporalProcessor(
            smooth_window_seconds=self.config['temporal']['smooth_window_seconds'],
            min_peak_distance_seconds=self.config['temporal']['min_peak_distance_seconds'],
            fps=self.config['frame_extraction']['fps']
        )
        
        # Clip extractor
        self.clip_extractor = ClipExtractor(
            pre_roll_seconds=self.config['clips']['pre_roll_seconds'],
            post_roll_seconds=self.config['clips']['post_roll_seconds'],
            video_codec=self.config['clips']['video_codec'],
            crf=self.config['clips']['crf'],
            preset=self.config['clips']['preset']
        )
        
        # Diversity filter
        if self.config['diversity']['enabled']:
            self.diversity_filter = DiversityFilter(
                similarity_threshold=self.config['diversity']['similarity_threshold'],
                use_cache=self.config['pipeline']['use_cache']
            )
        else:
            self.diversity_filter = None
    
    def process(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        top_k: Optional[int] = None
    ) -> Dict:
        """
        Process a video through the full pipeline.
        
        Args:
            video_path: Path to input video
            output_dir: Directory for output clips and artifacts
            top_k: Number of clips to extract (overrides config)
            
        Returns:
            Dictionary with processing results
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # Setup output directory
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = Path("output") / video_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get top_k from config if not specified
        if top_k is None:
            top_k = self.config['pipeline']['top_k']
        
        logger.info(f"Processing video: {video_path.name}")
        logger.info(f"Output directory: {output_dir}")
        
        start_time = time.time()
        
        # Step 1: Get video info
        logger.info("Step 1: Analyzing video...")
        video_info = get_video_info(video_path)
        logger.info(f"  Duration: {video_info['duration']:.1f}s, "
                   f"Resolution: {video_info['width']}x{video_info['height']}, "
                   f"FPS: {video_info['fps']}")
        
        # Step 2: Extract frames
        logger.info("Step 2: Extracting frames...")
        frames_dir = self.frame_extractor.extract(
            video_path,
            fps=self.config['frame_extraction']['fps'],
            height=self.config['frame_extraction']['height']
        )
        frame_paths = self.frame_extractor.get_frame_paths(frames_dir)
        logger.info(f"  Extracted {len(frame_paths)} frames")
        
        # Step 3: Score frames
        logger.info("Step 3: Scoring frames...")
        scores = self.scorer.score_frames(frame_paths)
        scores_stats = {
            "mean": float(scores.mean()),
            "std": float(scores.std()),
            "min": float(scores.min()),
            "max": float(scores.max())
        }
        logger.info(f"  Score statistics: mean={scores_stats['mean']:.3f}, "
                   f"std={scores_stats['std']:.3f}")
        
        # Step 4: Temporal processing
        logger.info("Step 4: Temporal processing...")
        smoothed_scores, peaks = self.temporal_processor.process(scores, top_k)
        logger.info(f"  Found {len(peaks)} peaks")
        
        # Step 5: Diversity filtering
        if self.diversity_filter and len(peaks) > 1:
            logger.info("Step 5: Diversity filtering...")
            diversity_stats = self.diversity_filter.analyze_diversity(peaks, frame_paths)
            logger.info(f"  Diversity analysis: mean_distance={diversity_stats['mean_distance']:.3f}, "
                       f"similar_pairs={diversity_stats['num_similar_pairs']}")
            
            filtered_peaks = self.diversity_filter.filter_diverse(peaks, frame_paths, top_k)
            logger.info(f"  Filtered to {len(filtered_peaks)} diverse clips")
        else:
            filtered_peaks = peaks
            diversity_stats = None
        
        # Step 6: Extract clips
        logger.info("Step 6: Extracting clips...")
        clips_metadata = self.clip_extractor.extract_clips(
            video_path,
            filtered_peaks,
            output_dir,
            fps=self.config['frame_extraction']['fps'],
            name_prefix=video_path.stem
        )
        logger.info(f"  Extracted {len(clips_metadata)} clips")
        
        # Step 7: Generate visualizations and reports
        logger.info("Step 7: Generating outputs...")
        
        # Score plot
        if self.config['output']['save_score_plot']:
            plot_path = output_dir / "score_plot.png"
            create_score_plot(
                scores,
                smoothed_scores,
                filtered_peaks,
                fps=self.config['frame_extraction']['fps'],
                output_path=plot_path
            )
        
        # Contact sheet
        if self.config['output']['save_contact_sheet']:
            peak_frame_paths = [frame_paths[idx] for idx, _ in filtered_peaks]
            contact_path = output_dir / "contact_sheet.jpg"
            create_contact_sheet(
                peak_frame_paths,
                contact_path,
                columns=self.config['output']['contact_sheet_columns'],
                thumb_size=tuple(self.config['output']['contact_sheet_thumb_size'])
            )
        
        # Save comprehensive report
        if self.config['output']['save_metadata']:
            report = {
                "video_info": video_info,
                "config": self.config,
                "scores_statistics": scores_stats,
                "peaks_detected": len(peaks),
                "peaks_after_filtering": len(filtered_peaks),
                "clips": clips_metadata,
                "processing_time": time.time() - start_time
            }
            
            if diversity_stats:
                report["diversity_analysis"] = diversity_stats
            
            report_path = output_dir / "pipeline_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"  Saved report to {report_path}")
        
        # Cleanup frames if requested
        if self.config['pipeline'].get('cleanup_frames', False):
            logger.info("Cleaning up extracted frames...")
            self.frame_extractor.cleanup(video_path.stem)
        
        # Processing complete
        processing_time = time.time() - start_time
        logger.info(f"Pipeline complete! Processing time: {processing_time:.1f}s")
        
        return {
            "clips": clips_metadata,
            "output_dir": str(output_dir),
            "processing_time": processing_time,
            "scores_stats": scores_stats,
            "diversity_stats": diversity_stats
        }