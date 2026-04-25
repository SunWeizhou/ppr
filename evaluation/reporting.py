"""Report writers for local evaluation runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _format_float(value) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def render_markdown_report(payload: dict) -> str:
    k_values = payload.get("k_values", [])
    variants = payload.get("variants", {})
    label_counts = payload.get("label_counts", {})
    total_papers = sum(variant.get("paper_count", 0) for variant in variants.values())
    full_mrr = variants.get("full_scorer", {}).get("metrics", {}).get("MRR", 0.0)

    lines = [
        "# Evaluation Report",
        "",
        f"- Generated at: `{payload.get('generated_at', '')}`",
        f"- Input runs: `{payload.get('input_runs', 0)}`",
        f"- K values: `{', '.join(str(k) for k in k_values)}`",
        f"- Label counts: `{json.dumps(label_counts, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Summary",
        "",
    ]

    if payload.get("input_runs", 0) == 0:
        lines.extend(
            [
                "No recommendation runs were found. Metrics are empty because evaluation does not fetch arXiv or generate recommendations.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| Variant | Runs | Papers | MRR | Delta vs Full MRR |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, variant in variants.items():
            metrics = variant.get("metrics", {})
            mrr = metrics.get("MRR", 0.0)
            lines.append(
                f"| {name} | {variant.get('run_count', 0)} | {variant.get('paper_count', 0)} | "
                f"{_format_float(mrr)} | {_format_float(mrr - full_mrr)} |"
            )
        lines.append("")

    lines.extend(["## Metrics By K", ""])
    for name, variant in variants.items():
        metrics = variant.get("metrics", {})
        lines.extend([f"### {name}", "", "| K | Relevant@K | DeepRead@K | Ignored@K | NDCG@K |", "| ---: | ---: | ---: | ---: | ---: |"])
        for k in k_values:
            lines.append(
                f"| {k} | {_format_float(metrics.get(f'Relevant@{k}', 0.0))} | "
                f"{_format_float(metrics.get(f'DeepRead@{k}', 0.0))} | "
                f"{_format_float(metrics.get(f'Ignored@{k}', 0.0))} | "
                f"{_format_float(metrics.get(f'NDCG@{k}', 0.0))} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Data Coverage",
            "",
            f"- Recommendation papers evaluated across variants: `{total_papers}`",
            f"- Labeled papers available: `{sum(label_counts.values())}`",
            "- Reports are local artifacts under `reports/` and are ignored by git.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(payload: dict, output_dir: Path | str) -> tuple[Path, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()
    json_path = output_path / f"evaluation_{stamp}.json"
    markdown_path = output_path / f"evaluation_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_report(payload), encoding="utf-8")
    return json_path, markdown_path

