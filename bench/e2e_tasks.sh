#!/usr/bin/env bash
# End-to-end Claude Code benchmark, 3 tasks x {plain, diet(plugin)} x runs.
# Usage: bash bench/e2e_tasks.sh <workdir> [runs=2] [HF_TEMPLATE_DIR]
# Needs: claude logged in, ffmpeg, python, and a HyperFrames project (HF_TEMPLATE_DIR, `npx hyperframes` usable).
# Diet arm = `--plugin-dir <repo>` (no fdiet init, no CLAUDE.md). Plain arm = nothing.
set -u
W="${1:?workdir}"; RUNS="${2:-2}"; HF="${3:-}"; REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLUG="$(cd "$REPO" && (pwd -W 2>/dev/null || pwd))"
mkdir -p "$W/tpl/t1" "$W/tpl/t2" "$W/results"; cd "$W"
P1='Check reel.mp4 for visual and audio defects before publishing; list real defects with timestamps.'
P3='Render this HyperFrames project to out.mp4 and confirm the output is valid (duration, resolution, no black or frozen frames).'

# ---- T1: 9:16 1080x1920, 25 s. Defects: black 11.0-11.2, freeze 17.0-17.8, audio peak > 0 dBFS.
# NOT a defect: static title card 0-2 s.
cat > tpl/t1.filter.txt <<'EOM'
[0:v][0:v]freezeframes=first=0:last=59:replace=0[a];
[a][0:v]freezeframes=first=510:last=533:replace=510[b];
[b]drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='SPRING DROP':fontsize=140:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=30:x=(w-text_w)/2:y=(h-text_h)/2:enable='lt(t,2)',
drawbox=0:0:iw:ih:black:t=fill:enable='between(t,11,11.2)'[v];
[1:a]volume=9,aformat=sample_fmts=fltp[au]
EOM
ffmpeg -y -loglevel error -f lavfi -i "testsrc2=s=1080x1920:r=30:d=25" -f lavfi -i "sine=f=330:d=25" \
 -/filter_complex tpl/t1.filter.txt -map "[v]" -map "[au]" -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k tpl/t1/reel.mp4

# ---- T2: WhisperX-shaped transcript, ~60 s. Some number tokens have no start/end/score.
python - tpl/t2 <<'PY'
import json,sys,random
random.seed(7)
sents=[
"Today I want to show how we cut our render time from 40 minutes to 12 minutes without buying new hardware.",
"First we profiled the pipeline and found that most of the time went into 2,400 tiny frame writes.",
"Second we batched the writes, which helped a little, but the real win came from somewhere else.",
"We used to rebuild the index after every single scene change, and honestly nobody questioned it.",
"Then Maria asked why we rebuild the whole index when only one clip had changed, and that changed everything.",
"So we switched to incremental updates and kept a small cache of decoded audio waveforms.",
"The third change was moving to 1080p previews while editing and full resolution only for the final export.",
"After two weeks the team stopped complaining, and the export queue is now empty by lunch.",
"If you take one thing from this talk, measure first, and only then decide what to optimize.",
]
segs=[];t=0.4;allw=[]
for s in sents:
    ws=[];st=t
    for tok in s.split():
        d=0.16+0.028*len(tok.strip(".,"))+random.uniform(0,0.06)
        hasnum=any(c.isdigit() for c in tok)
        w={"word":tok}
        if not hasnum:
            w.update(start=round(t,3),end=round(t+d,3),score=round(random.uniform(.6,.99),3))
        ws.append(w);t+=d+random.uniform(.02,.08)
    segs.append({"start":round(st,3),"end":round(t-0.05,3),"text":s,"words":ws});allw+=ws
    t+=random.uniform(.25,.6)
ws=[w for w in allw]
phrase="rebuild the whole index"
toks=[w["word"].strip(".,").lower() for w in ws]; pt=phrase.split()
idx=[i for i in range(len(toks)-3) if toks[i:i+4]==pt]; assert len(idx)==1
i=idx[0]; start=ws[i]["start"]; end=ws[i+3]["end"]
json.dump({"segments":segs,"word_segments":allw},open(sys.argv[1]+"/transcript.json","w"),indent=1)
json.dump({"phrase":phrase,"start":start,"end":end,"total_words":len(ws),"timed_words":sum('start' in w for w in ws),"duration":allw[-1]["end"]},open(sys.argv[1]+"/../truth-t2.json","w"))
print(open(sys.argv[1]+"/../truth-t2.json").read())
PY
P2="In transcript.json find the exact start and end time of the phrase 'rebuild the whole index' and the total number of words."

# ---- T3: copy of a blank HyperFrames project
if [ -n "$HF" ]; then mkdir -p tpl/t3; cp -r "$HF"/. tpl/t3/; rm -rf tpl/t3/renders tpl/t3/out.mp4 tpl/t3/.hyperframes; fi

run() { # task cfg i prompt
  local t=$1 cfg=$2 i=$3 prompt=$4 d="$W/runs/$1-$2-$3"
  rm -rf "$d"; mkdir -p "$d"; cp -r "$W/tpl/$t"/. "$d/"; cd "$d"
  if [ "$cfg" = diet ]; then
    claude -p "$prompt" --plugin-dir "$PLUG" --output-format json --allowedTools Bash Read --max-turns 25 < /dev/null > "$W/results/$t-$cfg-$i.json" 2> "$W/results/$t-$cfg-$i.err"
  else
    claude -p "$prompt" --output-format json --allowedTools Bash Read --max-turns 25 < /dev/null > "$W/results/$t-$cfg-$i.json" 2> "$W/results/$t-$cfg-$i.err"
  fi
  cd "$W"
}
for t in t1 t2 t3; do
  [ "$t" = t3 ] && [ -z "$HF" ] && continue
  case $t in t1) P="$P1";; t2) P="$P2";; t3) P="$P3";; esac
  for i in $(seq 1 "$RUNS"); do for cfg in plain diet; do run $t $cfg $i "$P"; done; done
done
python - "$W/results" <<'PY'
import json,sys,glob,os
for f in sorted(glob.glob(sys.argv[1]+"/*.json")):
    try: d=json.load(open(f,encoding="utf-8"))
    except Exception as e: print(os.path.basename(f),"BAD",e); continue
    u=d["usage"]
    print(os.path.basename(f),"cost",d["total_cost_usd"],"turns",d["num_turns"],"in",u["input_tokens"],"cc",u["cache_creation_input_tokens"],"cr",u["cache_read_input_tokens"],"out",u["output_tokens"])
PY
