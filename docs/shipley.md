# Shipley Source Workflow

Source:

Joseph T. Shipley, *The Origins of English Words: A Discursive Dictionary of
Indo-European Roots*. Johns Hopkins University Press, 1984.

This is a copyrighted book. The project should not ingest bulk text, dictionary
entries, scans, OCR, or long quoted passages from it.

## Safe Use

Use Shipley as citation-backed evidence for compact root claims:

```csv
word,source_form,source_language,root_meaning,relation_type,confidence,page,short_note
```

Rows belong in:

```text
Words/sources/shipley_roots.csv
```

Keep `short_note` brief and factual. Prefer your own paraphrase and page number.

## Import

Preview:

```bash
python3 -m ingestor.shipley_importer --dry-run
```

Import to Neo4j:

```bash
python3 -m ingestor.shipley_importer
```

## Why This Shape

Shipley is most useful as an additional etymological authority for
Indo-European root links. It should supplement stronger source-specific claims,
not replace source-ranked evidence from OED, Watkins, de Vaan, Beekes, or
direct historical dictionaries.
