"""Publish reproducible dataset provenance and the frozen research evaluations."""
import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

from evaluate_imaging import dataset_rows
from imaging_training import CACHE

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "skin": ("HAM10000", "https://doi.org/10.7910/DVN/DBW86T", "CC BY-NC 4.0",
             ["ham1.zip", "ham2.zip", "ham10000_metadata.csv"]),
    "mpox": ("MSID v6", "https://data.mendeley.com/datasets/r9bfpnvyxr/6", "CC BY 4.0", ["mpox.zip"]),
    "msld": ("MSLD v2 originals", "https://github.com/ShamsNafisaAli/Monkeypox-Skin-Lesion-Dataset-v2",
             "CC BY 4.0 (authors' badge)", ["msld_original.zip"]),
    "tb": ("TB/pneumonia/COVID/normal mirror",
           "https://huggingface.co/datasets/DevVoyageR007/classify_Pneumonia_Tuberculosis_and_Normal__Non_Xray_chest_Xray_images",
           "Mirror declares no licence; underlying lineage not fully verified", ["tb_full.zip"]),
    "pad": ("PAD-UFES-20 v1", "https://data.mendeley.com/datasets/zr7vgbcyr2/1", "CC BY 4.0", ["pad.zip"]),
    "dr": ("Retinopathy 256px mirror",
           "https://huggingface.co/datasets/Rami/Diabetic_Retinopathy_Preprocessed_Dataset_256x256",
           "Mirror declares no licence", ["dr.parquet"]),
    "oral": ("Oral carcinoma/normal mirror", "https://huggingface.co/datasets/Alwaly/Oral_Cancer-cancer",
             "Mirror declares no licence", ["oral_00000.parquet", "oral_00001.parquet"]),
}


