# Idiom Quality

Idioms should separate modern meaning, literal surface meaning, and origin
theory.

Recommended fields:

```csv
origin_theory,origin_theory_status,earliest_known_use_year,earliest_known_use_source,evidence_grade,confidence_reason
```

Allowed `origin_theory_status` values:

```text
attested
plausible
disputed
folk_etymology
unknown
```

Rules:

- Put the idiomatic meaning in `figurative_meaning`.
- Put the literal surface reading in `literal_meaning`.
- Mark popular but unsupported origin stories as `folk_etymology`.
- Do not present a disputed origin as fact.
- Prefer earliest known use evidence over attractive origin stories.
