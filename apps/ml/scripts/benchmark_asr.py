from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
import unicodedata
import wave
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("benchmark_asr")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SCRIPT_DIR = Path(__file__).resolve().parent
ML_APP_DIR = SCRIPT_DIR.parent
REPO_ROOT = ML_APP_DIR.parent.parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "benchmark_results"
CDSCO_REFERENCE_CSV = REPO_ROOT / "data" / "seeds" / "cdsco_reference.csv"

DEFAULT_WHISPER_DEVICE = "cpu"
DEFAULT_WHISPER_COMPUTE_TYPE = "int8"
DEFAULT_MODELS = ["small", "medium"]
SYNTH_SAMPLE_RATE = 16000

# ---------------------------------------------------------------------------
# Mocked fallback dataset
# ---------------------------------------------------------------------------
# Used when the CDSCO scraper output isn't available (e.g. fresh clone, no
# network access to the CDSCO portal, or running in CI). Names are picked to
# be representative of real-world difficulty: multi-syllable brand names,
# combination drugs, and names that are easy to mis-hear in Indian accents.
MOCK_MEDICINE_NAMES: list[str] = [
    "Dolo 650",
    "Augmentin 625 Duo",
    "Allegra 120",
    "Pan 40",
    "Crocin Advance",
    "Azithromycin 500",
    "Metformin 500",
    "Amoxicillin 250",
    "Ibuprofen 400",
    "Paracetamol 650",
    "Combiflam",
    "Voveran SR",
    "Calpol",
    "Zerodol P",
    "Montair LC",
    "Telma 40",
    "Glimepiride 2",
    "Rosuvastatin 10",
    "Pantoprazole 40",
    "Cetirizine 10",
    "Levocetirizine 5",
    "Amlodipine 5",
    "Ecosprin 75",
    "Thyronorm 50",
    "Shelcal 500",
    "Becosules Capsule",
    "Digene Gel",
    "Sinarest",
    "Ondansetron 4",
    "Domperidone 10",
]


def normalize_text(text: str) -> str:
    """Lowercase, strip accents/punctuation, and collapse whitespace so that
    WER/exact-match comparisons aren't skewed by casing or formatting noise.
    """
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Classic WER = (S + D + I) / N, computed via Levenshtein distance over
    word sequences. Returns a value >= 0.0 (can exceed 1.0 if the hypothesis
    has far more insertions than the reference has words).
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    n, m = len(ref_words), len(hyp_words)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion
                    dp[i][j - 1],      # insertion
                    dp[i - 1][j - 1],  # substitution
                )

    return dp[n][m] / n


def is_exact_match(reference: str, hypothesis: str) -> bool:
    return normalize_text(reference) == normalize_text(hypothesis)


# ---------------------------------------------------------------------------
# Medicine name loading
# ---------------------------------------------------------------------------

def load_medicine_names(num_samples: int | None = None) -> list[str]:
    """Load medicine names from the CDSCO scraper output if it exists,
    otherwise fall back to the bundled mock dataset.
    """
    names: list[str] = []

    if CDSCO_REFERENCE_CSV.exists():
        try:
            import pandas as pd

            df = pd.read_csv(CDSCO_REFERENCE_CSV)
            # CDSCO portal rows are lists under "aaData"; the brand name is
            # typically the first or second column depending on the search
            # endpoint used — try common column names, then fall back to the
            # first text-like column.
            for candidate in ("BrandName", "brand_name", "medicineName", "0", "1"):
                if candidate in df.columns:
                    names = [str(v).strip() for v in df[candidate].dropna().tolist()]
                    break
            if not names and len(df.columns) > 0:
                names = [str(v).strip() for v in df.iloc[:, 0].dropna().tolist()]

            names = [n for n in names if n and n.lower() != "nan"]
            if names:
                logger.info(
                    "Loaded %d medicine names from CDSCO reference CSV (%s)",
                    len(names),
                    CDSCO_REFERENCE_CSV,
                )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Failed to read CDSCO reference CSV, using mock data: %s", exc)

    if not names:
        logger.info(
            "CDSCO reference CSV not found at %s — using %d bundled mock medicine names. "
            "Run the ETL scraper (apps/etl/src/scrapers/cdsco.py) to benchmark against "
            "live data instead.",
            CDSCO_REFERENCE_CSV,
            len(MOCK_MEDICINE_NAMES),
        )
        names = list(MOCK_MEDICINE_NAMES)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped = []
    for name in names:
        key = normalize_text(name)
        if key and key not in seen:
            seen.add(key)
            deduped.append(name)
    names = deduped

    if num_samples is not None:
        names = names[:num_samples]

    if not names:
        raise RuntimeError("No medicine names available to benchmark.")

    return names


