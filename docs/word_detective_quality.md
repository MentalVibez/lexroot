# Word Detective Quality

Word Detective separates modern phonics behavior from spelling history.

Curated spelling evidence lives in:

```text
Words/sources/spelling_history.csv
```

Recommended fields:

```csv
word,phonics_rule_applies,standard_phonics_rule,spelling_history_type,exception_reason,spelling_explanation,root_influence,evidence_grade,confidence_reason
```

Allowed `spelling_history_type` values:

```text
regular_phonics
latin_learned_spelling
greek_learned_spelling
french_borrowing
old_english_survival
great_vowel_shift
silent_letter_restoration
scribal_convention
analogy
foreign_borrowing
unknown
```

Rules:

- A word can be a phonics exception without being a root-based historical
  exception.
- Historical spellings need an `exception_reason`.
- High-confidence explanations need evidence and a `confidence_reason`.
