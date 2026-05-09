"""
Prompt templates for the AI explanation features.
Pure string construction — no LLM instantiation here.
Extracted from api/ai_engine.py so prompts are independently testable and overridable.
"""

CONTEXT_INSTRUCTIONS: dict[str, str] = {
    "biblical":  "The reader is working through a KJV Bible passage. Lean on biblical examples (1611 translation, Paul's letters, Psalms). ",
    "legal":     "The reader is working through a historical legal document. Lean on examples from common law or legal Latin. ",
    "literary":  "The reader is working through Shakespeare or a Renaissance play. Lean on Elizabethan dramatic usage. ",
    "medical":   "The reader is working through a historical medical text. Lean on Galenic humoral medicine or early clinical writing. ",
}


def build_drift_prompt(
    word: str,
    root: str,
    root_meaning: str,
    root_origin: str,
    cognates: list[str],
    definition: str,
    context_hint: str | None = None,
    era_meanings: list[dict] | None = None,
) -> str:
    """Hybrid Contrast + Storytelling + Analogy prompt for non-scholar readers."""
    cognate_str = ", ".join(cognates) if cognates else "none on record"
    context_instruction = CONTEXT_INSTRUCTIONS.get(context_hint or "", "")

    era_block = ""
    authority_line = ""
    if era_meanings:
        lines = [
            f"  - {e['era_name']} ({e['era_start']}–{e['era_end']}): \"{e['meaning']}\""
            + (f" [{e['source_short_name']}]" if e.get("source_short_name") else "")
            + (f" — e.g. \"{e['usage_example']}\"" if e.get("usage_example") else "")
            for e in era_meanings
        ]
        era_block = "DOCUMENTED MEANINGS THROUGH TIME:\n" + "\n".join(lines) + "\n\n"

        tier_sources = sorted({
            e["source_short_name"]
            for e in era_meanings
            if e.get("source_short_name") and (e.get("source_tier") or 99) <= 2
        })
        if tier_sources:
            authority_line = f"SOURCES: {', '.join(tier_sources)}\n\n"

    return f"""You are an etymologist and historian writing for a curious general reader — not a scholar.
They hit the word "{word}" in an old text and are confused because it doesn't mean what they expect.

WORD: {word}
CURRENT DEFINITION: {definition}
ANCESTRAL ROOT: {root} (from {root_origin}, meaning "{root_meaning}")
WORD FAMILY (words sharing this root): {cognate_str}

{authority_line}{era_block}{context_instruction}Your task: explain in plain English how "{word}" traveled from its root meaning to today's meaning.

Follow this exact structure:

1. THEN vs NOW (2 sentences): State the historical meaning. State the modern meaning.
2. THE TURNING POINT (3–4 sentences): Name the specific century, religion, social class, or event that caused the shift. Never say "language just changes" — say WHY it changed.
3. THE ANALOGY (1–2 sentences): Start with "Think of how..." — find a vivid modern parallel that makes the shift feel obvious.
4. THE WORD FAMILY CLUE (1–2 sentences): Show how one word from ({cognate_str}) reveals the older meaning more clearly than "{word}" does alone.

Rules: No jargon without a plain-English gloss in parentheses. Under 200 words total. Write like a brilliant, slightly theatrical history teacher — not a textbook. When citing a historical meaning, name the source in brackets exactly as shown in the DOCUMENTED MEANINGS section."""


def build_era_explanation_prompt(
    word: str,
    era_name: str,
    era_start: int,
    era_end: int,
    era_summary: str,
    historical_meaning: str | None,
    usage_example: str | None,
    modern_definition: str,
    root: str,
    root_meaning: str,
    passage_snippet: str | None = None,
    source_short_name: str | None = None,
) -> str:
    snippet_line = f'\nREADER\'S PASSAGE: "{passage_snippet}"\n' if passage_snippet else ""
    example_line = f'\nPERIOD EXAMPLE: "{usage_example}"\n' if usage_example else ""
    source_citation = f" [{source_short_name}]" if source_short_name else ""
    meaning_line = (historical_meaning or "no documented meaning survives from this period") + source_citation

    return f"""You are a historian and language guide helping a modern reader understand a word in context.
The reader is working through a text from the {era_name} period ({era_start}–{era_end}).
{snippet_line}
WORD: {word}
WHAT IT MEANT IN {era_name.upper()}: {meaning_line}
WHAT IT MEANS TODAY: {modern_definition}
ROOT: {root} (meaning: "{root_meaning}")
{example_line}HISTORICAL CONTEXT: {era_summary}

In 3–5 sentences: state the in-era meaning plainly and confidently (no hedging).
If a passage snippet was provided, explain how this meaning makes that passage make sense.
Close with one sentence on why the modern meaning is misleading here.
No jargon. Write for a thoughtful reader who is not a linguist. Cite the source in brackets once when you state the historical meaning."""
