# MuseCPEval

Measures **music context preservation** between an original audio file and an edited
version of it: how much of the original's harmony, rhythm, structure, and melody
survives the edit.

Give it a reference/estimate pair and it returns a JSON object of scores. Give it a
manifest or a pair of directories and it scores thousands of pairs in parallel.

## Metrics

| CLI name | Output key | Returns |
|---|---|---|
| `harmony` | `harmony_tonality` | `key_relatedness` (`distance_steps`, `distance_norm_0to1`), `chroma_similarity` (`chroma_dtw_cosine`, `mean_chroma_cosine`) |
| `rhythm` | `rhythm_meter` | `delta_bpm_folded`, `beat_mir_eval` (`F-measure`, `Information gain`) |
| `structure` | `structural_form` | `pairwise_f`, `ari` |
| `melody` | `melodic_content` | `contour_dtw_similarity`, `motif_3gram_recall` |

All four run by default. Scoring an identical pair (same file as reference and
estimate) returns `1.0` on the similarity metrics and `0.0` on the distance metrics —
`mean_chroma_cosine` lands a few float ulps short of `1.0` rather than exactly on it.
That is a quick way to confirm an install is sane.

## Install

The metric code needs **numpy ≤ 2.2** — librosa depends on numba, and numba refuses
newer numpy. A dedicated environment is the least painful route:

```bash
conda create -y -n musecpeval python=3.10
conda activate musecpeval
pip install "numpy<2.3" "scipy>=1.9" "librosa>=0.10" "soundfile>=0.12" "mir_eval>=0.7" tqdm
pip install msaf                      # required by the structure metric
```

Verify:

```bash
python runner.py --ref path/to/file.wav --est path/to/file.wav
```

## Run

### Single pair

```bash
# JSON to stdout
python runner.py --ref original.wav --est edited.wav

# JSON to a file
python runner.py --ref original.wav --est edited.wav --out-json result.json

# a subset of metrics
python runner.py --ref original.wav --est edited.wav --metrics harmony rhythm
```

### Batch

Exactly one input source is required.

```bash
# JSON manifest
python runner.py --batch-json pairs.json --output-dir results/

# CSV manifest
python runner.py --batch-csv pairs.csv --output-dir results/

# two flat directories, paired by filename
python runner.py --ref-dir originals/ --est-dir edited/ --output-dir results/

# nested edits (edited/<section>/<slug>/001.wav) against flat originals
python runner.py --ref-dir originals/ --est-dir edited/ --recursive --output-dir results/
```

```json
[
  {"ref": "originals/001.wav", "est": "edited/harmony/-3semitone/001.wav",
   "id": "harmony/-3semitone/001", "section": "harmony", "n_steps": -3}
]
```

### Output

`--output-dir` receives three files:

| File | Contents |
|---|---|
| `results.jsonl` | one record per pair, appended and flushed as each finishes |
| `results.json` | the same records as a single array, written at the end |
| `summary.csv` | one row per pair, nested scores flattened to dotted columns |

`results.jsonl` is what makes a run resumable, so it is written incrementally;
`results.json` and `summary.csv` only appear once the run finishes.

### Resuming

Rerunning the same command skips pairs already present in `results.jsonl`, so an
interrupted job continues instead of restarting. Ctrl-C exits `130` with partial
results intact. Pass `--no-resume` to discard prior results and start clean.

Pairs are identified by `id` when present, otherwise by the absolute ref and est paths.

There is no lock file: **two runs against the same `--output-dir` can process the same
pairs.** Use separate output directories for concurrent jobs.

## Options

| Flag | Meaning |
|---|---|
| `--ref FILE`, `--est FILE` | single-pair input |
| `--out-json FILE` | single mode: write here instead of stdout |
| `--batch-json FILE` | batch from a JSON manifest |
| `--batch-csv FILE` | batch from a CSV manifest |
| `--ref-dir DIR`, `--est-dir DIR` | batch by pairing two directories |
| `--recursive` | walk `--est-dir` subdirectories |
| `--ext EXT` | extension for directory pairing (default `.wav`) |
| `--output-dir DIR` | batch output directory (default `./results`) |
| `--metrics ...` | any of `harmony rhythm structure melody` (default: all) |
| `--n-workers N` | worker processes (default `min(8, cpus - 1)`) |
| `--max-cpu` | use every CPU as a worker |
| `--no-parallel` | run serially in one process |
| `--no-resume` | ignore and overwrite prior results |
| `--limit N` | only the first N pairs, for smoke tests |

Worker count is capped at the number of pairs.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | everything scored cleanly |
| `1` | a pair failed, a metric family failed, or a score was degraded — or bad arguments |
| `130` | interrupted; partial results kept and resumable |


## Repository layout

```
runner.py              CLI: single-pair and batch evaluation
musecpeval_metrics/    the four metric families
  harmony_tonality.py  key relatedness, chroma similarity
  rhythm_meter.py      tempo delta, beat F-measure
  structural_form.py   segmentation agreement (needs msaf)
  melody_motif.py      contour DTW, motif n-gram recall
  utils.py             shared helpers
requirements.txt
```
