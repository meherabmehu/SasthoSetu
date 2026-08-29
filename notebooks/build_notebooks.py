# -*- coding: utf-8 -*-
"""Generate the training notebooks from the scripts they mirror.

Each model has a notebook so a reviewer can step through the training run,
see the intermediate numbers and change a parameter without editing the
pipeline. The notebooks are generated rather than hand-written so they cannot
drift away from the scripts that actually run in ``ml/prepare_all.py`` — that
divergence is how a repository ends up with a notebook claiming an accuracy no
one can reproduce.

    python notebooks/build_notebooks.py

Writes one .ipynb per model into this directory.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


# nbformat 4.5 requires a stable id per cell. Deriving it from a counter keeps
# regenerated notebooks byte-identical, so a rebuild produces no git diff.
_COUNTER = {"n": 0}


def _next_id() -> str:
    _COUNTER["n"] += 1
    return f"cell{_COUNTER['n']:03d}"


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "id": _next_id(), "metadata": {},
            "source": text.strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "id": _next_id(), "execution_count": None,
            "metadata": {}, "outputs": [],
            "source": text.strip().splitlines(keepends=True)}


SETUP = """
import subprocess, sys, json
from pathlib import Path

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
print("project root:", ROOT)
"""


def triage_notebook() -> dict:
    return {
        "cells": [
            markdown("""
# Triage severity model

Classifies a free-text symptom description into five levels, from self-care to
emergency. The text arrives in Bangla, romanised Banglish, English or a mix of
all three, which is how people actually write.

**The safety rule that matters:** the model's answer is never the final word.
A deterministic red-flag layer runs afterwards and can only ever raise the
severity. If the model calls chest pain with breathlessness routine, the rules
override it to emergency. The reverse cannot happen.
            """),
            code(SETUP),
            markdown("""
## 1. Build the corpus

Two sources are combined:

* **Generated** — 9,000 notes assembled from the symptom lexicon, with the
  label derived from symptom acuity, duration, qualifier and age.
* **Real presentations** — 12,466 Bangla and Banglish notes built from 9,446
  genuine emergency department visits in the US CDC survey. Each recorded
  complaint is routed through the lexicon to its canonical symptom, then
  written back out in natural Bangla.

The English text of those visits is deliberately **not** trained on. The survey
asks how fast someone already inside an emergency department must be seen;
this model answers what a person at home should do. Mixing the two scales cost
15 points of macro-F1 when it was tried.
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "build_bangla_from_real.py")], check=True)
subprocess.run([sys.executable, str(ROOT / "ml" / "build_triage_corpus.py")], check=True)
"""),
            code("""
import pandas as pd

corpus = pd.read_csv(ROOT / "data" / "triage" / "symptom_triage_dataset.csv")
print(f"{len(corpus):,} rows")
display(corpus.groupby(["source", "triage_level"]).size().unstack(fill_value=0))
display(corpus["language"].value_counts())
corpus.sample(5, random_state=0)[["text", "language", "triage_level", "source"]]
"""),
            markdown("""
## 2. Features

A TF-IDF branch over words and another over character n-grams, joined to a
block of structured clinical features. Character n-grams matter more than usual
here: Banglish has no fixed spelling, so `buke betha`, `bukey byatha` and
`buk betha` must all reach the same place.

Age is a separate feature because it arrives as a form field, not in the text —
a text-only model is blind to it, and age changes the answer.
            """),
            code("""
from app.ai.features import clinical_feature_matrix, text_column

sample = corpus[["text", "age"]].head(3)
matrix = clinical_feature_matrix(sample)
print("structured features per row:", matrix.shape[1])
"""),
            markdown("""
## 3. Train

Three candidates are compared on the validation split and the best by macro-F1
is kept. Macro-F1 rather than accuracy because the classes are very unbalanced
and getting the rare emergencies right is the whole point.
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "train_triage_model.py")], check=True)
"""),
            code("""
metrics = json.loads((ROOT / "backend/app/ai/artifacts/triage_metrics.json").read_text())
print(json.dumps(metrics, indent=2))
"""),
            markdown("""
## 4. Does it actually escalate an emergency?

