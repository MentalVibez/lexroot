# Senses And Attestations

Historical accuracy depends on separating words from meanings and meanings from
evidence.

## Senses

Curated senses live in:

```text
Words/sources/senses.csv
```

Required fields:

```csv
sense_id,word,definition
```

Recommended `sense_id` format:

```text
prevent.v.early-modern.001
```

Important fields:

```csv
meaning_type,era_name,first_attested_year,last_attested_year,source_slug,confidence
```

Use `meaning_type=inferred_from_etymology` only when no dated usage evidence is
available. Do not treat root meaning as period usage.

Scholarly evidence fields:

```csv
evidence_grade,confidence_reason,citation,page,entry_headword,source_url,access_date,review_status
```

High-confidence senses should have `evidence_grade=A` or `B`, or `C` with a
precise citation. Inferred root meanings should use `evidence_grade=E` and
should not be marked high confidence.

Semantic-change fields:

```csv
semantic_change_type,origin_status,usage_region,usage_register,first_attested_source
```

Allowed `semantic_change_type` values include `broadening`, `narrowing`,
`amelioration`, `pejoration`, `metaphor`, `metonymy`, `bleaching`,
`specialization`, `euphemism`, `folk_etymology`, `reanalysis`, and `unknown`.

## Attestations

Evidence rows live in:

```text
Words/sources/attestations.csv
```

Each row should point to a `sense_id`.

Preferred evidence order:

1. Primary dated quotation.
2. Historical dictionary with quotation/date.
3. Corpus citation.
4. Specialist dictionary.
5. Inference from etymology.

Use `evidence_grade=A` for primary dated quotations and `B` for historical
dictionary evidence with a date, quotation, entry, or citation.

## Import

Preview:

```bash
python3 -m ingestor.senses_importer --dry-run
```

Import:

```bash
python3 -m ingestor.senses_importer
```

API:

```text
GET /pg/word/{word}/senses
GET /pg/sense/{sense_id}
GET /pg/sense/{sense_id}/attestations
```
