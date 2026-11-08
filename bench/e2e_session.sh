#!/usr/bin/env bash
# End-to-end Claude Code session benchmark: plain vs FrameDiet (hook + CLAUDE.md).
# Usage: bash bench/e2e_session.sh <workdir> [runs=2]   (needs: claude logged in, ffmpeg, python venv support)
set -u
W="${1:?workdir}"; RUNS="${2:-2}"; REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT='Re-encode clip.mp4 to out.mp4 with libx264 crf 23, then check out.mp4 for visual and audio defects and list each with timestamps.'
mkdir -p "$W/plain" "$W/diet" "$W/results"; cd "$W"
# Test clip: 20 s, black 6.0-6.3 and 13.0-13.3, freeze 9-10 s, audio peak about +1 dBFS
ffmpeg -y -loglevel error -f lavfi -i "testsrc2=s=640x360:r=30:d=20" -f lavfi -i "sine=f=440:d=20" \
 -filter_complex "[0:v][0:v]freezeframes=first=270:last=299:replace=270,drawbox=0:0:iw:ih:black:t=fill:enable='between(t,6,6.3)+between(t,13,13.3)'[v];[1:a]volume=9,aformat=sample_fmts=fltp[a]" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k plain/clip.mp4
cp plain/clip.mp4 diet/clip.mp4
python -m venv venv
if [ -d venv/Scripts ]; then VB="$W/venv/Scripts"; else VB="$W/venv/bin"; fi
"$VB/pip" -q install -e "$REPO"
(cd diet && PATH="$VB:$PATH" framediet init --dir . && cat > CLAUDE.md <<'EOM'
# FrameDiet is available

Use `framediet qa <video>` before visual inspection of a video: it reports black/freeze intervals and audio peak in a short line. If it reports black/freeze intervals, add `--frames-dir <directory>` to extract small previews at those times.
Use `framediet frames <video> <time...>` when specific moments need inspection; times are seconds.
A clean QA report does not prove that typography, composition, or safe-area placement is correct.
EOM
)
for i in $(seq 1 "$RUNS"); do
  for cfg in plain diet; do
    ( cd "$cfg"; rm -f out.mp4
      if [ "$cfg" = diet ]; then export PATH="$VB:$PATH"; fi
      claude -p "$PROMPT" --output-format json --allowedTools Bash Read --max-turns 25 < /dev/null \
        > "$W/results/$cfg-$i.json" 2> "$W/results/$cfg-$i.err" )
  done
done
python - "$W/results" <<'PY'
import json,sys,glob
for f in sorted(glob.glob(sys.argv[1]+"/*.json")):
    d=json.load(open(f,encoding="utf-8")); u=d["usage"]
    print(f.split("/")[-1],"cost",d["total_cost_usd"],"turns",d["num_turns"],"in",u["input_tokens"],"cc",u["cache_creation_input_tokens"],"cr",u["cache_read_input_tokens"],"out",u["output_tokens"])
PY
