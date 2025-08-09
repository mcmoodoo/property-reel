# Best-Shot Extraction Pipeline - Detailed Steps

## Overview
A pipeline for extracting the best highlight clips from continuous take videos, identifying and extracting the highest quality moments based on aesthetic, technical, and compositional criteria.

## Step 1: Frame Sampling/Extraction

### Purpose
Convert the input video into individual frame images at a reduced framerate for efficient processing.

### Process
- **Input**: Single continuous take video file (e.g., `aerial-shot.mp4`)
- **Sampling rate**: 2-5 FPS (3 FPS recommended for most cases)
- **Resolution**: Downscale to 720p height while maintaining aspect ratio
- **Output format**: Sequential JPEG images

### Command
```bash
ffmpeg -i input_video.mp4 -vf fps=3,scale=-2:720 frames/frame_%06d.jpg
```

### Parameters
- `fps=3`: Extract 3 frames per second
- `scale=-2:720`: Scale to 720p height, `-2` maintains aspect ratio divisible by 2
- `frame_%06d.jpg`: Output pattern (frame_000001.jpg, frame_000002.jpg, etc.)

### Result
- 1-minute video at 30fps (1,800 frames) → 180 frames at 3fps
- Reduces data by 90% while maintaining temporal coverage
- Creates manageable set of images for batch processing

---

## Step 2: Per-Frame Scoring

### Purpose
Evaluate each extracted frame across multiple quality dimensions to create a composite quality score.

### Scoring Components

#### 2.1 Aesthetics Score
- **Method**: CLIP embeddings → aesthetic predictor model
- **Tool options**: 
  - LAION aesthetic predictor
  - Custom trained MLP on aesthetic datasets
- **Output**: Score 0.0-1.0 representing visual appeal
- **Weight**: `w_a` (typically 0.4)

#### 2.2 Sharpness Score
- **Method**: Variance of Laplacian
- **Implementation**:
  ```python
  laplacian = cv2.Laplacian(gray_frame, cv2.CV_64F)
  sharpness = laplacian.var()
  ```
- **Output**: Higher variance = sharper image
- **Normalization**: Scale to 0-1 range across all frames
- **Weight**: `w_s` (typically 0.3)

#### 2.3 Exposure Penalty
- **Method**: Histogram analysis
- **Checks**:
  - Blown highlights: >99% pixels near white (250-255)
  - Crushed blacks: <1% pixels near black (0-5)
- **Output**: Penalty score 0-1 (higher = worse exposure)
- **Weight**: `w_e` (typically 0.2, negative weight)

#### 2.4 Subject/Saliency Score (Optional)
- **Method**: CLIP similarity to text prompt
- **Example prompts**:
  - "well-lit interior wide shot"
  - "dramatic aerial landscape"
  - "sharp architectural details"
- **Output**: Cosine similarity score -1 to 1
- **Weight**: `w_c` (typically 0.1-0.3 when used)

### Score Combination
```
S[frame_i] = w_a * Aesthetics + w_s * Sharpness - w_e * ExposurePenalty + w_c * CLIPsim
```

### Result
- Single array of scores: `[0.72, 0.68, 0.81, 0.79, 0.65, ...]`
- One score per frame
- Length equals number of extracted frames
- Represents instantaneous quality at each sampled moment

---

## Step 3: Temporal Smoothing

### Purpose
Convert per-frame scores into scores for sustained moments, eliminating isolated spikes and finding consistently good segments.

### Process
- **Window size**: 2-3 seconds (6-9 frames at 3 FPS)
- **Method**: Sliding window mean
- **Formula**: `S_smooth[t] = mean(S[t−W/2 : t+W/2])`

### Implementation Details
- **Edge handling**: Use smaller windows at video start/end
- **Window examples**:
  - 2-second window at 3 FPS = 6 frames
  - 3-second window at 3 FPS = 9 frames

### Example
```
Original:  [0.72, 0.68, 0.81, 0.79, 0.65, 0.83, 0.77, 0.70, 0.74]
              ↓     ↓     ↓     ↓     ↓     ↓     ↓     ↓     ↓
Smoothed:  [0.70, 0.73, 0.75, 0.75, 0.74, 0.76, 0.75, 0.73, 0.72]
```

### Result
- Smoothed score array of same length as original
- Represents quality of multi-second "moments" rather than frames
- Eliminates noisy variations
- Preserves general quality trends

