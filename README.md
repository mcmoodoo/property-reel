# Best-Shot Extraction Pipeline

A CPU-optimized pipeline for extracting the best highlight clips from continuous video takes. Uses CLIP for aesthetic scoring, traditional computer vision for technical quality assessment, and temporal analysis to find the most compelling moments.

## Features

- **Multi-dimensional scoring**: Combines aesthetics (CLIP), sharpness, exposure, and subject saliency
- **Temporal smoothing**: Finds sustained high-quality moments, not just single good frames
- **Diversity filtering**: Ensures variety in selected clips using CLIP embeddings
- **CPU-optimized**: Designed to run efficiently on CPU with minimal dependencies
- **Configurable**: YAML-based configuration with presets for different video types
- **Caching**: Reuses CLIP embeddings across runs for faster processing

## Installation

### Prerequisites

- Python 3.10+
- FFmpeg (for video processing)
- UV package manager

On Arch Linux:
```bash
sudo pacman -S ffmpeg
pip install uv
```

### Setup

```bash
# Clone the repository
cd best-shot-extraction

# Create virtual environment and install dependencies
uv venv
uv pip install -e .

# For development dependencies
uv pip install -e ".[dev]"
```

## Quick Start

### Process a single video

```bash
# Using default settings
uv run best-shot process videos/aerial-shot.mp4

# With custom configuration
uv run best-shot process videos/interior-shot.mp4 --config config/interior.yaml

# Specify output directory and number of clips
uv run best-shot process videos/aerial-shot.mp4 --output-dir results --top-k 7
```

### Batch processing

```bash
# Process all MP4 files in a directory
uv run best-shot batch videos/

# With custom pattern
uv run best-shot batch videos/ --pattern "*.mov"
```

### Analyze without extraction

```bash
# Quick analysis to see scoring statistics
uv run best-shot analyze videos/aerial-shot.mp4
```

## Configuration

The pipeline uses YAML configuration files. Default presets are provided:

- `config/default.yaml` - General purpose settings
- `config/aerial.yaml` - Optimized for drone/aerial footage
- `config/interior.yaml` - Optimized for interior/architectural shots

### Key Configuration Parameters

```yaml
frame_extraction:
  fps: 3.0  # Frames per second to extract
  height: 720  # Target height for processing

scoring:
  weights:
    sharpness: 0.3
    exposure: -0.2  # Negative = penalty
    aesthetics: 0.4
    saliency: 0.1

temporal:
  smooth_window_seconds: 2.0
  min_peak_distance_seconds: 4.0

clips:
  pre_roll_seconds: 1.0
  post_roll_seconds: 2.0
  crf: 18  # Quality (lower = better)

diversity:
  enabled: true
  similarity_threshold: 0.12
```

## Pipeline Steps

1. **Frame Extraction**: Samples video at reduced FPS (e.g., 3 FPS)
2. **Per-Frame Scoring**: Evaluates aesthetics, sharpness, exposure, and saliency
3. **Temporal Smoothing**: Applies sliding window to find sustained quality
4. **Peak Detection**: Identifies best moments with minimum separation
5. **Clip Extraction**: Cuts video segments around peaks
6. **Diversity Filtering**: Removes near-duplicates using CLIP embeddings

## Output

The pipeline generates:

- **Highlight clips**: Individual MP4 files for each selected moment
- **Metadata JSON**: Detailed information about clips, scores, and parameters
- **Score plot**: Visualization of scores over time with selected peaks
- **Contact sheet**: Grid of thumbnails from selected moments

## Performance

On a typical CPU (laptop):
- 1-minute video: ~90-120 seconds processing time
- Memory usage: ~2-4 GB (including model loading)
- Cache speeds up repeated runs significantly

## Project Structure

```
best-shot-extraction/
├── src/best_shot_extraction/
│   ├── frame_extractor.py     # FFmpeg frame sampling
│   ├── scorers/               # Scoring modules
│   │   ├── aesthetics.py      # CLIP-based aesthetic scoring
│   │   ├── sharpness.py       # Laplacian variance
│   │   ├── exposure.py        # Histogram analysis
│   │   └── saliency.py        # Text-image similarity
│   ├── models/                # ML model management
│   │   └── clip_model.py      # CLIP singleton
│   ├── temporal.py            # Smoothing & peak detection
│   ├── clip_extractor.py      # Video clip extraction
│   ├── diversity.py           # Duplicate filtering
│   └── pipeline.py            # Main orchestrator
├── config/                    # Configuration presets
├── cache/                     # Embedding cache
├── output/                    # Generated clips
└── frames/                    # Temporary frames
```

## Advanced Usage

### Custom scoring weights

Create your own configuration file:

```yaml
# config/custom.yaml
scoring:
  weights:
    sharpness: 0.5  # Emphasize sharpness
    exposure: -0.1
    aesthetics: 0.3
    saliency: 0.1
```

### Video-specific prompts

For specialized content, customize saliency prompts:

```yaml
scoring:
  saliency_prompts:
    - "professional product photography"
    - "clean product shot on white background"
    - "detailed close-up of product"
```

## Troubleshooting

### FFmpeg not found
```bash
# Install on Arch Linux
sudo pacman -S ffmpeg

# Verify installation
ffmpeg -version
```

### Out of memory
- Reduce batch size in code
- Lower frame extraction resolution
- Process shorter video segments

### Slow processing
- Enable caching (default)
- Reduce frame extraction FPS
- Use lower resolution (480p)

## Development

### Running tests
```bash
uv run pytest tests/
```

### Code formatting
```bash
uv run black src/
uv run ruff check src/
```

## License

MIT

## Acknowledgments

- CLIP model by OpenAI
- LAION for aesthetic predictor research
- FFmpeg for video processing