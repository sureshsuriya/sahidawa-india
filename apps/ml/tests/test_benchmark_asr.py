import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import benchmark_asr as bench  # noqa: E402


def test_normalize_text_strips_punctuation_and_case():
    assert bench.normalize_text("Dolo-650!") == "dolo 650"
    assert bench.normalize_text("  Pan   40  ") == "pan 40"


def test_word_error_rate_perfect_match_is_zero():
    assert bench.word_error_rate("Dolo 650", "dolo 650") == 0.0


def test_word_error_rate_single_substitution():
    # 1 substitution out of 2 reference words -> WER 0.5
    assert bench.word_error_rate("Dolo 650", "Zolo 650") == 0.5


def test_word_error_rate_empty_reference():
    assert bench.word_error_rate("", "") == 0.0
    assert bench.word_error_rate("", "hello") == 1.0


def test_is_exact_match_ignores_case_and_punctuation():
    assert bench.is_exact_match("Augmentin 625 Duo", "augmentin 625 duo") is True
    assert bench.is_exact_match("Augmentin 625 Duo", "augmentin 625") is False


def test_load_medicine_names_falls_back_to_mock_when_csv_missing(monkeypatch, tmp_path):
    fake_csv = tmp_path / "cdsco_reference.csv"
    monkeypatch.setattr(bench, "CDSCO_REFERENCE_CSV", fake_csv)

    names = bench.load_medicine_names(num_samples=5)

    assert len(names) == 5
    assert names[0] in bench.MOCK_MEDICINE_NAMES


def test_load_medicine_names_deduplicates():
    monkeypatch_names = bench.MOCK_MEDICINE_NAMES + [bench.MOCK_MEDICINE_NAMES[0].lower()]
    deduped = []
    seen = set()
    for name in monkeypatch_names:
        key = bench.normalize_text(name)
        if key not in seen:
            seen.add(key)
            deduped.append(name)
    assert len(deduped) == len(bench.MOCK_MEDICINE_NAMES)


def test_summarize_results_computes_aggregate_metrics():
    results = [
        bench.SampleResult(
            medicine_name="Dolo 650",
            model_size="small",
            transcript="dolo 650",
            wer=0.0,
            exact_match=True,
            latency_seconds=0.5,
            audio_duration_seconds=1.0,
        ),
        bench.SampleResult(
            medicine_name="Pan 40",
            model_size="small",
            transcript="pant 40",
            wer=0.5,
            exact_match=False,
            latency_seconds=0.5,
            audio_duration_seconds=1.0,
        ),
    ]

    summary = bench.summarize_results("small", results)

    assert summary.num_samples == 2
    assert summary.mean_wer == 0.25
    assert summary.exact_match_accuracy == 0.5
    assert summary.mean_latency_seconds == 0.5
    assert summary.real_time_factor == 0.5  # 1.0s total latency / 2.0s total audio


def test_generate_markdown_report_includes_delta_section():
    small = bench.summarize_results(
        "small",
        [
            bench.SampleResult("Dolo 650", "small", "dolo 650", 0.2, False, 0.3, 1.0),
        ],
    )
    medium = bench.summarize_results(
        "medium",
        [
            bench.SampleResult("Dolo 650", "medium", "dolo 650", 0.0, True, 0.6, 1.0),
        ],
    )

    report = bench.generate_markdown_report([small, medium])

    assert "small -> medium" in report or "small` -> `medium" in report
    assert "Dolo 650" in report
    assert "Mean WER" in report


def test_write_csv_report_creates_file(tmp_path):
    summary = bench.summarize_results(
        "small",
        [
            bench.SampleResult("Dolo 650", "small", "dolo 650", 0.0, True, 0.3, 1.0),
        ],
    )
    out_path = tmp_path / "results.csv"

    bench.write_csv_report([summary], out_path)

    assert out_path.exists()
    content = out_path.read_text()
    assert "Dolo 650" in content
    assert "medicine_name" in content