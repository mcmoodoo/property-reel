# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a CPU-optimized pipeline for extracting the best highlight clips from continuous video takes. The system uses CLIP for aesthetic scoring, traditional computer vision for technical quality assessment, and temporal analysis to find the most compelling moments from long-form video content.

## Development Commands

### Environment Setup
```bash
# Install UV package manager first (if not installed)
pip install uv

# Create virtual environment and install dependencies
uv venv
uv pip install -e .

# For development with linting/formatting tools
uv pip install -e ".[dev]"
```

### Running the Pipeline
```bash
# Process a single video with default settings
uv run best-shot process videos/aerial-shot.mp4

# With custom configuration
uv run best-shot process videos/interior-shot.mp4 --config config/interior.yaml

# Specify output directory and number of clips
uv run best-shot process videos/aerial-shot.mp4 --output-dir results --top-k 7

# Batch process all videos in directory (auto-detects .mp4, .MP4, .mov, etc.)
uv run best-shot batch videos/

# Process only specific pattern
uv run best-shot batch videos/ --pattern "*.MP4"

# Stop on first error instead of continuing
uv run best-shot batch videos/ --no-continue-on-error

# Quick analysis without extraction
uv run best-shot analyze videos/aerial-shot.mp4
```

### Testing and Code Quality
```bash
# Run tests
uv run pytest tests/

# Code formatting
uv run black src/

# Linting
uv run ruff check src/
```

## Architecture Overview

The pipeline follows a 6-step modular architecture:

### Core Pipeline Components (`src/best_shot_extraction/`)

1. **`pipeline.py`** - Main orchestrator that coordinates all processing steps
2. **`frame_extractor.py`** - Extracts frames from video using FFmpeg at reduced FPS (typically 3 FPS)
3. **`scorers/`** - Modular scoring system with multiple quality assessments:
   - `composite.py` - Combines multiple scorers with configurable weights
   - `aesthetics.py` - CLIP-based aesthetic scoring using LAION aesthetic predictor
   - `sharpness.py` - Laplacian variance for focus quality
   - `exposure.py` - Histogram analysis to penalize blown highlights/crushed blacks
   - `saliency.py` - CLIP text-image similarity for content relevance
4. **`temporal.py`** - Temporal smoothing and peak detection to find sustained quality moments
5. **`clip_extractor.py`** - Extracts video clips around detected peaks using FFmpeg
6. **`diversity.py`** - Removes near-duplicate clips using CLIP embeddings and cosine similarity

### Supporting Modules
- **`models/clip_model.py`** - Singleton CLIP model management with caching
- **`utils/`** - Video utilities and visualization tools
- **`cli.py`** - Command-line interface with Click

### Configuration System
The pipeline uses YAML-based configuration with presets for different video types:
- `config/default.yaml` - General purpose settings
- `config/aerial.yaml` - Optimized for drone/aerial footage  
- `config/interior.yaml` - Optimized for interior/architectural shots

## Key Design Patterns

### Scorer Architecture
All scorers inherit from `BaseScorer` and implement a consistent interface. The `CompositeScorer` combines multiple scorers using weighted averaging, allowing for easy experimentation with different quality metrics.

### Caching Strategy
CLIP embeddings are cached to disk (in `cache/` directory) to speed up repeated runs on the same video. Cache files are named by frame content hash for consistency.

### Temporal Processing
The pipeline applies sliding window smoothing (default 2-3 seconds) to eliminate noisy score variations, then uses peak detection with minimum separation constraints (4-6 seconds) to ensure diverse clip selection.

### Output Structure
Each processed video generates:
- Individual MP4 clips (`output/{video_name}_001.mp4`, etc.)
- JSON metadata with scores and parameters (`pipeline_report.json`)
- Score visualization plot (`score_plot.png`)
- Contact sheet of thumbnails (`contact_sheet.jpg`)

## Dependencies and Environment

- **Python 3.10+** required
- **FFmpeg** required for video processing
- **PyTorch with CPU-optimized setup** via UV's index configuration
- **CLIP models** downloaded automatically on first use
- Uses CPU-only inference for broader compatibility

The project uses UV package manager with a CPU-optimized PyTorch index for efficient installation without CUDA dependencies.