The metric that matters is not accuracy. It is whether a genuine emergency,
written the way a frightened person writes it, reaches level 5.
            """),
            code("""
from app.ai.triage_service import triage

cases = [
    ("বুকে ব্যথা, শ্বাস নিতে কষ্ট", 55, "cardiac, Bangla"),
    ("bukey betha, ghamtesi", 55, "cardiac, Banglish"),
    ("রক্তবমি হচ্ছে", 45, "GI bleed"),
    ("খিঁচুনি হচ্ছে", 25, "seizure"),
    ("niswas nite parchi na", 60, "cannot breathe"),
    ("হালকা সর্দি কাশি", 25, "common cold — must NOT escalate"),
    ("পেট ব্যথা", 30, "one ordinary symptom — must NOT escalate"),
]

for text, age, label in cases:
    result = triage(text, age=age)
    print(f"L{result['severity_level']}  {label:42} {text[:34]}")
"""),
            markdown("""
## Limitation

The Bangla training text is still generated, even where the underlying
presentation is real. No public dataset carries a clinician-assigned urgency
label against Bangla free text; that has to be collected with a hospital
partner under ethics approval. Until then this is decision support for review,
not a tool to be pointed at patients.
            """),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def skin_notebook() -> dict:
    return {
        "cells": [
            markdown("""
# Skin lesion model

Reads a photograph of a mole or skin patch and decides whether it needs a
dermatologist. Trained on HAM10000: 10,015 dermatoscopic images, each labelled
with a diagnosis confirmed by histopathology, follow-up, expert consensus or
confocal microscopy.

**Why handcrafted features and not a CNN.** A dermatologist assessing a lesion
looks at asymmetry, border, colour and diameter — the ABCD rule taught for
decades. A model built on those same measurements can be shown to a clinician
and argued with. A convolutional network would score higher and could not be
interrogated the same way. For a tool that must be reviewed before it is
trusted, that trade is worth making.
            """),
            code(SETUP),
            markdown("""
## 1. Fetch the data

About 2.8 GB from Harvard Dataverse. Cached, so this is cheap on a re-run.
Licence is CC BY-NC 4.0 — non-commercial — which is why the images stay out of
the repository.
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "fetch_skin_data.py")], check=True)
"""),
            code("""
import pandas as pd

meta = pd.read_csv(ROOT / "data" / "real" / "skin" / "metadata.csv")
print(f"{len(meta):,} labelled lesions")
display(meta.groupby(["risk", "diagnosis_name"]).size())
"""),
            markdown("""
Note how unbalanced this is. Ordinary moles outnumber melanoma roughly six to
one, which is exactly the trap: a model that always says "ordinary mole" scores
67% accuracy and is useless.
            """),
            markdown("""
## 2. What is measured

32 numbers per image, all of them things a dermatologist would name.
            """),
            code("""
from app.ai.skin_features import extract_features, FEATURE_NAMES
from PIL import Image

images = ROOT / "data" / "real" / "skin" / "images"
melanoma = meta[meta.diagnosis == "mel"].iloc[0].image_id
mole = meta[meta.diagnosis == "nv"].iloc[0].image_id

for name, label in ((melanoma, "melanoma"), (mole, "ordinary mole")):
    vector = extract_features(Image.open(images / f"{name}.jpg"))
    interesting = ["asymmetry_vertical", "border_irregularity",
                   "colour_clusters", "blue_white_fraction"]
    values = {k: round(float(vector[FEATURE_NAMES.index(k)]), 3)
              for k in interesting}
    print(f"{label:14} {values}")
"""),
            markdown("""
## 3. Train
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "train_skin_model.py")], check=True)
"""),
            code("""
metrics = json.loads((ROOT / "backend/app/ai/artifacts/skin_metrics.json").read_text())
print(json.dumps(metrics, indent=2))
"""),
            markdown("""
## 4. The number that matters

Macro-F1 across seven classes is around 0.51, which sounds poor. It is the
wrong question.

What a patient needs to know is not *which* of seven diagnoses this is — it is
*does this need a doctor*. Taking the single most likely class misses almost
half of all cancers, because melanoma rarely wins the argmax outright against
a huge population of ordinary moles.

