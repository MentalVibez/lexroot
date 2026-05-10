# Data Quality Standards

The project treats lexical history as evidence-backed claims, not just enriched
word rows.

## Evidence Grades

| Grade | Meaning |
|---|---|
| `A` | Primary dated quotation, manuscript, or corpus attestation |
| `B` | Historical dictionary with date, quotation, entry, or citation |
| `C` | Specialist scholarly source or etymological dictionary |
| `D` | Modern dictionary or secondary summary |
| `E` | Inference from etymology or root evidence only |

## Confidence Rules

- `confidence=high` requires a source slug and precise citation evidence.
- `meaning_type=inferred_from_etymology` must use `evidence_grade=E`.
- Root meaning is not the same thing as period usage.
- Disputed idiom origins and folk etymologies cannot be high confidence.
- Every high-confidence claim should explain why in `confidence_reason`.

## Citation Fields

Use the most specific fields available:

```csv
source_slug,citation,page,entry_headword,source_url,access_date
```

For copyrighted sources, store compact citations and paraphrases. Do not paste
bulk source text into the repository.

## Review Status

Use `review_status` to make cleanup queueable:

```text
needs_review
reviewed
needs_source
disputed
deprecated
```
