"""Command-line interface for best-shot extraction."""

import click
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@click.group()
def main():
    """Best-shot extraction pipeline for continuous video takes."""
    pass


@main.command()
@click.argument('video_path', type=click.Path(exists=True, path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path), 
              default='config/default.yaml', help='Configuration file path')
@click.option('--output-dir', '-o', type=click.Path(path_type=Path), 
              default='output', help='Output directory for clips')
@click.option('--top-k', '-k', type=int, default=5, 
              help='Number of clips to extract')
@click.option('--cache/--no-cache', default=True, 
              help='Use cached embeddings if available')
def process(video_path, config, output_dir, top_k, cache):
    """Process a single video to extract best shots."""
    from .pipeline import Pipeline
    
    logger.info(f"Processing video: {video_path}")
    logger.info(f"Config: {config}, Output: {output_dir}, Top-K: {top_k}")
    
    pipeline = Pipeline(config, use_cache=cache)
    results = pipeline.process(video_path, output_dir, top_k)
    
    logger.info(f"Extracted {len(results['clips'])} clips to {output_dir}")
    for i, clip in enumerate(results['clips'], 1):
        logger.info(f"  Clip {i}: {clip['filename']} (score: {clip['score']:.3f})")


@main.command()
@click.argument('directory', type=click.Path(exists=True, path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path),
              default='config/default.yaml', help='Configuration file path')
@click.option('--output-dir', '-o', type=click.Path(path_type=Path),
              default='output', help='Output directory for clips')
@click.option('--pattern', '-p', default='*.[mM][pP]4', 
              help='File pattern to match (supports both .mp4 and .MP4)')
@click.option('--continue-on-error', is_flag=True, default=True,
              help='Continue processing other videos if one fails')
def batch(directory, config, output_dir, pattern, continue_on_error):
    """Process all videos in a directory."""
    from .pipeline import Pipeline
    import traceback
    import time
    
    batch_start_time = time.time()
    pipeline = Pipeline(config)
    
    # Support multiple patterns for common video formats
    patterns = [pattern]
    if pattern == '*.[mM][pP]4':  # Default case
        patterns = ['*.mp4', '*.MP4', '*.mov', '*.MOV', '*.avi', '*.AVI']
    
    # Collect all video files
    video_files = []
    for p in patterns:
        video_files.extend(Path(directory).glob(p))
    
    # Remove duplicates and sort
    video_files = sorted(set(video_files))
    
    logger.info(f"Found {len(video_files)} video files")
    logger.info(f"Patterns: {patterns}")
    
    if not video_files:
        logger.warning("No video files found! Check the pattern and directory.")
        return
    
    # Track results
    successful = []
    failed = []
    
    for i, video in enumerate(video_files, 1):
        try:
            logger.info(f"Processing {i}/{len(video_files)}: {video.name}")
            
            # Create individual output directory for this video
            video_output_dir = Path(output_dir) / video.stem
            
            results = pipeline.process(video, video_output_dir)
            
            logger.info(f"✓ Success: {video.name} -> {len(results['clips'])} clips")
            successful.append(video.name)
            
        except Exception as e:
            error_msg = f"✗ Failed: {video.name} - {str(e)}"
            logger.error(error_msg)
            failed.append((video.name, str(e)))
            
            if not continue_on_error:
                logger.error("Stopping batch processing due to error.")
                break
            
            # Log full traceback in debug mode
            logger.debug(f"Full error trace for {video.name}:")
            logger.debug(traceback.format_exc())
    
    # Calculate total time
    batch_end_time = time.time()
    total_time = batch_end_time - batch_start_time
    
    # Summary
    logger.info("=" * 60)
    logger.info("BATCH PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total videos: {len(video_files)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")
    logger.info(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    
    if successful:
        total_clips = 0
        logger.info("\nSuccessful videos:")
        for video in successful:
            logger.info(f"  ✓ {video}")
        
        # Calculate clips per video average
        try:
            # Count total clips generated
            output_path = Path(output_dir)
            if output_path.exists():
                total_clips = len(list(output_path.rglob("*.mp4")))
                if total_clips > 0:
                    avg_clips_per_video = total_clips / len(successful)
                    logger.info(f"\nTotal clips generated: {total_clips}")
                    logger.info(f"Average clips per video: {avg_clips_per_video:.1f}")
        except Exception:
            pass  # Don't fail if we can't count clips
    
    if failed:
        logger.info("\nFailed videos:")
        for video, error in failed:
            logger.info(f"  ✗ {video}: {error}")
    
    # Performance stats
    if successful:
        avg_time_per_video = total_time / len(successful)
        logger.info(f"\nPerformance: {avg_time_per_video:.1f}s per video average")
    
    if failed:
        logger.warning(f"\n{len(failed)} videos failed processing. Check logs above for details.")
    else:
        logger.info("\nAll videos processed successfully!")


@main.command()
@click.argument('video_path', type=click.Path(exists=True, path_type=Path))
def analyze(video_path):
    """Analyze a video and show scoring without extraction."""
    from .utils.video import get_video_info
    from .frame_extractor import FrameExtractor
    from .scorers import CompositeScorer
    
    info = get_video_info(video_path)
    logger.info(f"Video: {video_path.name}")
    logger.info(f"  Duration: {info['duration']:.1f}s")
    logger.info(f"  Resolution: {info['width']}x{info['height']}")
    logger.info(f"  FPS: {info['fps']}")
    
    # Quick frame analysis
    extractor = FrameExtractor()
    frames_dir = extractor.extract(video_path, fps=1)  # 1 FPS for quick analysis
    
    scorer = CompositeScorer()
    scores = scorer.score_frames(frames_dir)
    
    logger.info(f"Score statistics:")
    logger.info(f"  Mean: {scores.mean():.3f}")
    logger.info(f"  Std: {scores.std():.3f}")
    logger.info(f"  Max: {scores.max():.3f}")
    logger.info(f"  Min: {scores.min():.3f}")


if __name__ == '__main__':
    main()