So the referral decision sums the probability across the malignant and
precancerous classes and compares it to a threshold chosen on the validation
split to catch **at least 90%** of them. That deliberately over-refers: roughly
four in ten flagged lesions turn out benign. For a screening tool that is the
right way round.
            """),
            code("""
from app.ai.skin_service import assess_skin_image

for name, truth in ((melanoma, "melanoma"), (mole, "ordinary mole")):
    payload = (images / f"{name}.jpg").read_bytes()
    result = assess_skin_image(payload, age=58)
    print(f"{truth:14} -> {result['band']:16} concern={result['concern_score']:.3f}")
    print(f"                  {result['advice']}")
"""),
            markdown("""
## Limitation

HAM10000 is dermatoscopic — taken through a lens pressed against the skin,
under even lighting. A photograph taken on a phone in a village will not look
like that, and the model has never seen one. It is also overwhelmingly
light-skinned European data, which matters a great deal for Bangladesh.

The interface therefore never names a cancer to a patient. It says whether to
see a dermatologist, and it carries a disclaimer in both languages saying a
photograph cannot replace an examination.
            """),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def imaging_notebook() -> dict:
    return {
        "cells": [
            markdown("""
# Medical imaging models

Three image models, each answering a different question. All three return a
**referral band** rather than a diagnosis, because naming a disease to a
patient from a phone photograph is not defensible — but telling them whether
to see a doctor is useful and honest.

| Model | Data | Question |
|---|---|---|
| Skin conditions | DermNet, 15,557 photographs, 23 conditions | Does this rash need a doctor? |
| Pigmented lesions | HAM10000, 10,015 dermatoscopic images | Could this mole be cancer? |
| Chest X-ray | 5,856 paediatric films | Does this film look like pneumonia? |

**Why DermNet matters more here than HAM10000.** HAM10000 is beautifully
labelled but covers only pigmented lesions. Ringworm, scabies, eczema and nail
fungus — which is most of what walks into a Bangladeshi clinic — are not in it
at all, so a model trained only on HAM10000 will confidently call ringworm an
ordinary mole. DermNet's images are also ordinary photographs rather than
dermatoscope images, which is much closer to what a phone produces.
            """),
            code(SETUP),
            markdown("""
## 1. Fetch

About 1.7 GB for DermNet and the chest films, another 2.8 GB if you also want
HAM10000. Cached, so a re-run is cheap.
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "fetch_medical_datasets.py")], check=True)
"""),
            code("""
import pandas as pd

derm = pd.read_csv(ROOT / "data" / "real" / "imaging" / "dermnet_labels.csv")
print(f"{len(derm):,} skin photographs, {derm.condition.nunique()} conditions")
display(derm.groupby("urgency").size())
display(derm.condition_bn.value_counts().head(10))
"""),
            markdown("""
Note how many of the top conditions are infections and inflammatory rashes.
That is the clinical reality this tool has to handle.
            """),
            markdown("""
## 2. Train the skin condition model
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "train_dermnet_model.py")], check=True)
"""),
            code("""
metrics = json.loads((ROOT / "backend/app/ai/artifacts/dermnet_metrics.json").read_text())
print(json.dumps(metrics, indent=2))
"""),
            markdown("""
### Reading these numbers honestly

Macro-F1 around 0.38 is low, and accuracy around 0.43 is little better than
guessing among three bands. Taken at face value the model looks poor.

The number that decides whether it is *safe* is different: how many genuinely
urgent cases were told to stay home. Choosing the band by highest probability
sent 167 of 583 urgent cases home. Deciding by cumulative probability against
a threshold chosen on the validation split brings that to 18.

The cost of the two errors is not symmetric, so the operating point is not
where accuracy is highest. It errs towards review, and the interface wording
reflects that.
            """),
            markdown("""
## 3. Train the chest X-ray screen
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "train_chest_xray_model.py")], check=True)
"""),
            code("""
metrics = json.loads((ROOT / "backend/app/ai/artifacts/chest_xray_metrics.json").read_text())
print(json.dumps(metrics, indent=2))
"""),
            markdown("""
