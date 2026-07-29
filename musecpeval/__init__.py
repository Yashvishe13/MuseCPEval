"""MuseCPEval — music context preservation metrics.

Scores how much of an original recording's harmony, rhythm, structure, and
melody survives an edit.

    from musecpeval import harmony_score, rhythm_score

    harmony_score("original.wav", "edited.wav")

The CLI in :mod:`musecpeval.runner` (installed as ``musecpeval``) wraps the same
functions for single pairs and for parallel batches.

The four scoring functions are resolved lazily: importing this package does not
pull in librosa or mir_eval, and ``python -m musecpeval.metrics.<name>`` still
runs a family's own directory-scoring CLI without double-import warnings.
"""
from importlib import import_module

__version__ = "0.1.0"

_LAZY = {
    "harmony_score": "musecpeval.metrics.harmony_tonality",
    "melody_score": "musecpeval.metrics.melody_motif",
    "rhythm_score": "musecpeval.metrics.rhythm_meter",
    "structural_score": "musecpeval.metrics.structural_form",
}

__all__ = ["__version__", *_LAZY]


def __getattr__(name: str):
    if name in _LAZY:
        value = getattr(import_module(_LAZY[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
