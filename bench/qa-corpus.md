# FrameDiet 0.3: external corpus for `qa`

Run T1, 2026-11-09. The goal was to check how often `qa` gives `WARN` and `note:` on other people's videos and how sensitive it is to `--freeze-warn-duration`. This is not an assessment of video or skill quality.

## Environment and corpus

- FrameDiet from checkout `ce510ce49aa28065b14d2e6ff90c013187744545`; the default threshold was not changed.
- FFmpeg/ffprobe `9.0-full_build-www.gyan.dev`; Python `3.11.9`.
- No code from the external repositories was run; no packages or paid APIs were used.
- 10 MP4 files from 6 repositories, `70,117,445` bytes in total (70.12 MB; 66.87 MiB). All actual sizes matched the approved list. SHA-256 sums and source URLs are in [`qa-corpus-raw/sources.json`](qa-corpus-raw/sources.json).
- The videos and previews live only in `C:\Temp\fd-corpus\framediet-0.3-2026-11-08`. The repository keeps sources, ffprobe metadata and FrameDiet JSON results only; no external video is included.
- The video type is a rough topical grouping from the example's description or purpose. The corpus is built from published examples and releases: curated demos, not a random sample of ordinary user renders.

## Sources

| Repository | Videos in corpus | Material and licences |
|---|---:|---|
| `actionow-ai/vvv` | 5 | [starter](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/starter.mp4), [album-vertical](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/album-vertical.mp4), [cinema](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/cinema.mp4), [comedy](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/comedy.mp4), [doodle](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/doodle.mp4); [MEDIA_LICENSE](https://github.com/actionow-ai/vvv/blob/main/MEDIA_LICENSE.md). |
| `Changroro/code-video` | 1 | [hero-45s.mp4](https://raw.githubusercontent.com/Changroro/code-video/main/docs/hero-45s.mp4); [repository and README](https://github.com/Changroro/code-video). |
| `lemomo-ai/lemo-opuscar` | 1 | [archive-lighttable.mp4](https://github.com/lemomo-ai/lemo-opuscar/releases/download/web/archive-lighttable.mp4); [licence](https://github.com/lemomo-ai/lemo-opuscar#licence), [film description](https://pdoom.video/styles/archive-lighttable/). |
| `mileson/chaojifeng-video-design` | 1 | [opuscar-swiss-motion sample](https://raw.githubusercontent.com/mileson/chaojifeng-video-design/main/styles/opuscar-swiss-motion/sample.mp4); [THIRD_PARTY_NOTICES](https://github.com/mileson/chaojifeng-video-design/blob/main/THIRD_PARTY_NOTICES.md). |
| `Aaryan-Kapoor/video-production-skill` | 1 | [product-walkthrough-demo.mp4](https://raw.githubusercontent.com/Aaryan-Kapoor/video-production-skill/main/examples/videos/product-walkthrough-demo.mp4); [repository](https://github.com/Aaryan-Kapoor/video-production-skill). No separate licence for the MP4 itself was found; the file was included in the local run from the approved list and is not redistributed. |
| `gnipbao/story-to-handdrawn-video` | 1 | [handdrawn-styles example](https://raw.githubusercontent.com/gnipbao/story-to-handdrawn-video/main/examples/style-showcase/handdrawn-styles-75-page-flip-45s-bgm.mp4); [BGM credits](https://github.com/gnipbao/story-to-handdrawn-video/blob/main/examples/style-showcase/BGM_CREDITS.md). The music is CC BY 4.0 with attribution; the video is not published or redistributed. |

## Commands and results

Exact commands and environment are in [`qa-corpus-commands.txt`](qa-corpus-commands.txt). Raw `ffprobe` JSON (10 files), QA JSON (30 files) and the text output of the six visual checks are in [`qa-corpus-raw/`](qa-corpus-raw/). The tables below are reproduced with `python -I bench/qa_corpus.py bench/qa-corpus-raw --output bench/qa-corpus-table.md`; the script reads JSON only and never opens a video.

In the `Notes` columns the number is the count of items in the `notes` array; one note line can list several intervals. Statuses are given in the order 0.5 / 0.75 / 1.0 s.

## Per video

| File | Type | Length | Video / fps / audio | Status 0.5 / 0.75 / 1.0 s | Notes 0.5 / 0.75 / 1.0 s | Warnings at 0.75 s (# + text) | Notes at 0.75 s (# + text) |
|---|---|---:|---|---|---|---|---|
| actionow-ai-vvv-starter.mp4 | motion graphics | 34.90 s | 1280x720 / 30 / 1 audio | PASS/PASS/PASS | 1/1/1 | 0: — | 1: black at start/end, likely a fade: 00:00:00.000 - 00:00:00.100 (0.10s), 00:00:34.567 - 00:00:34.867 (0.30s) |
| actionow-ai-vvv-album-vertical.mp4 | vertical motion graphics | 49.81 s | 540x960 / 30 / 1 audio | WARN/WARN/WARN | 1/1/1 | 1: audio peak -0.0 dBFS exceeds warning threshold -1.0 dBFS | 1: black at start/end, likely a fade: 00:00:49.433 - 00:00:49.767 (0.33s) |
| actionow-ai-vvv-cinema.mp4 | motion graphics | 115.84 s | 960x540 / 30 / 1 audio | WARN/WARN/WARN | 2/3/3 | 2: black intervals: 10 (00:00:11.233 - 00:00:11.700 (0.47s), 00:00:19.533 - 00:00:19.733 (0.20s), 00:00:27.833 - 00:00:32.367 (4.53s), 00:00:36.100 - 00:00:42.033 (5.93s), 00:00:52.667 - 00:00:58.567 (5.90s), +5 more); audio peak -1.0 dBFS exceeds warning threshold -1.0 dBFS | 3: black at start/end, likely a fade: 00:00:00.000 - 00:00:00.533 (0.53s), 00:01:54.767 - 00:01:55.800 (1.03s); still at start/end, likely a title or end card: 00:01:55.167 - 00:01:55.840 (0.67s); short stills under 0.75s, likely held beats: 00:00:39.467 - 00:00:39.967 (0.50s), 00:00:40.433 - 00:00:40.933 (0.50s) |
| actionow-ai-vvv-comedy.mp4 | motion graphics | 212.01 s | 960x540 / 30 / 1 audio | WARN/WARN/WARN | 1/2/2 | 1: freeze intervals: 3 (00:00:01.267 - 00:00:02.533 (1.27s), 00:01:24.633 - 00:01:25.467 (0.83s), 00:01:41.500 - 00:01:43.433 (1.93s)) | 2: black at start/end, likely a fade: 00:03:31.733 - 00:03:31.967 (0.23s); short stills under 0.75s, likely held beats: 00:00:02.767 - 00:00:03.300 (0.53s), 00:00:04.600 - 00:00:05.100 (0.50s) |
| actionow-ai-vvv-doodle.mp4 | illustrated animation | 142.02 s | 960x540 / 30 / 1 audio | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 1 (00:02:06.733 - 00:02:08.400 (1.67s)); audio peak 0.3 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:00.000 - 00:00:00.867 (0.87s); short stills under 0.75s, likely held beats: 00:00:14.200 - 00:00:14.733 (0.53s) |
| Changroro-code-video-hero-45s.mp4 | explainer/demo | 45.00 s | 1920x1080 / 30 / 1 audio | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 5 (00:00:11.133 - 00:00:13.000 (1.87s), 00:00:13.300 - 00:00:14.800 (1.50s), 00:00:24.000 - 00:00:25.000 (1.00s), 00:00:31.967 - 00:00:33.000 (1.03s), 00:00:36.133 - 00:00:37.100 (0.97s)); audio peak 1.6 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:43.500 - 00:00:44.667 (1.17s); short stills under 0.75s, likely held beats: 00:00:28.367 - 00:00:29.033 (0.67s), 00:00:30.500 - 00:00:31.000 (0.50s) |
| lemomo-ai-lemo-opuscar-archive-lighttable.mp4 | motion graphics | 40.00 s | 1280x720 / 24 / 1 audio | PASS/PASS/PASS | 1/1/1 | 0: — | 1: black at start/end, likely a fade: 00:00:00.083 - 00:00:00.208 (0.12s) |
| mileson-chaojifeng-opuscar-swiss-motion.mp4 | motion graphics | 44.00 s | 1280x720 / 24 / 1 audio | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 4 (00:00:05.500 - 00:00:07.542 (2.04s), 00:00:10.000 - 00:00:11.542 (1.54s), 00:00:27.792 - 00:00:28.917 (1.12s), 00:00:30.000 - 00:00:31.792 (1.79s)); audio peak -0.7 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:41.000 - 00:00:44.000 (3.00s); short stills under 0.75s, likely held beats: 00:00:04.500 - 00:00:05.167 (0.67s), 00:00:17.583 - 00:00:18.208 (0.62s), 00:00:20.958 - 00:00:21.542 (0.58s), 00:00:22.500 - 00:00:23.083 (0.58s) |
| Aaryan-Kapoor-product-walkthrough-demo.mp4 | product walkthrough | 10.00 s | 1280x720 / 12 / 0 audio | WARN/WARN/WARN | 1/1/1 | 1: freeze intervals: 1 (00:00:02.083 - 00:00:10.000 (7.92s)) | 1: still at start/end, likely a title or end card: 00:00:00.333 - 00:00:01.750 (1.42s) |
| gnipbao-handdrawn-styles-page-flip.mp4 | hand-drawn animation | 45.00 s | 1080x1440 / 30 / 1 audio | PASS/PASS/PASS | 1/1/1 | 0: — | 1: still at start/end, likely a title or end card: 00:00:00.000 - 00:00:01.033 (1.03s), 00:00:44.033 - 00:00:45.000 (0.97s) |

## By type

| Type | n | WARN 0.5 / 0.75 / 1.0 s | WARN share at 0.75 s | Mean notes at 0.75 s |
|---|---:|---|---:|---:|
| explainer/demo | 1 | 1/1 / 1/1 / 1/1 | 100% | 2.00 |
| hand-drawn animation | 1 | 0/1 / 0/1 / 0/1 | 0% | 1.00 |
| illustrated animation | 1 | 1/1 / 1/1 / 1/1 | 100% | 2.00 |
| motion graphics | 5 | 3/5 / 3/5 / 3/5 | 60% | 1.80 |
| product walkthrough | 1 | 1/1 / 1/1 / 1/1 | 100% | 1.00 |
| vertical motion graphics | 1 | 1/1 / 1/1 / 1/1 | 100% | 1.00 |

## Shifts relative to the 0.75 s threshold

Videos with WARN and freeze intervals are counted separately: audio or black WARNs can keep a video's status.

| Threshold | Videos with WARN | Freeze WARN intervals, total | Videos: new / gone WARN vs 0.75 s | Freeze intervals: added / removed vs 0.75 s |
|---:|---:|---:|---:|---:|
| 0.5 s | 7/10 | 25 | 0 / 0 | 11 / 0 |
| 0.75 s | 7/10 | 14 | — | — |
| 1.0 s | 7/10 | 12 | 0 / 0 | 0 / 2 |

## Visual check of disputed signals

Done from `qa --frames-dir` previews for six videos. This checks individual frames at the times that fired, not the whole video. The conclusions are about a likely intentional device, not about the quality of the skill.

| Repository / video | Signal and what was seen | Assessment and proposed rule |
|---|---|---|
| `actionow-ai/vvv`, cinema | 10 `black intervals`; thumbnails of dark scenes show parts of the picture, text and light detail. | Likely a false "black frame" signal: the brightness threshold caught dark colour grading. Treat `blackdetect` as a cue to look; for dark material check the frame and, if needed, tune `--black-pixel-threshold` separately. The accompanying audio WARN stays a plain numeric comparison of the peak. |
| `actionow-ai/vvv`, comedy | The `1.267-2.533 s` interval shows a static title screen; the same video has two more freeze WARNs that these previews cannot classify. | The first interval looks like an intentional title screen, not a defect. A rule for titles and credits should allow a static hold; the other two stay unresolved without the context of the full video. |
| `actionow-ai/vvv`, doodle | Freeze `126.733-128.400 s`; the frame shows an illustrated "Thank you for coming" card. | Likely a false signal: a static thank-you card is an expected device. The edge heuristic only recognises cards at the very start or end; cards embedded mid-video need a look at the context. |
| `Changroro/code-video`, hero | Five freeze intervals match a sequence of explanatory screens, diagrams and steps. | Looks like intentional stops so the viewer can read the explanation. For teaching diagrams a freeze WARN should stay a cue to look, not an automatic claim of a defect. |
| `mileson/chaojifeng-video-design`, Swiss Motion | Four intervals show static typographic posters and compositions meant to be read. | Likely intentional holds. For poster-style motion graphics a static composition is not a defect by itself; the warning calls for a check of the expected pace and editing. |
| `Aaryan-Kapoor/video-production-skill`, product walkthrough | Freeze WARN `2.083-10.000 s`; thumbnails show nodes being added to a teaching diagram one by one, so changes are rare and local. | Likely a false "full freeze" signal: rare interface updates can look like a freeze. Before concluding there is a defect, compare the start, middle and end of the interval; more frequent, contextual frames are needed here. |

Likely false signals are listed with a reason and a rule to check; they are not used as proof of a defect. Other WARNs remain unresolved on this sample, notably the audio peak and the two other freeze intervals in comedy. The peak in the human-readable line is rounded to 0.1 dBFS, so a value such as `-1.0 dBFS` can look equal to the threshold while the JSON holds an unrounded number slightly above it.

## Limits and conclusion

- Small sample: 10 videos, 6 sources, five videos from one repository. Categories other than motion graphics have single examples.
- These are published demo videos, not random user renders. Music, titles, cards and authors' deliberate pauses change how often signals fire.
- At most six videos were reviewed, and only from `qa --frames-dir` frames; the cause of a WARN is not always settled by thumbnails of the motion or editing.
- `WARN` means a measurable signal fired (black intervals, low motion, audio peak), not that a video or skill is bad. A `note:` also does not confirm the author's intent.
- Only the freeze classification thresholds were varied; other `qa` settings stayed at their defaults. Code and the default threshold were not changed. The project test suite was not run for this survey.

**Conclusion:** 0.75 s works as a threshold for a cue to look manually, not as automatic proof of a defect. On this sample 0.5 s adds 11 freeze intervals and 1.0 s removes 2 relative to 0.75 s; the WARN status stays on 7 of 10 videos at every threshold. The results give no grounds to change the default without a larger labelled sample.