# ---------------------------------------------------------------------------
# Audio acquisition (synthetic TTS or pre-recorded)
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + ".wav"


def synthesize_audio_clips(names: list[str], out_dir: Path) -> dict[str, Path]:
    """Generate one WAV clip per medicine name using an offline TTS engine
    (pyttsx3), caching clips on disk so repeated runs are fast. Offline TTS
    is deliberately used instead of the project's Google Cloud TTS router so
    this script can run without cloud credentials or network access.
    """
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError(
            "pyttsx3 is required to synthesize audio. Install it with "
            "`pip install pyttsx3`, or pass --audio-dir with pre-recorded clips."
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    clips: dict[str, Path] = {}

    engine = pyttsx3.init()
    engine.setProperty("rate", 150)

    for name in names:
        clip_path = out_dir / _safe_filename(name)
        if not clip_path.exists():
            engine.save_to_file(name, str(clip_path))
        clips[name] = clip_path

    engine.runAndWait()

    missing = [name for name, path in clips.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"TTS synthesis failed to produce audio for: {missing}")

    return clips


def load_prerecorded_clips(names: list[str], audio_dir: Path) -> dict[str, Path]:
    clips: dict[str, Path] = {}
    missing = []
    for name in names:
        clip_path = audio_dir / _safe_filename(name)
        if clip_path.exists():
            clips[name] = clip_path
        else:
            missing.append(name)

    if missing:
        raise FileNotFoundError(
            f"Missing pre-recorded clips in {audio_dir} for: {missing}. "
            f"Expected files named like '{_safe_filename(missing[0])}'."
        )

    return clips


def get_wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())
    except (wave.Error, EOFError):
        return 0.0


# ---------------------------------------------------------------------------
# Benchmark execution
# ---------------------------------------------------------------------------

@dataclass
class SampleResult:
    medicine_name: str
    model_size: str
    transcript: str
    wer: float
    exact_match: bool
    latency_seconds: float
    audio_duration_seconds: float


@dataclass
class ModelSummary:
    model_size: str
    num_samples: int
    mean_wer: float
    exact_match_accuracy: float
    mean_latency_seconds: float
    real_time_factor: float
    results: list[SampleResult] = field(default_factory=list)


def run_model_benchmark(
    model_size: str,
    clips: dict[str, Path],
    *,
    device: str = DEFAULT_WHISPER_DEVICE,
    compute_type: str = DEFAULT_WHISPER_COMPUTE_TYPE,
) -> ModelSummary:
    from faster_whisper import WhisperModel

    logger.info("Loading Whisper model '%s' (device=%s, compute_type=%s)...", model_size, device, compute_type)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    results: list[SampleResult] = []
    for reference_name, clip_path in clips.items():
        audio_duration = get_wav_duration_seconds(clip_path)

        started_at = time.perf_counter()
        segments, _info = model.transcribe(str(clip_path), task="transcribe", beam_size=5)
        transcript = " ".join(seg.text for seg in segments).strip()
        latency = time.perf_counter() - started_at

        wer = word_error_rate(reference_name, transcript)
        exact = is_exact_match(reference_name, transcript)

        logger.info(
            "[%s] '%s' -> '%s' | WER=%.2f exact=%s latency=%.2fs",
            model_size,
            reference_name,
            transcript,
            wer,
            exact,
            latency,
        )

        results.append(
            SampleResult(
                medicine_name=reference_name,
                model_size=model_size,
                transcript=transcript,
                wer=wer,
                exact_match=exact,
                latency_seconds=latency,
                audio_duration_seconds=audio_duration,
            )
        )

    return summarize_results(model_size, results)


