# Reddit Story → TikTok video

Builds a 1080×1920 TikTok-style Reddit story: AI narration, big pop-in captions,
a Reddit title card for the intro, and muted Minecraft parkour gameplay behind it.

The story lives in `story/story.json` (an original AITA post, ~5 min narrated).

## Setup

```bash
pip install piper-tts pillow yt-dlp
# voice model (Piper "ryan", high quality)
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json
# gameplay footage ("Minecraft Parkour Gameplay No Copyright")
yt-dlp -f "bv*[height<=1080][ext=mp4]" -o parkour.mp4 "https://youtu.be/u7kdVe8q5zs"
```

Requires `ffmpeg` with libass, and the Inter font (`fonts-inter` on Debian/Ubuntu).

## Render

```bash
python3 make_video.py --background parkour.mp4 --voice en_US-ryan-high.onnx
# → output/reddit_story.mp4
```

Options: `--speed 0.9` for faster narration, `--seed N` to pick different
gameplay segments, `--placeholder` to preview without footage.