## 4. Try them
            """),
            code("""
import csv, pathlib
from app.ai.skin_service import assess_skin_image
from app.ai.xray_service import assess_chest_xray

imaging = ROOT / "data" / "real" / "imaging"
rows = list(csv.DictReader(open(imaging / "dermnet_labels.csv")))

for condition in ("Tinea Ringworm Candidiasis and other Fungal Infections",
                  "Scabies Lyme Disease and other Infestations and Bites",
                  "Acne and Rosacea Photos"):
    name = next(r["file"] for r in rows
                if r["condition"] == condition and r["split"] == "test")
    result = assess_skin_image((imaging / "dermnet" / name).read_bytes(), age=30)
    print(f'{condition[:38]:40} -> {result["band"]}')
"""),
            code("""
films = [r for r in csv.DictReader(open(imaging / "chest_xray_labels.csv"))
         if r["split"] == "test"]
for finding in ("pneumonia", "normal"):
    name = next(r["file"] for r in films if r["finding"] == finding)
    result = assess_chest_xray((imaging / "chest_xray" / name).read_bytes(), age=30)
    print(f'truth={finding:10} -> {result["band"]:14} '
          f'score={result["pneumonia_score"]:.3f}')
"""),
            markdown("""
## Limitations, plainly

- **DermNet is web-sourced.** Image quality varies enormously and the labels
  are the site's own categories, not biopsy-confirmed.
- **Skin tone.** Both skin datasets are predominantly light-skinned. How these
  behave on Bangladeshi skin is unvalidated and cannot be assumed.
- **The chest films are paediatric, from one hospital in China.** Adult films
  and different equipment will look different.
- **A photograph of an X-ray is not an X-ray.** Glare, angle and phone
  processing all degrade the signal.

None of these are fixed by more training. They are fixed by a clinical
partnership and locally collected data, which is the same precondition that
applies to every model in this project.
            """),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def surge_notebook() -> dict:
    return {
        "cells": [
            markdown("""
# Hospital bed surge forecast

Predicts ward occupancy 24, 48 and 72 hours ahead, so a hospital can see a
surge coming rather than discovering it when the beds run out.

A forecast is only worth having if it beats the obvious guess. The obvious
guess here is "tomorrow looks like today" — naive persistence — and that is
reported alongside every horizon.
            """),
            code(SETUP),
            markdown("""
## 1. Data

Generated: two years of daily ward occupancy across five hospitals, with
seasonal dengue pressure and injected surge events.

This is the corpus most in need of replacement. DGHS publishes real bed
occupancy, but monthly and per facility, where the model needs daily and per
ward. That requires a data-sharing agreement with a hospital.
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "generate_bed_logs.py")], check=True)
"""),
            code("""
import pandas as pd

beds = pd.read_csv(ROOT / "data" / "surge" / "bed_utilization.csv")
print(f"{len(beds):,} rows  {beds.date.min()} to {beds.date.max()}")
display(beds.groupby("ward_type")[["capacity", "occupied"]].mean().round(1))
"""),
            markdown("""
## 2. Train
            """),
            code("""
subprocess.run([sys.executable, str(ROOT / "ml" / "train_surge_model.py")], check=True)
"""),
            code("""
metrics = json.loads((ROOT / "backend/app/ai/artifacts/surge_metrics.json").read_text())
for horizon in ("h1", "h2", "h3"):
    row = metrics[horizon]
    better = row["naive_persistence_mae"] - row["test_mae_beds"]
    print(f"{horizon}: MAE {row['test_mae_beds']:.2f} beds "
          f"(naive {row['naive_persistence_mae']:.2f}, better by {better:.2f})")
"""),
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def main() -> None:
    notebooks = {
        "01_triage_model.ipynb": triage_notebook(),
        "02_skin_lesion_model.ipynb": skin_notebook(),
        "03_bed_surge_model.ipynb": surge_notebook(),
        "04_medical_imaging_models.ipynb": imaging_notebook(),
    }
    for name, content in notebooks.items():
        path = HERE / name
        path.write_text(json.dumps(content, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(content['cells'])} cells)")


if __name__ == "__main__":
    main()
