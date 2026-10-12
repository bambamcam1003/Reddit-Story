# Project manifest: Reddit Story → TikTok video

A handoff for continuing this project in Claude Code (or by hand). It covers what
exists, how it was built, every outside resource used, and the workarounds needed.

## Goal

Make TikTok-ready (1080×1920 vertical) Reddit-story videos of about 5 minutes.
Each has an AI voiceover, big pop-in captions and a Reddit-style title card, over
muted Minecraft parkour gameplay. The voice should match the narrator's gender.

## Current state

- The finished video exists for the story in `story/story.json`, an original AITA
  post about a sister demanding a lake house the narrator inherited. It runs 5:12.
- Outputs (gitignored, so they're only in the session that made them):
  - `output/reddit_story.mp4`: 1080×1920, about 240 MB
  - `output/reddit_story_small.mp4`: 720×1280, under 30 MB, for sending or uploading
- Git branch: `ccr-f48ada7b-c7euao` on `bambamcam1003/reddit-story`

| Commit | What it did |
|---|---|
| `e33f5b2` | Generator, story, title card, captions, background cutting (Piper voice) |
| `ad44fc6` | Switched to Kokoro TTS; auto male or female voice |
| `73b97a7` | misaki pronunciation, controlled pauses, Reddit acronyms spoken in full |

## Files

| Path | Purpose |
|---|---|
| `make_video.py` | The whole pipeline (see below) |
| `story/story.json` | Story data: `narrator`, `subreddit`, `username`, `title`, `upvotes`, `comments`, `body` (list of paragraphs) |
| `README.md` | Short setup and usage notes |
| `.gitignore` | Leaves out `build/`, `models/`, `output/`, `*.mp4`, `*.onnx`, `*.bin`, `*.wav` |

## Pipeline (`make_video.py`)

1. **Narrator gender.** The `"narrator"` field in the story JSON decides it. If
   it's missing, the script looks for clues in the text: `(26F)`, `32M`,
   "I'm twenty six, female", "I'm a dad", "my wife" or "my husband". If it finds
   none, it uses the female voice and prints a warning. Voices: female `af_heart`,
   male `am_michael`.
2. **Spoken text.** `spoken()` spells out Reddit shorthand: AITA/AITAH, WIBTA,
   TIFU, YTA, NTA, ESH, NAH, TL;DR, MIL/FIL/SIL/BIL, BF/GF, DH/DW, IMO and TBH,
   plus `(26F)` → "26, female". The captions use this spoken text; the title card
   keeps the original.
3. **Narration.** Each sentence goes through misaki, Kokoro's native
   pronunciation dictionary, to get phonemes. Kokoro then speaks them
   (`is_phonemes=True`, speed 1.05). Pauses are 0.32 s after a sentence, 0.65 s
   after a paragraph and 0.9 s after the title. The output is
   `build/narration.wav` (24 kHz mono).
4. **Captions.** Word timings are estimated by spreading each sentence's length
   across its words, weighted by word length plus extra time before commas. They
   go in an ASS subtitle file: Inter Black, 92 px, white with a black outline,
   centered, up to 3 words at a time, pop-in scale animation, and about 18% of
   lines in yellow.
5. **Title card.** A Pillow-drawn PNG of a white rounded Reddit post (avatar,
   subreddit, username, wrapped title, upvotes and comments). It's overlaid only
   while the title is read.
6. **Background.** Clips of about 45 s each come from random points in the
   source video (seeded with `--seed`, default 7). Each is scaled to 1920 px
   tall, center-cropped to 1080×1920 at 30 fps and muted, then they're joined.
7. **Final mux.** ffmpeg overlays the card, burns in the captions and adds the
   narration as 192 kbps AAC. Encoding is x264 CRF 20 with faststart.

```bash
python3 make_video.py --background parkour.mp4 --kokoro-dir models \
  [--story story/story.json] [--voice am_fenrir] [--speed 1.1] [--seed 3] \
  [--out output/reddit_story.mp4] [--placeholder]
```

Compressed copy under 30 MB (two-pass encode; the bitrate here is for 5:12):
```bash
ffmpeg -y -i output/reddit_story.mp4 -vf scale=720:1280 -c:v libx264 -preset faster -b:v 665k -pass 1 -an -f mp4 /dev/null
ffmpeg -y -i output/reddit_story.mp4 -vf scale=720:1280 -c:v libx264 -preset faster -b:v 665k -pass 2 -c:a aac -b:a 64k -movflags +faststart output/reddit_story_small.mp4
```

## Resources used

| Resource | Source | Notes |
|---|---|---|
| Gameplay footage (used) | The user's Google Drive: `https://drive.google.com/file/d/1Pe7SnuYz4cto8ZAsi9yeFMe3-9u9h60K/view` | 811 MB, 2 h 29 m, **640×360** h264. Direct download: `https://drive.usercontent.google.com/download?id=1Pe7SnuYz4cto8ZAsi9yeFMe3-9u9h60K&export=download&confirm=t` |
| Gameplay (first request, not used) | YouTube `https://youtu.be/u7kdVe8q5zs`, "Minecraft Parkour Gameplay No Copyright", 31 min | YouTube blocked the download from the cloud server (403). Should work locally with yt-dlp |
| Kokoro TTS model | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx` (325 MB) | Put in `models/` |
| Kokoro voices | `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin` (28 MB) | Put in `models/` |
| spaCy English model (needed by misaki) | `https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl` | pip install |
| Font | Inter (`/usr/share/fonts/opentype/inter/`: Black, Bold, Medium) | Debian/Ubuntu: `apt install fonts-inter`. On Mac or Windows, install Inter and change the `FONT_*` paths and `fontsdir` in `make_video.py` |
| Piper "ryan" voice (dropped) | rhasspy/piper-voices on Hugging Face | First version only; replaced by Kokoro |

### Software versions it ran on
Python 3.13.16, ffmpeg 6.1.1 (needs libass), kokoro-onnx 0.6.1, onnxruntime
1.29.0, misaki 0.7.4, spacy 3.8.16, espeakng-loader 0.2.4, num2words 0.5.14,
docopt-ng 0.9.0, numpy 2.5.3, pillow 12.3.0, soundfile 0.14.0, yt-dlp 2026.8.19.

## Setup (including workarounds)

```bash
pip install kokoro-onnx soundfile pillow yt-dlp spacy regex addict docopt-ng
# misaki[en] fails to install on Python 3.13: its dependency `docopt` won't build.
# Install misaki and num2words without dependencies; docopt-ng provides `docopt`.
pip install --no-deps misaki num2words
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
```

Other gotchas:
- **espeak isn't installed system-wide.** `make_phonemizer()` points the
  phonemizer at the espeak-ng copy that comes with `espeakng_loader`, so nothing
  extra is needed.
- **Don't let Kokoro phonemize on its own.** Its built-in espeak path
  mispronounced "lawyer", "lake" and "house" and dropped pauses. That's why the
  phonemes come from misaki.
- **edge-tts (Microsoft voices)** didn't work in the cloud session because it uses
  a websocket connection the proxy blocked. It may work locally and could be an
  alternative voice.
- **YouTube downloads:** if yt-dlp gets 403 or "confirm you're not a bot", update
  yt-dlp, install `deno` (yt-dlp uses it to solve YouTube's download checks), or
  use `--cookies-from-browser chrome`.

## Known limitations / ideas for next steps

- The gameplay source is only 360p, so the full-screen crop is upscaled about 5×.
  A 1080p+ parkour video would look sharper.
- Caption timing is estimated, not measured. Forced alignment (e.g. whisperX or
  aeneas) would make the captions match the voice exactly.
- Nobody has listened to the audio from the pronunciation fix yet. If a word
  still sounds wrong, add an override: misaki accepts `[word](/phonemes/)`
  markup, or extend `SPOKEN`.
- Ideas: background music under the voice, a "Part 1/2" split for a 3-minute
  limit, several stories per run, a random Minecraft clip per video, an end
  card ("Follow for part 2").

## Posting copy (already given to the user)

Caption: *She spent a year calling me a gold digger… then asked me to hand over
the lake house 😳 Wait for the update at the end 👀 AITA?*

Hashtags: `#redditstories #aita #amitheasshole #redditreadings #reddit #storytime
#minecraftparkour #familydrama #inheritance #sisterdrama #fyp #foryou`