---

## Step 4: Peak Detection / Finding Moments

### Purpose
Identify the K best moments in the video as anchor points for clip extraction.

### Process

#### 4.1 Find Local Maxima
- **Definition**: Points where `S_smooth[t] > S_smooth[t-1]` and `S_smooth[t] > S_smooth[t+1]`
- **Implementation**: Use scipy.signal.find_peaks or similar

#### 4.2 Apply Minimum Separation
- **Distance**: 4-6 seconds minimum between peaks (12-18 frames at 3 FPS)
- **Reason**: Prevents overlapping clips and ensures diversity
- **Method**: If peaks are too close, keep only the higher one

#### 4.3 Select Top-K Peaks
- **Sort** by score value (descending)
- **Select** top K peaks (typically K=3-7)
- **Store** both frame index and score

### Example Output
```python
peaks = [
    (frame_24, 0.85),  # 8.0 seconds - highest quality moment
    (frame_51, 0.82),  # 17.0 seconds - second best
    (frame_12, 0.78),  # 4.0 seconds - third best
    (frame_89, 0.76),  # 29.7 seconds
    (frame_142, 0.74)  # 47.3 seconds
]
```

### Result
- List of K frame indices representing best moments
- Each peak is center of a high-quality segment
- Guaranteed minimum temporal separation
- Sorted by quality score

---

## Step 5: Clip Extraction

### Purpose
Cut video segments around each peak moment to create individual highlight clips.

### Clip Boundaries
- **Pre-roll** (`L_pre`): 1 second before peak
- **Post-roll** (`L_post`): 2 seconds after peak
- **Total duration**: 3 seconds (adjustable to 3-7 seconds)
- **Formula**: `[t* - L_pre, t* + L_post]`

### Extraction Process

#### 5.1 Calculate Timestamps
For peak at frame F (at 3 FPS):
```
peak_time = F / 3.0
start_time = max(0, peak_time - 1.0)
end_time = min(video_duration, peak_time + 2.0)
duration = end_time - start_time
```

#### 5.2 FFmpeg Extraction
```bash
ffmpeg -ss <start_time> -i input_video.mp4 -t <duration> \
       -c:v libx264 -crf 18 -preset veryfast \
       highlight_<n>.mp4
```

#### 5.3 Optional Stabilization
```bash
# Two-pass stabilization
ffmpeg -i highlight_<n>.mp4 -vf vidstabdetect=stepsize=6 -f null -
ffmpeg -i highlight_<n>.mp4 -vf vidstabtransform=smoothing=30 \
       stabilized_<n>.mp4
```

### Encoding Parameters
- `-c:v libx264`: H.264 codec for compatibility
- `-crf 18`: High quality (lower = better, 18-23 recommended)
- `-preset veryfast`: Balance between speed and compression
- Audio: Copy original audio track with `-c:a copy`

### Result
- K individual video files (highlight_1.mp4, highlight_2.mp4, etc.)
- Each 3-7 seconds long
- Centered on highest-quality moments
- Original quality preserved

---

## Step 6: Diversity Filtering

### Purpose
Remove near-duplicate clips to ensure variety in the final selection.

### Process

#### 6.1 Extract Representative Frames
- Use peak frame from each clip
- Or use middle frame of each clip
- Load as images for embedding

#### 6.2 Generate CLIP Embeddings
```python
for each clip:
    peak_frame = load_image(f"frames/frame_{peak_index:06d}.jpg")
    embedding = CLIP.encode_image(peak_frame)
    embeddings.append(embedding)
```

#### 6.3 Calculate Pairwise Distances
- **Metric**: Cosine distance
- **Formula**: `dist = 1 - cosine_similarity(emb_i, emb_j)`
- **Range**: 0 (identical) to 2 (opposite)

#### 6.4 Greedy Selection
```python
final_clips = [highest_scored_clip]
for clip in remaining_clips_by_score:
    if all(distance(clip, kept) > threshold for kept in final_clips):
        final_clips.append(clip)
```

### Parameters
- **Threshold** (`τ`): 0.12-0.15 typically
- **Maximum clips**: Stop at K clips or when no diverse clips remain

### Example
```
Clip pairs and distances:
clip_1 ↔ clip_2: 0.08  ❌ Too similar
clip_1 ↔ clip_3: 0.25  ✓ Different enough
clip_1 ↔ clip_4: 0.31  ✓ Different enough
clip_2 ↔ clip_3: 0.18  ✓ Different enough

Final selection: [clip_1, clip_3, clip_4]  # clip_2 removed as duplicate
```

