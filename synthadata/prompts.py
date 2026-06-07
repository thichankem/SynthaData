"""Lớp dựng prompt: biến domain + ngữ cảnh thành lời nhắc cho model."""

from __future__ import annotations

from .schema import Domain

_DEFAULT_SYSTEM = (
    "You are a meticulous domain data engineer who builds high-quality datasets "
    "to train other machine-learning models. You output ONLY valid JSON. "
    "Every record must be factually accurate, specific, self-consistent, and "
    "clearly distinct from the others. Never invent fake placeholder values."
)


def build_system_prompt(domain: Domain) -> str:
    return domain.system.strip() or _DEFAULT_SYSTEM


def build_user_prompt(
    domain: Domain,
    *,
    batch_size: int,
    facet: str | None,
    avoid: list[str],
) -> str:
    """Dựng prompt yêu cầu model sinh `batch_size` bản ghi cho domain."""
    field_specs = "\n".join(col.spec_line() for col in domain.columns)

    focus = ""
    if facet:
        focus = (
            f"\nFOCUS for this batch: concentrate on \"{facet}\". "
            f"Generate items that belong to this slice of the topic.\n"
        )

    avoid_block = ""
    if avoid:
        listed = ", ".join(f'"{a}"' for a in avoid)
        avoid_block = (
            f"\nDo NOT generate any of these already-collected items "
            f"(produce different ones): {listed}.\n"
        )

    return f"""Generate {batch_size} UNIQUE, real records for a dataset about:
{domain.topic}
{focus}
Each record is a JSON object with EXACTLY these fields (use these exact keys):
{field_specs}

Hard rules:
- Output language for text fields: {domain.language}.
- Be factually accurate and concrete. NO placeholders, NO "N/A", NO empty strings.
- Every record must be clearly distinct from the others in this batch.
- Keep each text field concise but informative (about 1-3 sentences).
- For enum fields, pick exactly one allowed value.
{avoid_block}
Return ONE JSON object of this exact shape and NOTHING else:
{{"records": [ {{ ...one object per record using the keys above... }} ]}}"""