def summarize_results(model_size: str, results: list[SampleResult]) -> ModelSummary:
    n = len(results)
    mean_wer = sum(r.wer for r in results) / n if n else 0.0
    exact_accuracy = sum(1 for r in results if r.exact_match) / n if n else 0.0
    mean_latency = sum(r.latency_seconds for r in results) / n if n else 0.0
    total_audio = sum(r.audio_duration_seconds for r in results)
    total_latency = sum(r.latency_seconds for r in results)
    rtf = (total_latency / total_audio) if total_audio > 0 else 0.0

    return ModelSummary(
        model_size=model_size,
        num_samples=n,
        mean_wer=mean_wer,
        exact_match_accuracy=exact_accuracy,
        mean_latency_seconds=mean_latency,
        real_time_factor=rtf,
        results=results,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_csv_report(summaries: list[ModelSummary], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "medicine_name",
                "model_size",
                "transcript",
                "wer",
                "exact_match",
                "latency_seconds",
                "audio_duration_seconds",
            ]
        )
        for summary in summaries:
            for r in summary.results:
                writer.writerow(
                    [
                        r.medicine_name,
                        r.model_size,
                        r.transcript,
                        f"{r.wer:.4f}",
                        r.exact_match,
                        f"{r.latency_seconds:.4f}",
                        f"{r.audio_duration_seconds:.4f}",
                    ]
                )
    logger.info("Wrote per-sample CSV results to %s", output_path)


def generate_markdown_report(summaries: list[ModelSummary]) -> str:
    lines = [
        "# ASR Benchmark Report — Whisper `small` vs `medium`",
        "",
        "Benchmarking Whisper model sizes against Indian medicine names, per issue #3144.",
        "",
        "## Summary",
        "",
        "| Model | Samples | Mean WER | Exact Match Accuracy | Mean Latency (s) | Real-Time Factor |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.model_size} | {s.num_samples} | {s.mean_wer:.3f} | "
            f"{s.exact_match_accuracy:.1%} | {s.mean_latency_seconds:.3f} | {s.real_time_factor:.2f}x |"
        )

    if len(summaries) >= 2:
        by_size = {s.model_size: s for s in summaries}
        if "small" in by_size and "medium" in by_size:
            small, medium = by_size["small"], by_size["medium"]
            wer_delta = small.mean_wer - medium.mean_wer
            acc_delta = medium.exact_match_accuracy - small.exact_match_accuracy
            latency_delta = medium.mean_latency_seconds - small.mean_latency_seconds
            lines += [
                "",
                "## `small` -> `medium` Delta",
                "",
                f"- WER improvement: **{wer_delta:+.3f}** (positive = medium is better)",
                f"- Exact-match accuracy change: **{acc_delta:+.1%}**",
                f"- Extra latency per clip: **{latency_delta:+.3f}s**",
            ]

    lines += ["", "## Per-Sample Results", ""]
    for s in summaries:
        lines.append(f"### Model: `{s.model_size}`")
        lines.append("")
        lines.append("| Medicine Name | Transcript | WER | Exact Match | Latency (s) |")
        lines.append("|---|---|---|---|---|")
        for r in s.results:
            lines.append(
                f"| {r.medicine_name} | {r.transcript} | {r.wer:.2f} | "
                f"{'✅' if r.exact_match else '❌'} | {r.latency_seconds:.2f} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_markdown_report(summaries: list[ModelSummary], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_markdown_report(summaries), encoding="utf-8")
    logger.info("Wrote Markdown summary report to %s", output_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--num-samples",
        type=int,
        default=20,
        help="Number of medicine names to benchmark (default: 20).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Whisper model sizes to benchmark (default: small medium).",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=None,
        help="Directory of pre-recorded WAV clips (one per medicine name). "
        "If omitted, audio is synthesized offline via pyttsx3.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write CSV/Markdown reports to (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_WHISPER_DEVICE,
        help="Device to run inference on (default: cpu).",
    )
    parser.add_argument(
        "--compute-type",
        default=DEFAULT_WHISPER_COMPUTE_TYPE,
        help="faster-whisper compute type (default: int8, matching production).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    names = load_medicine_names(num_samples=args.num_samples)
    logger.info("Benchmarking %d medicine names: %s", len(names), ", ".join(names[:5]) + ("..." if len(names) > 5 else ""))

    if args.audio_dir:
        clips = load_prerecorded_clips(names, args.audio_dir)
    else:
        tts_cache_dir = args.output_dir / "synthetic_audio"
        clips = synthesize_audio_clips(names, tts_cache_dir)

    summaries: list[ModelSummary] = []
    for model_size in args.models:
        summary = run_model_benchmark(
            model_size,
            clips,
            device=args.device,
            compute_type=args.compute_type,
        )
        summaries.append(summary)

    write_csv_report(summaries, args.output_dir / "benchmark_asr_results.csv")
    write_markdown_report(summaries, args.output_dir / "benchmark_asr_report.md")

    print("\n" + generate_markdown_report(summaries).split("## Per-Sample Results")[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())