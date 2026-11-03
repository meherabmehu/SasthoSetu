"""Separate subjects/lesions and exact duplicate images across evaluation splits."""
import hashlib
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupShuffleSplit


def grouped_image_split(paths, groups, seed=42, val_fraction=0.15, test_fraction=0.15):
    """Join repeated subjects AND byte-identical images, then split components.

    Missing subject IDs are an error: an image ID is not an independent subject.
    Grouping changes class balance, so callers must report per-class metrics and
    missing classes rather than manufacturing a stratified independent test set.
    """
    if (len(paths) != len(groups) or len(paths) < 3
            or any(g is None or str(g).strip().lower() in {"", "nan", "none"} for g in groups)):
        raise ValueError("Subject/lesion IDs are required. Re-fetch the source metadata first.")
    parent = list(range(len(groups)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    by_subject, by_hash = {}, {}
    for index, (path, group) in enumerate(zip(paths, groups, strict=True)):
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for seen, key in [(by_subject, str(group)), (by_hash, digest)]:
            if key in seen:
                parent[find(index)] = find(seen[key])
            else:
                seen[key] = index
    components = np.array([find(i) for i in range(len(groups))])
    indices = np.arange(len(groups))
    if len(np.unique(components)) < 3:
        raise ValueError("At least three independent subjects are required")
    train, held = next(GroupShuffleSplit(n_splits=1, random_state=seed,
        test_size=val_fraction + test_fraction).split(indices, groups=components))
    val_local, test_local = next(GroupShuffleSplit(n_splits=1, random_state=seed + 1,
        test_size=test_fraction / (val_fraction + test_fraction)).split(
            held, groups=components[held]))
    return train, held[val_local], held[test_local]
