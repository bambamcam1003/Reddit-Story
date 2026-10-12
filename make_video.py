#!/usr/bin/env python3
"""Build a vertical (1080x1920) Reddit-story video for TikTok.

Pipeline:
  1. Narrate the title + body with Kokoro TTS (offline), sentence by sentence, using a
     male or female voice to match the story's narrator.
  2. Estimate per-word timings and write big, centered, pop-in captions (ASS).
  3. Draw a Reddit-style title card shown while the title is read.
  4. Cut the gameplay footage into segments from across the source, crop to 9:16,
     mute it, and lay the narration + captions on top.

Usage:
  python3 make_video.py --background parkour.mp4 --kokoro-dir models/
  python3 make_video.py --placeholder ...      # preview without gameplay footage
"""
import argparse
import json
import random
import re
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_REG = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
SAMPLE_GAP = 0.18  # silence between sentences, seconds


def run(cmd):
    subprocess.run(cmd, check=True)


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------- narration
VOICES = {"female": "af_heart", "male": "am_michael"}  # best-rated Kokoro voices

GENDER_PATTERNS = [
    (r"\(\s*\d{2}\s*([MF])\s*\)|\[\s*\d{2}\s*([MF])\s*\]|\b\d{2}\s?([MF])\b", None),
    (r"\b\d{2}\s*,?\s*(male|female)\b|\bI'?m\s+(?:a\s+)?[\w -]{0,20}?,?\s*(male|female)\b", None),
    (r"\bI'?m\s+(?:a|an)\s+(?:\w+\s+)?(guy|man|dude|husband|boyfriend|dad|father|son|brother)\b", "male"),
    (r"\bI'?m\s+(?:a|an)\s+(?:\w+\s+)?(girl|woman|lady|wife|girlfriend|mom|mother|daughter|sister)\b", "female"),
    (r"\bmy (wife|girlfriend)\b", "male"),
    (r"\bmy (husband|boyfriend)\b", "female"),
]


def narrator_gender(story):
    """Explicit "narrator" field wins; otherwise look for clues like (26F), "26 female", "I'm a guy"."""
    if story.get("narrator") in VOICES:
        return story["narrator"]
    text = " ".join([story["title"], *story["body"]])
    for pattern, gender in GENDER_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if gender:
                return gender
            g = next(x for x in m.groups() if x).lower()
            return "male" if g in ("m", "male") else "female"
    print("warning: couldn't tell the narrator's gender; defaulting to female (set \"narrator\" in the story)")
    return "female"


def narrate(story, model_dir, voice_name, work, speed):
    import numpy as np
    from kokoro_onnx import Kokoro

    model_dir = Path(model_dir)
    tts = Kokoro(str(model_dir / "kokoro-v1.0.onnx"), str(model_dir / "voices-v1.0.bin"))

    sentences = [("title", s) for s in split_sentences(story["title"])]
    for para in story["body"]:
        sentences += [("body", s) for s in split_sentences(para)]

    chunks, timeline, t, rate = [], [], 0.0, 24000
    for i, (kind, text) in enumerate(sentences):
        audio, rate = tts.create(text, voice=voice_name, speed=speed, lang="en-us")
        dur = len(audio) / rate
        timeline.append((kind, text, t, t + dur))
        pause = SAMPLE_GAP
        # a longer pause after the title, before the story starts
        if kind == "title" and (i + 1 == len(sentences) or sentences[i + 1][0] != "title"):
            pause *= 4
        chunks += [audio, np.zeros(int(rate * pause), dtype=np.float32)]
        t += dur + pause

    pcm = (np.clip(np.concatenate(chunks), -1, 1) * 32767).astype("<i2")
    out = work / "narration.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return out, timeline


# ----------------------------------------------------------------- captions
def word_timings(timeline):
    """Spread each sentence's duration over its words, weighted by length."""
    words = []
    for kind, text, start, end in timeline:
        toks = text.split()
        weights = [len(re.sub(r"\W", "", t)) + 2 for t in toks]
        total = sum(weights)
        t = start
        for tok, w in zip(toks, weights):
            d = (end - start) * w / total
            words.append((kind, tok, t, t + d))
            t += d
    return words


def ass_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_captions(words, path, max_words=3):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Black,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,4,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    body = [w for w in words if w[0] == "body"]  # title is shown on the card instead
    chunk = []
    for i, w in enumerate(body):
        chunk.append(w)
        ends_clause = re.search(r"[.,!?;:]$", w[1])
        if len(chunk) == max_words or ends_clause or i == len(body) - 1:
            start = chunk[0][2]
            end = body[i + 1][2] if i + 1 < len(body) and body[i + 1][2] - chunk[-1][3] < 0.4 else chunk[-1][3]
            text = " ".join(c[1] for c in chunk).upper()
            # pop-in: start at 80% scale, grow to 100% in 80ms; highlight words in yellow at random
            colour = r"{\c&H00E5FF&}" if random.random() < 0.18 else ""
            lines.append(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,"
                rf"{{\fscx80\fscy80\t(0,80,\fscx100\fscy100)}}{colour}{text}")
            chunk = []
    path.write_text(header + "\n".join(lines) + "\n")


