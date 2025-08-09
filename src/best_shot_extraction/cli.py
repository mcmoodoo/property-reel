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
@click.option('--pattern', '-p', default='*.mp4', 
              help='File pattern to match')
def batch(directory, config, output_dir, pattern):
    """Process all videos in a directory."""
    from .pipeline import Pipeline
    
    pipeline = Pipeline(config)
    video_files = list(Path(directory).glob(pattern))
    
    logger.info(f"Found {len(video_files)} videos matching {pattern}")
    
    for video in video_files:
        logger.info(f"Processing: {video.name}")
        pipeline.process(video, output_dir)


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