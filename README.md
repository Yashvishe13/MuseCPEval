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
# same file twice -> every similarity 1.0
```

Notes on dependencies:

- **`msaf` is required for `--metrics structure`**, not optional. Without it the
  structure metric raises `ModuleNotFoundError` rather than silently degrading.
  A bare `import msaf` fails with `cannot import name 'inf' from 'scipy'`; that is
  expected and harmless, because `structural_form.py` patches `scipy.inf` before
  importing it. The other three metrics work without msaf.
- `essentia` and `madmom` appear in `requirements.txt` but are not imported by any
  current metric module. You can skip them.
- Do **not** apply the legacy `np.bool = bool` / `np.float = float` aliases that older
  scripts in this project use. Under numpy 2.x they corrupt `numpy.ma` and every
  `scipy.spatial` import then fails.

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

Exits non-zero if either file is missing. A metric family that fails is reported as
`{"error": ...}` under its own key so the others still return.

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

**JSON manifest** — a list of objects, or `{"pairs": [...]}`. `ref` and `est` are
required; `id` (or `song_id`) is optional; any other field is copied through onto the
output record, which is useful for grouping later:

```json
[
  {"ref": "originals/001.wav", "est": "edited/harmony/-3semitone/001.wav",
   "id": "harmony/-3semitone/001", "section": "harmony", "n_steps": -3}
]
```

**CSV manifest** — same idea, one header row: `ref,est,id,section,...`

**Directory pairing** — files sharing a name are paired, and the filename stem becomes
the `id`. `--ext` changes the extension (default `.wav`). Plain mode is flat; with
`--recursive`, `--est-dir` is walked and each edit is matched against `--ref-dir` first
by mirrored relative path and then by bare filename, so a nested edit tree can be
compared against a flat directory of originals. Recursive ids are the relative path
without extension (`harmony/-3semitone/001`), which keeps pairs distinct when every
subdirectory reuses the same filenames.

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

## Degraded structure scores

`structural_form` warns instead of raising when msaf segmentation and then its
uniform-grid fallback both fail on a file. It then scores against a dummy segment, so
the number it returns is meaningless — but nothing in the returned dict distinguishes
it from a real score.

The runner detects that warning and lists the affected family under
`degraded_metrics` on the record, counts it in the run summary, and marks it in the
progress line. Treat any record carrying `degraded_metrics` as unscored:

```json
{"key": "…", "structural_form": {"pairwise_f": 0.662, "ari": 0.0},
 "degraded_metrics": ["structural_form"]}
```

## Performance

Batch parallelism is process-based (spawn), with BLAS threads pinned to one per worker
so N workers do not oversubscribe the cores. Measured runtimes:

| Workload | Workers | Wall |
|---|---|---|
| 32 pairs of 10s audio | 1 | 111s |
| 32 pairs of 10s audio | 8 | 18s |
| 32 pairs of 10s audio | 32 | 8.7s |
| 400 pairs, 37s–1782s audio, structure + melody | 48 | 778s |

Cost scales with audio duration, so a few long files can dominate a run — in the
400-pair job above, one 1782s track's edits were the last thing running for roughly
15 minutes. Consider giving unusually long files their own job.

Batch and single mode agree to within ~1e-9. The difference is real but not
meaningful: workers run single-threaded BLAS while single mode does not, which changes
floating-point accumulation order in the DTW cosine. Most values are bit-identical.

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

`musecpeval_metrics/` is not an importable package — it has no `__init__.py` and its
modules import each other flatly (`from utils import ...`). `runner.py` therefore adds
the directory to `sys.path` rather than importing it as a package. Keep that insert at
module scope: batch workers are spawned and re-import the module before the metric
imports run.

Each metric module also has its own `__main__` block that scores a directory of pairs
for that family alone, independent of `runner.py`. Beware that the flag spelling is not
consistent between them: `rhythm_meter.py` takes `--orig-dir` / `--edit-dir`, while
`harmony_tonality.py`, `melody_motif.py`, and `structural_form.py` take `--orig_dir` /
`--edit_dir`.