# --------------------------------------------------------------- title card
def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def title_card(story, path):
    pad, card_w = 48, 940
    f_title = ImageFont.truetype(FONT_BOLD, 50)
    f_sub = ImageFont.truetype(FONT_BOLD, 36)
    f_user = ImageFont.truetype(FONT_REG, 30)
    f_stat = ImageFont.truetype(FONT_BOLD, 32)

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = wrap(probe, story["title"], f_title, card_w - 2 * pad)
    line_h = 64
    card_h = pad + 96 + 28 + len(lines) * line_h + 36 + 50 + pad

    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=36, fill=(255, 255, 255, 255))

    # subreddit avatar: orange circle with a simple white face
    cx, cy, r = pad + 44, pad + 44, 44
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 69, 0))
    d.ellipse((cx - 26, cy - 14, cx + 26, cy + 26), fill="white")
    d.ellipse((cx - 14, cy - 2, cx - 4, cy + 8), fill=(255, 69, 0))
    d.ellipse((cx + 4, cy - 2, cx + 14, cy + 8), fill=(255, 69, 0))
    d.text((pad + 108, pad + 6), story["subreddit"], font=f_sub, fill=(26, 26, 27))
    d.text((pad + 108, pad + 52), story["username"], font=f_user, fill=(120, 124, 126))

    y = pad + 96 + 28
    for ln in lines:
        d.text((pad, y), ln, font=f_title, fill=(26, 26, 27))
        y += line_h
    y += 36
    d.text((pad, y), f"↑ {story['upvotes']}", font=f_stat, fill=(255, 69, 0))
    d.text((pad + 220, y), f"{story['comments']} comments", font=f_stat, fill=(120, 124, 126))
    img.save(path)


# --------------------------------------------------------------- background
def build_background(sources, duration, work, placeholder, seed):
    out = work / "background.mp4"
    vf = f"scale=-2:{H}:flags=lanczos,crop={W}:{H},fps=30,setsar=1"
    if placeholder:
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
             f"gradients=s={W}x{H}:c0=0x3a7d2c:c1=0x6b4a2b:speed=0.02:d={duration + 1}:r=30",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(out)])
        return out

    # take ~45s segments from different parts of the source(s) so it never looks looped
    rng = random.Random(seed)
    lengths = [(s, probe_duration(s)) for s in sources]
    seg_len, parts, total, i = 45.0, [], 0.0, 0
    while total < duration + 1:
        src, src_len = lengths[i % len(lengths)]
        take = min(seg_len, duration + 1 - total)
        start = rng.uniform(5, max(5.0, src_len - take - 5))
        part = work / f"bg{i:02d}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{take:.2f}",
             "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", str(part)])
        parts.append(part)
        total += take
        i += 1
    listing = work / "bg.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    return out


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", default="story/story.json")
    ap.add_argument("--background", nargs="*", default=[], help="gameplay video file(s)")
    ap.add_argument("--placeholder", action="store_true", help="use a generated background")
    ap.add_argument("--kokoro-dir", default="models", help="folder with kokoro-v1.0.onnx + voices-v1.0.bin")
    ap.add_argument("--voice", help="force a Kokoro voice, e.g. af_bella or am_fenrir")
    ap.add_argument("--speed", type=float, default=1.1, help="narration speed (1.0 = normal)")
    ap.add_argument("--work", default="build")
    ap.add_argument("--out", default="output/reddit_story.mp4")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    if not args.background and not args.placeholder:
        ap.error("pass --background FILE (or --placeholder for a preview)")

    random.seed(args.seed)
    story = json.loads(Path(args.story).read_text())
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    gender = narrator_gender(story)
    voice = args.voice or VOICES[gender]
    print(f"narrator: {gender} -> voice {voice}")
    audio, timeline = narrate(story, args.kokoro_dir, voice, work, args.speed)
    duration = probe_duration(audio)
    title_end = max(e for k, _, _, e in timeline if k == "title") + 0.4
    print(f"narration: {duration:.1f}s (title card until {title_end:.1f}s)")

    write_captions(word_timings(timeline), work / "captions.ass")
    title_card(story, work / "card.png")
    bg = build_background(args.background, duration, work, args.placeholder, args.seed)

    fc = (f"[0:v][2:v]overlay=(W-w)/2:(H-h)/2-80:enable='lt(t,{title_end:.2f})'[v1];"
          f"[v1]ass={work / 'captions.ass'}:fontsdir=/usr/share/fonts/opentype/inter[v]")
    run(["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(bg), "-i", str(audio), "-loop", "1", "-i",
         str(work / "card.png"), "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
         "-t", f"{duration:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
         "-movflags", "+faststart", args.out])
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
