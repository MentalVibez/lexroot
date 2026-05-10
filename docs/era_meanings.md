# Era Meanings

Era meanings should describe what an entry meant when it was actually used, as
close to source evidence as the project can support.

## Minimum Evidence Standard

Use an era meaning only when you can attach at least one of these:

- A dated quotation or usage example from a primary text.
- A historical dictionary entry with a date range or first-attestation note.
- A trusted lexical source that explicitly names the historical sense.

If the evidence is inferred from etymology rather than attested usage, mark the
row `confidence=low` and say that in `notes`.

## CSV Fields

The clean import file supports era records in `semantic_drift_history` JSON, or
these structured columns:

```csv
era_name,start_year,end_year,meaning,usage_example,source_slug,confidence,notes
```

Recommended meanings:

- `meaning`: period-specific sense, not the modern definition.
- `usage_example`: short source-backed phrase or sentence.
- `source_slug`: a source registered in the source catalog when possible.
- `confidence`: `high`, `medium`, or `low`.
- `notes`: uncertainty, dating caveats, or why the era assignment is inferred.

## Workflow

1. Add or revise rows in curated source files such as `Words/sources/idioms.csv`.
2. Build the one-file feed:

```bash
python3 -m ingestor.lexicon_build_importer
```

3. Preview database import:

```bash
python3 -m ingestor.words_csv_importer --path Words/build/lexicon_import.csv --dry-run
```

4. Import when the preview looks right:

```bash
python3 -m ingestor.words_csv_importer --path Words/build/lexicon_import.csv --batch-size 2000
```

## Idioms

Idioms should use `entry_type=idiom`. Put the modern idiomatic sense in
`figurative_meaning`, the literal surface reading in `literal_meaning`, and the
historical period-specific sense in the era fields.
