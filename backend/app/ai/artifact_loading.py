"""Refuse incompatible pickles instead of silently serving unsupported models."""
import warnings
from threading import RLock

import joblib
from sklearn.exceptions import InconsistentVersionWarning


class IncompatibleArtifact(RuntimeError):
    pass

_LOAD_LOCK = RLock()


def load_artifact(path, error_type=IncompatibleArtifact):
    try:
        with _LOAD_LOCK, warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            return joblib.load(path)
    except InconsistentVersionWarning as error:
        raise error_type(
            f"{path.name} must be rebuilt with the installed scikit-learn version"
        ) from error
