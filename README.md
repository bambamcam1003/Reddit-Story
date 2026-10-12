# Reddit Story → TikTok video

Builds a 1080×1920 TikTok-style Reddit story: natural AI narration (Kokoro TTS), big pop-in captions,
a Reddit title card for the intro, and muted Minecraft parkour gameplay behind it.

The story lives in `story/story.json` (an original AITA post, ~5 min narrated).

## Setup

```bash
pip install kokoro-onnx soundfile pillow yt-dlp
# Kokoro voice model (~350 MB)
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
# gameplay footage ("Minecraft Parkour Gameplay No Copyright")
yt-dlp -f "bv*[height<=1080][ext=mp4]" -o parkour.mp4 "https://youtu.be/u7kdVe8q5zs"
```

Requires `ffmpeg` with libass, and the Inter font (`fonts-inter` on Debian/Ubuntu).

## Render

```bash
python3 make_video.py --background parkour.mp4 --kokoro-dir models
# → output/reddit_story.mp4
```

## Narrator voice

The voice matches the story's narrator: `af_heart` for a female narrator,
`am_michael` for a male one. It's read from `"narrator": "male" | "female"` in the
story JSON, or detected from clues like `(26F)`, `32M`, "I'm twenty six, female",
"my wife" / "my husband". Force any Kokoro voice with `--voice am_fenrir` etc.

Options: `--speed 1.2` for faster narration, `--seed N` to pick different
gameplay segments, `--placeholder` to preview without footage.
