# Training notebooks

One notebook per model, so a reviewer can step through a training run, see the
intermediate numbers and change a parameter without editing the pipeline.

| Notebook | Model | Key metric |
|---|---|---|
| `01_triage_model.ipynb` | Symptom text → 5-level urgency | macro-F1 0.86, emergency recall 0.99 |
| `02_skin_lesion_model.ipynb` | Lesion photograph → referral band | malignant recall 0.92, AUC 0.91 |
| `03_bed_surge_model.ipynb` | Ward occupancy 24/48/72h ahead | MAE 2.7–3.0 beds |

## Running them

```bash
pip install -r backend/requirements.txt jupyter
jupyter notebook notebooks/
```

The skin notebook downloads about 2.8 GB the first time. The other two run in
a couple of minutes.

## Why they are generated

`build_notebooks.py` writes these files from the scripts in `ml/`. They are not
hand-maintained, because a hand-maintained notebook drifts away from the code
that actually runs and ends up claiming an accuracy nobody can reproduce. Each
notebook calls the same script `ml/prepare_all.py` calls.

To regenerate after changing a script:

```bash
python notebooks/build_notebooks.py
```

Cell ids are derived from a counter, so regenerating produces no spurious git
diff.
