"""
Medical Terms Importer — supplements the master lexicon with clinical,
pharmaceutical, and psychological terminology from three sources:

  1. ICD-10-CM (kamillamagna/ICD-10-CSV on GitHub)
     ~120k rows; extracts unique parent category names + descriptions.

  2. glutanimate/wordlist-medicalterms-en (GitHub)
     ~8.5k standalone medical/anatomical/pharmaceutical terms.

  3. Curated acronyms & DSM-5 terms
     Medical/psychiatric abbreviations not covered by any automated source.

Output: Words/medical_terms.csv
  Columns: word, definition, origin_language, language_family, historical_context

Deduplicates against Words/english_words_master_lexicon.csv so the supplement
contains ONLY net-new terms. Run words_merge_importer.py afterwards to fold
medical_terms.csv into the master lexicon.

Usage:
  python3 -m ingestor.medical_importer
  python3 -m ingestor.medical_importer --dry-run
  python3 -m ingestor.medical_importer --no-fetch      # use cached downloads
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
from pathlib import Path

WORDS_DIR = Path(__file__).parent.parent / "Words"
MASTER_LEXICON   = WORDS_DIR / "english_words_master_lexicon.csv"
OUTPUT           = WORDS_DIR / "medical_terms.csv"
ICD10_CACHE      = WORDS_DIR / ".icd10_cache.csv"
GLUTANIMATE_CACHE = WORDS_DIR / ".glutanimate_medical.txt"

ICD10_URL = "https://raw.githubusercontent.com/kamillamagna/ICD-10-CSV/master/codes.csv"
GLUTANIMATE_URL = (
    "https://raw.githubusercontent.com/glutanimate/wordlist-medicalterms-en"
    "/master/wordlist.txt"
)

OUTPUT_FIELDS = ["word", "definition", "origin_language", "language_family", "historical_context"]

# ---------------------------------------------------------------------------
# Curated list: acronyms & DSM-5/ICD terms with no automated source
# ---------------------------------------------------------------------------
CURATED_TERMS: list[tuple[str, str, str, str]] = [
    # (word, definition, origin_language, historical_context)
    # Psychiatric / psychological acronyms
    ("ADHD",  "Attention-Deficit/Hyperactivity Disorder; a neurodevelopmental condition characterised by inattention, hyperactivity, and impulsivity.", "English", "Coined in DSM-III-R (1987); replaced 'ADD'."),
    ("PTSD",  "Post-Traumatic Stress Disorder; an anxiety disorder triggered by experiencing or witnessing traumatic events.", "English", "Formalised in DSM-III (1980) after Vietnam War studies."),
    ("OCD",   "Obsessive-Compulsive Disorder; characterised by intrusive obsessions and compulsive behaviours.", "English", "Recognised as a distinct disorder in DSM-III (1980)."),
    ("BPD",   "Borderline Personality Disorder; characterised by emotional dysregulation, unstable relationships, and identity disturbance.", "English", "Added to DSM-III (1980)."),
    ("GAD",   "Generalised Anxiety Disorder; persistent, excessive worry across multiple domains of life.", "English", "Introduced in DSM-III (1980)."),
    ("NPD",   "Narcissistic Personality Disorder; a pervasive pattern of grandiosity, need for admiration, and lack of empathy.", "English", "Added to DSM-III (1980)."),
    ("ASD",   "Autism Spectrum Disorder; a neurodevelopmental condition affecting social communication and characterised by restricted, repetitive behaviours.", "English", "Unified under a single spectrum diagnosis in DSM-5 (2013)."),
    ("FASD",  "Fetal Alcohol Spectrum Disorder; a range of conditions caused by prenatal alcohol exposure.", "English", "Term adopted in 2004 by the CDC and NIH."),
    ("TBI",   "Traumatic Brain Injury; an acquired injury to the brain caused by an external physical force.", "English", "Medical terminology standardised in the 1990s."),
    ("ASPD",  "Antisocial Personality Disorder; a pattern of disregard for, and violation of, the rights of others.", "English", "Defined in DSM-III (1980)."),
    ("MDD",   "Major Depressive Disorder; a mood disorder characterised by persistent depressed mood or loss of interest.", "English", "Formalised in DSM-III (1980)."),
    ("SAD",   "Seasonal Affective Disorder or Social Anxiety Disorder depending on context; mood disorder with seasonal pattern.", "English", "Seasonal subtype recognised in DSM-III-R (1987)."),
    ("CPTSD", "Complex Post-Traumatic Stress Disorder; PTSD arising from prolonged, repeated trauma.", "English", "Recognised in ICD-11 (2019) but not yet in DSM."),
    ("DID",   "Dissociative Identity Disorder; formerly Multiple Personality Disorder; characterised by two or more distinct identity states.", "English", "Renamed from MPD in DSM-IV (1994)."),
    # Medical imaging / diagnostic acronyms
    ("MRI",   "Magnetic Resonance Imaging; a non-invasive imaging technique using magnetic fields and radio waves to visualise internal body structures.", "English", "Developed in the 1970s; first clinical use ~1980."),
    ("CT",    "Computed Tomography (also CAT scan); an imaging procedure that uses X-rays to create cross-sectional images of the body.", "English", "Invented by Godfrey Hounsfield; first clinical scan 1971."),
    ("PET",   "Positron Emission Tomography; a nuclear imaging technique that measures metabolic activity in tissues.", "English", "Developed at Washington University in the 1970s."),
    ("EEG",   "Electroencephalography; a method of recording electrical activity of the brain via scalp electrodes.", "English", "Pioneered by Hans Berger, 1924."),
    ("ECG",   "Electrocardiogram (also EKG); a recording of the electrical activity of the heart.", "English", "Developed by Willem Einthoven, Nobel Prize 1924."),
    ("EKG",   "Electrocardiogram; recording of cardiac electrical activity. EKG from German 'Elektrokardiogramm'.", "German", "Alternative abbreviation from German; commonly used in North America."),
    ("fMRI",  "Functional Magnetic Resonance Imaging; measures brain activity by detecting changes in blood oxygenation.", "English", "Developed at Bell Labs, first published 1992."),
    ("DEXA",  "Dual-Energy X-ray Absorptiometry; a scan used to measure bone density.", "English", "Clinical use began in the late 1980s."),
    ("PFT",   "Pulmonary Function Test; a group of tests that measure how well the lungs work.", "English", "Standardised testing protocols developed through the 20th century."),
    # Hospital / clinical settings
    ("ICU",   "Intensive Care Unit; a specialised hospital ward providing intensive medical monitoring and care.", "English", "Modern ICUs developed from polio wards in the 1950s."),
    ("ER",    "Emergency Room; the hospital department treating acute illness and trauma.", "English", "US term; equivalent to A&E (Accident and Emergency) in the UK."),
    ("OR",    "Operating Room; a sterile environment in a hospital used for surgical procedures.", "English", "Standardised as a dedicated space in the late 19th century."),
    ("IV",    "Intravenous; referring to the administration of substances directly into a vein.", "Latin", "From Latin 'intra' (within) + 'vena' (vein)."),
    ("BP",    "Blood Pressure; the force exerted by circulating blood on the walls of blood vessels.", "English", "Measured clinically since Scipione Riva-Rocci's sphygmomanometer, 1896."),
    # Classification systems
    ("DSM",   "Diagnostic and Statistical Manual of Mental Disorders; the American Psychiatric Association's classification of mental disorders.", "English", "First published in 1952; DSM-5 is the current edition (2013, revised 2022)."),
    ("ICD",   "International Classification of Diseases; the WHO's global standard for health data and clinical diagnoses.", "English", "Origins in the 1850s Bertillon Classification; current edition ICD-11 (2022)."),
    ("SNOMED","Systematized Nomenclature of Medicine; a comprehensive clinical terminology used in electronic health records.", "English", "Originally developed by the College of American Pathologists (1965)."),
    # Psychotherapy modalities
    ("CBT",   "Cognitive Behavioural Therapy; a structured psychotherapy targeting the relationship between thoughts, feelings, and behaviours.", "English", "Developed by Aaron Beck in the 1960s."),
    ("DBT",   "Dialectical Behaviour Therapy; a CBT-based therapy originally developed for borderline personality disorder.", "English", "Developed by Marsha Linehan in the late 1980s."),
    ("EMDR",  "Eye Movement Desensitisation and Reprocessing; a trauma psychotherapy using bilateral stimulation.", "English", "Developed by Francine Shapiro, first published 1989."),
    ("ACT",   "Acceptance and Commitment Therapy; a 'third-wave' behavioural therapy based on psychological flexibility.", "English", "Developed by Steven Hayes in the 1980s."),
    ("MBSR",  "Mindfulness-Based Stress Reduction; an evidence-based programme using mindfulness meditation.", "English", "Developed by Jon Kabat-Zinn at UMass Medical School, 1979."),
    # Neuroscience
    ("CNS",   "Central Nervous System; the brain and spinal cord collectively.", "English", "Standard anatomical term established in the 19th century."),
    ("PNS",   "Peripheral Nervous System; the nervous tissue outside the brain and spinal cord.", "English", "Anatomical division formalised in classical neurology."),
    ("ANS",   "Autonomic Nervous System; the division of the nervous system controlling involuntary functions.", "English", "Termed 'autonomic' by John Newport Langley, 1898."),
    ("HPA",   "Hypothalamic-Pituitary-Adrenal axis; the neuroendocrine system regulating the stress response.", "English", "Research into the axis accelerated after Hans Selye's stress theory, 1950s."),
    ("GABA",  "Gamma-Aminobutyric Acid; the primary inhibitory neurotransmitter in the central nervous system.", "English", "First isolated and identified as a brain constituent in 1950."),
    # DSM-5 major diagnostic categories (not acronyms but uncommon as standalone words)
    ("Neurocognitive",      "Relating to cognitive functions and their neurological basis; as in 'neurocognitive disorder'.", "Greek/Latin", "From Greek 'neuron' + Latin 'cognoscere'; clinical use expanded with DSM-5 (2013)."),
    ("Somatic",             "Relating to the body as distinct from the mind; 'somatic symptom disorder' involves physical symptoms with psychological components.", "Greek", "From Greek 'soma' (body); distinguished from psychosomatic in DSM-5."),
    ("Dysthymia",           "A mild but long-term form of depression; now termed Persistent Depressive Disorder in DSM-5.", "Greek", "From Greek 'dys' (bad) + 'thymos' (mind/spirit)."),
    ("Cyclothymia",         "A mild form of bipolar disorder characterised by cycling mood episodes that are less severe than full mania or depression.", "Greek", "From Greek 'kyklos' (circle) + 'thymos' (mind)."),
    ("Trichotillomania",    "A compulsive urge to pull out one's own hair, classified as an obsessive-compulsive related disorder in DSM-5.", "Greek", "From Greek 'thrix' (hair) + 'tillein' (to pull) + 'mania'."),
    ("Dermatillomania",     "Compulsive skin picking; classified under obsessive-compulsive and related disorders.", "Greek/Latin", "From Greek 'derma' (skin) + Latin 'tillomania'."),
    ("Misophonia",          "Extreme sensitivity or aversion to specific sounds; under research as a distinct disorder.", "Greek", "From Greek 'misos' (hatred) + 'phone' (sound); term coined by Pawel and Margaret Jastreboff, 2000."),
    ("Alexithymia",         "Difficulty identifying and describing one's own emotions; associated with autism and PTSD.", "Greek", "Coined by Peter Sifneos from Greek 'a' (without) + 'lexis' (word) + 'thymos' (emotion), 1972."),
    ("Anhedonia",           "The inability to feel pleasure in normally pleasurable activities; a core symptom of depression.", "Greek", "From Greek 'an' (without) + 'hedone' (pleasure)."),
    ("Hypervigilance",      "A state of being abnormally alert to potential threats; a hallmark of PTSD and anxiety disorders.", "Greek/Latin", "From Greek 'hyper' (over) + Latin 'vigilantia' (watchfulness)."),
    ("Anosognosia",         "The lack of awareness or denial of one's own illness or disability; common in schizophrenia and dementia.", "Greek", "From Greek 'a' (without) + 'nosos' (disease) + 'gnosis' (knowledge)."),
    ("Confabulation",       "The production of fabricated or distorted memories without conscious deception; associated with Korsakoff syndrome.", "Latin", "From Latin 'confabulari' (to chat together)."),
    ("Perseveration",       "The repetition of a particular response regardless of the stimulus; associated with brain injury and autism.", "Latin", "From Latin 'perseverare' (to persist)."),
]

# Noise words to exclude when extracting terms from ICD-10 descriptions
_STOP_WORDS = {
    "a", "an", "the", "of", "and", "or", "in", "with", "due", "to", "by",
    "for", "from", "as", "at", "is", "are", "on", "not", "no", "other",
    "unspecified", "following", "without", "subsequent", "encounter",
    "initial", "sequela", "type", "nos", "nec", "excluding", "including",
    "certain", "elsewhere", "classified",
}

# Exclude ICD entries whose descriptions match these patterns (too specific)
_EXCLUSION_RE = re.compile(
    r"\b(due to|unspecified|without|with coma|following|"
    r"nonketotic|subsequent encounter|sequela|initial encounter)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _fetch(url: str, cache: Path, label: str, skip: bool) -> str | None:
    if cache.exists():
        print(f"  [cache] {label}")
        return cache.read_text(encoding="utf-8")
    if skip:
        print(f"  [skip] {label} (--no-fetch, no cache)")
        return None
    print(f"  Downloading {label} …")
    try:
        urllib.request.urlretrieve(url, cache)
        return cache.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [warn] Failed: {e}", file=sys.stderr)
        return None


def load_icd10(raw: str) -> dict[str, str]:
    """
    Returns word → definition for unique, clean parent category names.
    Prioritises exact-match rows where description == parent_label.
    """
    by_parent: dict[str, list[str]] = {}

    for line in raw.splitlines():
        try:
            parts = next(csv.reader([line]))
        except StopIteration:
            continue
        if len(parts) < 6:
            continue

        description = parts[3].strip().strip('"')
        parent = parts[5].strip().strip('"')

        if not parent or not description:
            continue
        if _EXCLUSION_RE.search(description):
            continue

        by_parent.setdefault(parent, []).append(description)

    result: dict[str, str] = {}
    for term, descriptions in by_parent.items():
        # Prefer the shortest description (most generic) that isn't just the term itself
        non_trivial = [d for d in descriptions if d.lower() != term.lower()]
        best = min(non_trivial, key=len) if non_trivial else descriptions[0]
        result[term] = best

    return result


def load_glutanimate(raw: str) -> list[str]:
    """Returns list of single-word medical terms."""
    terms = []
    for line in raw.splitlines():
        word = line.strip()
        # Keep only alphabetic single words; skip chemical compound notation
        if word and re.match(r"^[A-Za-z][a-z]{2,}$", word):
            terms.append(word.capitalize())
    return terms


# ---------------------------------------------------------------------------
# Dedup check
# ---------------------------------------------------------------------------

def load_existing_words() -> set[str]:
    if not MASTER_LEXICON.exists():
        return set()
    words = set()
    with MASTER_LEXICON.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = row.get("word", "").strip()
            if w:
                words.add(w.lower())
    return words


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_supplement(skip_fetch: bool = False, dry_run: bool = False) -> None:
    print("=== Medical Terms Importer ===\n")

    print("[1/5] Loading existing master lexicon for dedup …")
    existing = load_existing_words()
    print(f"  {len(existing):,} words already in master lexicon")

    print("\n[2/5] Fetching ICD-10-CM …")
    icd_raw = _fetch(ICD10_URL, ICD10_CACHE, "ICD-10-CM CSV", skip_fetch)
    icd_terms: dict[str, str] = load_icd10(icd_raw) if icd_raw else {}
    print(f"  {len(icd_terms):,} unique parent category names extracted")

    print("\n[3/5] Fetching glutanimate medical wordlist …")
    glut_raw = _fetch(GLUTANIMATE_URL, GLUTANIMATE_CACHE, "glutanimate wordlist", skip_fetch)
    glut_terms: list[str] = load_glutanimate(glut_raw) if glut_raw else []
    print(f"  {len(glut_terms):,} single-word medical terms extracted")

    print("\n[4/5] Building supplement (deduplicating against master lexicon) …")
    seen: set[str] = set()
    rows: list[dict] = []

    def add(word: str, definition: str = "", origin: str = "", family: str = "", context: str = "") -> None:
        key = word.strip().lower()
        if key in existing or key in seen:
            return
        seen.add(key)
        rows.append({
            "word": word.strip(),
            "definition": definition,
            "origin_language": origin,
            "language_family": family,
            "historical_context": context,
        })

    # Priority 1: curated acronyms and DSM terms (most valuable, hand-crafted)
    for word, defn, origin, context in CURATED_TERMS:
        family = (
            "Indo-European (Italic)" if origin == "Latin" else
            "Indo-European (Hellenic)" if origin == "Greek" else
            "Indo-European (Germanic)" if origin in ("German", "English") else
            "Indo-European" if "/" in origin else ""
        )
        add(word, defn, origin, family, context)

    curated_added = len(rows)
    print(f"  Curated acronyms/DSM terms: {curated_added} new")

    # Priority 2: ICD-10 parent category names with their descriptions
    for term, defn in sorted(icd_terms.items()):
        add(term, defn)
    icd_added = len(rows) - curated_added
    print(f"  ICD-10 category names:       {icd_added} new")

    # Priority 3: glutanimate single-word medical terms (no definition)
    for term in sorted(set(glut_terms)):
        add(term)
    glut_added = len(rows) - curated_added - icd_added
    print(f"  glutanimate medical words:   {glut_added} new")

    total = len(rows)
    print(f"\n  Total net-new medical terms: {total:,}")

    if dry_run:
        print("\n[dry_run] First 20 rows:")
        for r in rows[:20]:
            defn = r["definition"][:70] + "…" if len(r["definition"]) > 70 else r["definition"]
            print(f"  {r['word']:<30s}  {defn}")
        print("  (no file written)")
        return

    print(f"\n[5/5] Writing → {OUTPUT} …")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["word"].lower()))

    print(f"[done] {total:,} medical terms written to {OUTPUT.name}")
    print(f"\nNext step — fold into master lexicon:")
    print(f"  python3 -m ingestor.words_merge_importer")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Words/medical_terms.csv from ICD-10 and medical wordlists.")
    parser.add_argument("--no-fetch", action="store_true", help="Use local cache only; skip downloads.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    args = parser.parse_args()
    build_supplement(skip_fetch=args.no_fetch, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
