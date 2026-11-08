# Frames vs `fdiet qa` on a clip with injected defects (2026-11-08)

Script: `bench/frames_vs_qa.py`. Source clip, copies and intermediate files live outside this repository.

## Method

- Source: the local PixelFX reel (1080x1920, 30 fps, 26.45 s). A byte-identical copy is the **control**.
- The **defect clip** is a re-encode (libx264 crf 18, AAC) of the same reel with injected, known defects:
  - black frames 7.35-7.55 s and 14.00-14.20 s (0.2 s each, about 6 frames, off and on the 1 fps grid);
  - a 1.0 s freeze at 3.0-4.0 s (frames held with `freezeframes`), placed where the reel is moving;
  - +5 dB audio gain (source peak -1.6 dBFS).
- Compared: 1 fps sampling (27 frames), one 3x3 `fdiet sheet`, and `fdiet qa`. Detection is judged against the injected windows.
- Vision tokens use the documented formula `ceil(w/28) x ceil(h/28)` after the documented resize rule (standard tier: 1568 px side, 1568 tokens). This is an estimate. The documentation's table of which models use the high-resolution tier was only read through a model summary, not verified verbatim. Text tokens use `cl100k_base`, not Claude's tokenizer.

## Detection of injected defects

| Defect | 1 fps frames | 3x3 sheet | `fdiet qa` |
|---|---|---|---|
| black A (0.20 s) | no | no | yes |
| black B (0.20 s) | yes | no | yes |
| freeze (1.0 s) | no | no | yes |
| audio peak above -1 dBFS | no | no | yes (reported +1.0 dBFS) |

Notes:

- Black B is seen by 1 fps only because it was placed on a grid second. For a 0.2 s glitch at a random position the chance of landing on a 1 fps sample is about 20%, and on the sheet about 7% (nine samples about 2.9 s apart).
- A hold cannot be seen in sparse single frames by construction, and frames carry no audio. The audio baseline that matters is `ffmpeg volumedetect`, not frames.

## False positives of `fdiet qa`

- Control (no injected defects): 4 freeze intervals (11.97-12.50, 17.23-17.83, 18.20-18.87, 25.20 s to end).
- Defect clip: the same 4 outside the injected windows, plus the injected one.

These are probably intentional holds in the reel, but the benchmark has no label that says so. On this stylised reel `qa` raised about as many unlabelled warnings as it found real injected events; default thresholds are not tuned per clip type.

## Context cost

| Item | Pixels after resize | Est. vision tokens (standard tier) |
|---|---|---:|
| one full 1080x1920 frame | 819x1456 | 1,560 |
| one `fdiet frames` preview 384x684 | 384x684 | 350 |
| 27 frames at 1 fps, full size | | 42,120 |
| 27 frames at 1 fps, previews | | 9,450 |
| one 3x3 sheet 1184x2078 | 830x1456 | 1,560 |

On the high-resolution tier the same arithmetic gives 2,691 tokens per full frame (72,657 for 27) and 3,225 for the sheet; previews stay at 350.

| Text | Chars | `cl100k` tokens |
|---|---:|---:|
| raw `ffmpeg` output with blackdetect, freezedetect, cropdetect, volumedetect | 118,358 | 60,517 |
| the same output filtered with grep to detector lines (19 lines) | 1,557 | 560 |
| `fdiet qa` report | 478 | 224 |

`qa` + one sheet + one preview frame is roughly 2,100 tokens (text proxy plus vision estimate, mixed units).

## What this does and does not show

- The raw `ffmpeg` row is dominated by one `cropdetect` line per frame (788 lines). Against an agent that greps the detector lines, `qa` saves about 340 tokens (560 to 224). Its advantage there is aggregation and a verdict, not token count.
- Against reading frames, `qa` + sheet is far cheaper and, for short glitches, holds and audio peaks, the frames and sheet cannot detect those events at all. This is a statement about sparse sampling, not about how well a model reads a layout.
- Not measured: whether a model judges composition, typography or safe areas from the sheet, whether `qa` + sheet replaces visual review of design quality, and any end-to-end conversation cost.

## Limits

- One source clip, one defect set, one encode. Defect positions were chosen by hand.
- The injected freeze was made with `freezeframes`; the encode changes pixel values slightly, so freeze intervals drift by a few tenths of a second.
- The defect clip's video stream is 26.33 s against 26.45 s of audio.
- Vision tokens are formula estimates, not provider counts.
