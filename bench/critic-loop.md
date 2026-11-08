# Third-party critic loops vs `fdiet qa` on the defect clip (2026-11-08)

Script: `bench/critic_loop.py`. Same 4 injected defects as `bench/frames-vs-qa.md` (black 7.35-7.55 s, black 14.00-14.20 s, freeze 3.0-4.0 s, +5 dB audio gain). We did not run the skills, did not install them and did not call a model.

## Skills read

Both were found in `zhuyansen/awesome-claude-video-skills`. Stars, licence and push date are from `gh api` on 2026-11-08; files were read from GitHub.

| Skill | URL | Stars | Licence | Last push |
|---|---|---:|---|---|
| motion-video-kit (`business-motion-film`) | https://github.com/echris6/motion-video-kit | 1,370 | MIT | 2026-10-14 |
| remotion-director (`critic-loop` skill) | https://github.com/Zane-0x5a/remotion-director | 51 | MIT | 2026-10-24 |

### Sampling rules (as written in the repos)

**motion-video-kit.** An independent "Gauntlet" critic receives frames the critic extracts itself.
- `scripts/contact-sheet.sh`: header says "one frame every N seconds, tiled". Default `every=1`, `cols=6`, `rows=5`; the filter is `fps=1/$e,scale=480:-1,tile=6x5`, `-frames:v 1`, so one JPEG of up to 30 cells, 480 px wide per cell.
- `references/critic-prompts.md`, full-film critic: "ffmpeg frames every 0.2s into timestamped contact sheets", plus native frames at key moments and dense 1/30 s windows around transitions (times left to the agent).
- Component critic: "a contact sheet every 0.1s".
- The number of sheets per iteration is not fixed. We counted it from the 30-cell sheet: 0.2 s gives 5 sheets for our clip, 0.1 s gives 9. Native frames and 1/30 s windows are not counted (their number is up to the agent), so these are lower bounds.
- The kit also ships non-visual checks: `frozen-time.sh` (luma difference at 10 fps) and `loudness.sh` (`ebur128`, true peak). The SKILL says to run both before sending the critic. We did not run them (running third-party scripts was blocked in this session), so we do not know what they report on our clip.

**remotion-director.** `tools/time-overview.ts` builds the "time overview" that the critic reads.
- Thumbnail cells every 0.25 s (0.5 s for pieces over 20 s), 12 per row, at most 4 rows per page, thumbnails 90x160 for portrait (read from the code), then full-resolution "settle frames" (calmest frame of each hold or slow stretch, plus the last frame).
- The tool also measures from pixels and prints on the page: blank or black stretches, holds that keep changing, short-lived content, and grey bands for stills. So this skill's critic does not rely on thumbnails alone. We did not run it (it needs Node and `tsx`).

## Result on our clip

Defect clip regenerated from the PixelFX reel (1080x1920, 30 fps, 26.45 s) with ffmpeg `drawbox` and `freezeframes`; there was no generator in `frames_vs_qa.py`, so this is a recreation, not the original file. A black defect is "covered" when a sampled frame falls inside it; a freeze needs at least two sampled frames inside it (identical neighbours; one frame cannot show a hold).

| Rule | Images / iteration | Est. vision tokens | Defects with a frame inside, of 4 |
|---|---:|---:|---|
| mvk `contact-sheet.sh` default (1 s) | 1 | 1,536 | 1 (black B only; audio no) |
| mvk full-film critic prompt (0.2 s sheets) | 5 | 7,680 | 3 (both blacks, freeze as repeated tiles; audio no) |
| mvk component critic prompt (0.1 s sheets) | 9 | 13,824 | 3 (same) |
| remotion-director overview, thumbnails only (0.5 s cells) | 2 pages | ~2,100 | 3 (same; freeze as 2 identical cells) |
| remotion-director, per settle frame | +1 each | +1,560 each | count depends on content |
| `fdiet qa` | 0 (text) | ~224 text tokens | 4 (both blacks, freeze, +2.7 dBFS peak) |

Reading the table:
- "Covered" means the evidence is in the images, not that a model notices it. A 0.2 s black frame among 30 small tiles is easy to see; five identical tiles in a row are easy to miss. We did not test this.
- Audio is in no frame. Neither skill's image path can see it; mvk's `loudness.sh` could, if the agent runs it.
- Vision tokens use the same estimate as `frames-vs-qa.md` (`ceil(w/28) x ceil(h/28)`, 1568 px side, 1568 tokens). One mvk sheet is 2880x4265 and is downscaled to about 1058x1568, so each tile reaches the model at roughly 176x313 px. remotion-director page sizes are computed from constants in the code (width 1164) with an estimated header height, so its token figure is approximate.
- `fdiet qa` on this regenerated clip reported the 4 injected defects plus 4 other freeze intervals at 11.97-12.50, 17.27-17.80, 18.20-18.87 and 24.90 s to end. These are hold intervals in the source reel with no label, as in the earlier benchmark. Since the hold notes were added (same day), those four are printed as `note:` lines and only the 4 injected defects are warnings. The audio peak reads +2.7 dBFS here, not the +1.0 in the earlier run, because the gain was applied by a different command.

## Limits

- One clip, recreated by us, one defect set; defect positions were chosen by hand and 2 of the 4 are on the 1 s grid by luck of placement (black B at 14.0 s, freeze start at 3.0 s).
- We did not run either skill end to end, did not call a model, and did not run their own frozen-time, loudness or time-overview tools. A real loop with those tools would likely flag more than the image rule alone; this test measures the image sampling rule only.
- The rules are read from SKILL, prompt and script text. Agents are free to deviate (dense windows, native frames, crops), so image counts per iteration are minimums and real loops may send more.
- Token figures are formula estimates, not provider counts; text tokens use `cl100k_base`.
- Two skills chosen for stating a critic loop in their description; they are not a sample of the ecosystem.