def report(artifacts, destination):
    artifacts, destination = Path(artifacts), Path(destination)
    provenance, summaries, pixels = {}, {}, {}
    for name, (title, url, licence, files) in SOURCES.items():
        holdout = json.loads((artifacts / f"{name}_holdout.json").read_text(encoding="utf-8"))
        summaries[name] = holdout
        audit = holdout["split_audit"]
        cached = json.loads((CACHE / f"{name}-{audit['input_signature']}.json").read_text(encoding="utf-8"))
        pixels[name] = {image["pixel_sha256"] for image in cached["images"] if image["pixel_sha256"]}
        records = []
        for filename in files:
            path = ROOT / "data/real/_cache" / filename
            source_file = path.with_name(path.name + ".source.json")
            if filename == "msld_original.zip":
                source_file = path.with_suffix(".source.json")
            if source_file.exists():
                record = json.loads(source_file.read_text(encoding="utf-8"))
            else:
                with path.open("rb") as handle:
                    record = {"sha256": hashlib.file_digest(handle, "sha256").hexdigest()}
            records.append({"cache_file": filename, "bytes": path.stat().st_size, **record})
        provenance[name] = {"title": title, "source": url, "licence": licence,
            "images_extracted": audit["source_rows"], "eligible_images": audit["eligible_images"],
            "files": records, "clinical_validation": False}
    overlaps = [{"datasets": [a, b], "shared_decoded_pixel_hashes": len(pixels[a] & pixels[b])}
                for a, b in combinations(pixels, 2) if pixels[a] & pixels[b]]
    (ROOT / "data/real/imaging/dataset_sources.json").write_text(json.dumps({
        "scope": "local research/demo acquisition; no production licensing clearance",
        "datasets": provenance, "cross_dataset_exact_overlap": overlaps,
        "overlap_limitation": "Exact 128px pixel hashes only; absence does not exclude transformed/shared patients."
    }, indent=2), encoding="utf-8")
    lines = ["# Imaging retraining — 2026-11-04", "",
        "Seven public image collections were acquired or refreshed and trained locally under the pinned "
        "Python 3.12 / scikit-learn 1.5.2 runtime. This release is for demo/research only. "
        "It does not establish diagnostic accuracy in Bangladesh or authorize clinical deployment.", "",
        "## Frozen evaluation", "",
        "Source patient IDs (PAD, MSLD and recognizable TB filenames), HAM lesion IDs, exact decoded-pixel "
        "duplicates and 64-bit perceptual hashes (Hamming distance ≤4) form connected components before "
        "splitting. Unreadable/blank images, exact duplicates and every conflicting-label pixel duplicate "
        "are excluded. Seed-42 stratified group folds separate training, validation and test. "
        "HAM uses ten folds, MSID/MSLD five and the remaining datasets seven; one fold each is reserved "
        "for validation and test. Near-duplicate matching is heuristic, not proof of independence.", "",
        "Classifier selection uses validation macro-F1 across logistic regression, histogram boosting "
        "and balanced extra trees (400 trees). The highest observed threshold meeting 90% validation "
        "positive recall is frozen before test evaluation, with a 1e-12 downward numerical margin "
        "to keep parallel tree summation roundoff from losing a boundary case. "
        "HAM includes malignant/precancerous labels; "
        "PAD positives are BCC/SCC/MEL; retina positives are severe/proliferative; other positives are "
        "TB, monkeypox or oral carcinoma respectively. Weighted concern scores retain the serving contract.", "",
        "Research release gate: disjoint components, validation recall ≥90%, nonzero validation specificity, "
        "at least ten positive holdout images and holdout recall ≥80%. Test results participate only in "
        "this acceptance gate, not classifier or threshold tuning. This is not a clinical safety standard.", "",
        "| Dataset | Source / excluded | Train / validation / test | Test recall (95% component CI) | "
        "Specificity | Macro-F1 | Research gate |",
        "|---|---:|---:|---:|---:|---:|---|"]
    for name, summary in summaries.items():
        audit = summary["split_audit"]
        test = summary["metrics"]["test"]
        ci = test["confidence_intervals"]["recall_95"]
        size = audit["partition_sizes"]
        lines.append(f"| {name} | {audit['source_rows']} / {audit['excluded_images']} | "
            f"{size['train']} / {size['validation']} / {size['test']} | {test['recall']:.1%} "
            f"({ci[0]:.1%}–{ci[1]:.1%}) | {test['specificity']:.1%} | {test['macro_f1']:.3f} | "
            f"{'pass' if summary['engineering_gate_passed'] else 'reject'} |")
    lines += ["", "Intervals resample test components 1,000 times. They measure sampling uncertainty "
        "within these collections, not transportability. All partitions, hashes, per-image predictions, "
        "confusion counts and validation metrics accompany the model artifacts.", "",
        "## Provenance and limitations", "",
        "| Collection | Extracted images | Source licence | Patient identity |",
        "|---|---:|---|---|"]
    for name, item in provenance.items():
        audit = summaries[name]["split_audit"]
        _, _, labels = dataset_rows(name)
        identity = "source patient groups" if audit["all_subjects_known"] else audit["patient_identity_limitation"]
        lines.append(f"| [{item['title']}]({item['source']}) | {item['images_extracted']} | "
                     f"{item['licence']} | {identity} |")
        if not labels.exists():
            raise FileNotFoundError(labels)
    lines += ["", "Downloaded archive/shard SHA-256 values, immutable Hugging Face revisions and file sizes "
        "are recorded in [dataset_sources.json](../data/real/imaging/dataset_sources.json). "
        "Public availability does not establish reuse rights. Images and source archives remain local "
        "and gitignored. HAM is noncommercial; unclear mirror licences require independent clearance.", "",
        "MSLD uses the 755 originals once (fold1), with filename patient IDs; augmented images and repeated "
        "fold directories are not new cases. TB is stored as lossless 128px PNG after the exact serving "
        "resize; a regression test verifies unchanged runtime features. Its original archive is retained. "
        "Retina/oral mirrors lack patient IDs and may include unknown source transformations or augmentation; "
        "their results cannot be called patient-independent. MSID is web-collected, not a Bangladesh clinical cohort.", "",
        "Cross-collection exact decoded-pixel matches: " + ("; ".join(
            f"{item['datasets'][0]}/{item['datasets'][1]}: {item['shared_decoded_pixel_hashes']}"
            for item in overlaps) or "none detected") + ". Near matches and shared patients can still exist. "
        "Separate skin/rash screens are not proven independent ensemble evidence.", "",
        "The previous scores in AI_REPORT.md used different splits and are historical. No numerical "
        "improvement over those scores is claimed. The improvement here is compatible retraining, "
        "better validation separation, source traceability and measured uncertainty. Inspect specificity "
        "alongside recall: high referral rates can place substantial burden on clinicians.", "",
        "The [skin-tone audit](model_cards/skin_tone_audit.md) uses only PAD's held-out test images. "
        "Independent consented local cases, darker-skin cohorts, clinician-reviewed referral mappings, "
        "prospective external validation and licensing clearance remain necessary before real use.", "",
        "## Reproduction", "", "```powershell", "python -m pip install -r requirements-ml.txt",
        "$env:SASTHOSETU_ARTIFACT_DIR = '.tmp/imaging-candidates'",
        "# Acquire originals with ml/fetch_{skin,mpox,msld,dr,oral,pad}_data.py individually.",
        "python ml/fetch_tb_data.py --compact",
        "# Run ml/train_{skin,tb,pad,mpox,msld,dr,oral}_model.py individually.",
        "python ml/evaluate_imaging.py skin tb pad mpox msld dr oral --artifacts .tmp/imaging-candidates",
        "python ml/audit_skin_tones.py --artifacts .tmp/imaging-candidates",
        "python ml/report_imaging.py --artifacts .tmp/imaging-candidates",
        "python ml/promote_imaging.py --source .tmp/imaging-candidates", "```", "",
        "Allow over 15 GB for archives plus extraction space. Range downloads resume completed chunks; "
        "feature caches are invalidated when ordered metadata, file attributes or feature code changes. "
        "Only evaluated artifacts passing the research gate are copied into the serving directory. "
        "Restart running application processes to reload their cached model bundles.", ""]
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/MODEL_RETRAINING_2026-11-04.md")
    args = parser.parse_args()
    report(args.artifacts, args.report)