### Result
- Reduced set of clips (typically 60-80% of original K)
- Each clip shows distinctly different content
- Maintains quality ranking where possible
- Ensures variety in final highlight reel

---

## Pipeline Configuration Parameters

### Global Parameters
- `input_video`: Path to continuous take video
- `output_dir`: Directory for clips and intermediate files
- `K`: Number of top clips to extract (before diversity filter)
- `clip_duration`: Length of each clip (3-7 seconds)

### Sampling Parameters
- `sample_fps`: Frame extraction rate (2-5 FPS)
- `sample_height`: Target height for processing (480-1080p)

### Scoring Weights
- `w_aesthetics`: 0.3-0.5
- `w_sharpness`: 0.2-0.4
- `w_exposure`: 0.1-0.3 (negative)
- `w_saliency`: 0.0-0.3 (optional)

### Temporal Parameters
- `smooth_window`: 2-3 seconds
- `min_peak_distance`: 4-6 seconds
- `clip_pre_roll`: 0.5-2 seconds
- `clip_post_roll`: 1-3 seconds

### Diversity Parameters
- `similarity_threshold`: 0.10-0.20
- `max_similar_clips`: 1-2

---

## Output Artifacts

### Primary Outputs
1. **Highlight clips**: `highlights/clip_001.mp4`, `clip_002.mp4`, etc.
2. **Metadata JSON**: Timestamps, scores, and parameters for each clip
3. **Contact sheet**: Grid of representative frames from each clip

### Optional Outputs
1. **Score visualization**: Graph showing scores over time with selected peaks
2. **Full timeline**: CSV with per-frame scores and smoothed values
3. **Similarity matrix**: Pairwise distances between all candidate clips

### Example Metadata
```json
{
  "clips": [
    {
      "filename": "clip_001.mp4",
      "source_video": "aerial-shot.mp4",
      "start_time": 7.0,
      "duration": 3.0,
      "peak_frame": 24,
      "score": 0.85,
      "components": {
        "aesthetics": 0.92,
        "sharpness": 0.88,
        "exposure": 0.05,
        "saliency": 0.75
      }
    }
  ],
  "parameters": {
    "sample_fps": 3,
    "smooth_window": 2.0,
    "weights": {...}
  }
}
```

---

## Performance Considerations

### Processing Time Estimates
- Frame extraction: ~10% of video duration
- CLIP processing: ~1-2 seconds per frame
- Scoring: <0.1 seconds per frame
- Peak detection: <1 second total
- Clip extraction: ~20% of video duration per clip

### Memory Requirements
- Frame storage: ~100KB per frame (720p JPEG)
- Embeddings: 512-2048 floats per frame
- Total for 1-minute video: ~50-100MB

### Optimization Strategies
1. **Batch processing**: Process frames in GPU batches for CLIP
2. **Caching**: Store embeddings for reuse
3. **Parallel extraction**: Extract clips in parallel
4. **Lower resolution**: Use 480p for scoring, full res for extraction
5. **Adaptive sampling**: Higher FPS only during motion

---

## Error Handling

### Common Issues and Solutions

1. **No peaks found**
   - Lower quality thresholds
   - Reduce minimum peak distance
   - Check if video is too short

2. **All clips too similar**
   - Increase diversity threshold
   - Extend minimum peak distance
   - Add more weight to saliency scoring

3. **Poor quality scores**
   - Adjust scoring weights
   - Check video quality (resolution, compression)
   - Verify frame extraction worked correctly

4. **Memory issues**
   - Reduce sampling FPS
   - Lower processing resolution
   - Process in chunks for long videos

---

## Extensions and Variations

### Advanced Features
1. **Motion-aware scoring**: Add optical flow analysis
2. **Audio quality**: Include audio level/clarity scores
3. **Face detection**: Prioritize clips with faces in focus
4. **Scene classification**: Different weights for indoor/outdoor
5. **Temporal coherence**: Ensure smooth clip boundaries

### Alternative Approaches
1. **ML-based**: Train end-to-end model on human-rated clips
2. **Interactive**: User provides feedback to refine selection
3. **Template matching**: Compare to reference "good" clips
4. **Multi-video**: Extract best clips across multiple takes