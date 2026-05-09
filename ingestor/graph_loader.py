"""
LexiconIngestor: writes etymology data into Neo4j using MERGE (idempotent).
Running the ingestor twice on the same word will update it, never duplicate it.

Graph schema:
  (Word {name, language, definition})
  (Root {name, meaning, origin_language})
  (Era {name, start_year, end_year, summary, register})
  (Source {slug, short_name, full_name, author, year, category, authority_tier})
  (Word)-[:DESCENDED_FROM {attested_year}]->(Root)
  (Word)-[:COGNATE_WITH]->(Word)
  (Word)-[:HAD_MEANING_IN {meaning, usage_example, register, source, confidence}]->(Era)
  (Word)-[:ATTESTED_IN {context}]->(Source)
  (Word)-[:TRANSLATION_OF {context}]->(Word)
"""
import os
from dataclasses import dataclass, field
from hashlib import sha1
from neo4j import GraphDatabase, Driver


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lexicon_secret")


@dataclass
class EtymologyClaim:
    source_form: str
    source_language: str
    relation_type: str
    source_slug: str
    confidence: str = "medium"
    note: str = ""
    original_form: str | None = None
    is_reconstructed: bool = False
    intermediate_path: list[str] = field(default_factory=list)


@dataclass
class WordEntry:
    name: str
    language: str
    definition: str
    root_name: str
    root_meaning: str
    root_origin_language: str
    attested_year: int | None = None
    cognates: list[str] | None = None
    # Each dict: {era_name, meaning, usage_example, register, source, confidence}
    era_meanings: list[dict] | None = None
    etymology_claims: list[EtymologyClaim] | None = None


class LexiconIngestor:
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def ensure_indexes(self):
        """Create full-text, uniqueness, and era indexes on first run."""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT word_unique IF NOT EXISTS FOR (w:Word) REQUIRE (w.name, w.language) IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT root_unique IF NOT EXISTS FOR (r:Root) REQUIRE r.name IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT etymology_claim_unique IF NOT EXISTS FOR (c:EtymologyClaim) REQUIRE c.id IS UNIQUE"
            )
            session.run(
                "CREATE FULLTEXT INDEX word_search IF NOT EXISTS FOR (w:Word) ON EACH [w.name, w.definition]"
            )
        self.ensure_era_indexes()
        self.ensure_source_indexes()

    def ensure_era_indexes(self):
        """Create Era uniqueness constraint and year-range index."""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT era_unique IF NOT EXISTS FOR (e:Era) REQUIRE e.name IS UNIQUE"
            )
            session.run(
                "CREATE INDEX era_years IF NOT EXISTS FOR (e:Era) ON (e.start_year, e.end_year)"
            )

    def ensure_source_indexes(self):
        """Create Source uniqueness constraint."""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT source_unique IF NOT EXISTS FOR (s:Source) REQUIRE s.slug IS UNIQUE"
            )

    def ingest_source(self, source: dict) -> None:
        """Upsert a Source node. Safe to call multiple times — MERGE guarantees no duplicates."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (s:Source {slug: $slug})
                SET s.short_name     = $short_name,
                    s.full_name      = $full_name,
                    s.author         = $author,
                    s.year           = $year,
                    s.publisher      = $publisher,
                    s.category       = $category,
                    s.authority_tier = $authority_tier,
                    s.description    = $description
                """,
                slug=source["slug"],
                short_name=source["short_name"],
                full_name=source["full_name"],
                author=source.get("author"),
                year=source.get("year"),
                publisher=source.get("publisher"),
                category=source["category"],
                authority_tier=source["authority_tier"],
                description=source.get("description", ""),
            )

    def write_attested_in(self, word: str, language: str, source_slug: str, context: str = "") -> None:
        """Create or update an ATTESTED_IN edge from a Word to a Source node."""
        with self.driver.session() as session:
            session.execute_write(self._write_attested_in, word, language, source_slug, context)

    @staticmethod
    def _write_attested_in(tx, word: str, lang: str, source_slug: str, context: str):
        tx.run(
            """
            MATCH (w:Word {name: $word, language: $lang})
            MATCH (s:Source {slug: $slug})
            MERGE (w)-[a:ATTESTED_IN]->(s)
            SET a.context = $context
            """,
            word=word, lang=lang, slug=source_slug, context=context,
        )

    def annotate_frequency(
        self,
        word: str,
        language: str,
        source_slug: str,
        frequency: float | None = None,
        rank: int | None = None,
        zipf: float | None = None,
    ) -> None:
        """Attach frequency/rank metadata to a Word without creating duplicate nodes."""
        with self.driver.session() as session:
            session.execute_write(
                self._annotate_frequency,
                word,
                language,
                source_slug,
                frequency,
                rank,
                zipf,
            )

    @staticmethod
    def _annotate_frequency(
        tx,
        word: str,
        lang: str,
        source_slug: str,
        frequency: float | None,
        rank: int | None,
        zipf: float | None,
    ):
        tx.run(
            """
            MERGE (w:Word {name: $word, language: $lang})
            ON CREATE SET w.definition = "(frequency metadata only; definition pending enrichment)"
            SET w.frequency_source = $source_slug,
                w.frequency = coalesce($frequency, w.frequency),
                w.frequency_rank = coalesce($rank, w.frequency_rank),
                w.zipf_frequency = coalesce($zipf, w.zipf_frequency)
            WITH w
            MATCH (s:Source {slug: $source_slug})
            MERGE (w)-[a:ATTESTED_IN]->(s)
            SET a.context = "frequency metadata"
            """,
            word=word,
            lang=lang,
            source_slug=source_slug,
            frequency=frequency,
            rank=rank,
            zipf=zipf,
        )

    def annotate_validation(self, word: str, language: str, source_slug: str, tag: str = "") -> None:
        """Mark a Word as recognized by a validation word list."""
        with self.driver.session() as session:
            session.execute_write(self._annotate_validation, word, language, source_slug, tag)

    @staticmethod
    def _annotate_validation(tx, word: str, lang: str, source_slug: str, tag: str):
        tx.run(
            """
            MERGE (w:Word {name: $word, language: $lang})
            ON CREATE SET w.definition = "(validated headword; definition pending enrichment)"
            SET w.validation_sources =
                CASE
                    WHEN w.validation_sources IS NULL THEN [$source_slug]
                    WHEN $source_slug IN w.validation_sources THEN w.validation_sources
                    ELSE w.validation_sources + $source_slug
                END,
                w.validation_tags =
                CASE
                    WHEN $tag = "" THEN coalesce(w.validation_tags, [])
                    WHEN w.validation_tags IS NULL THEN [$tag]
                    WHEN $tag IN w.validation_tags THEN w.validation_tags
                    ELSE w.validation_tags + $tag
                END
            WITH w
            MATCH (s:Source {slug: $source_slug})
            MERGE (w)-[a:ATTESTED_IN]->(s)
            SET a.context = CASE WHEN $tag = "" THEN "validated headword" ELSE $tag END
            """,
            word=word,
            lang=lang,
            source_slug=source_slug,
            tag=tag,
        )

    def ingest(self, entry: WordEntry) -> None:
        """
        Upsert a word, its root, cognates, and era meanings into Neo4j.
        MERGE guarantees no duplicate nodes regardless of how many times this runs.
        """
        with self.driver.session() as session:
            session.execute_write(self._write_word_and_root, entry)
            for cognate in (entry.cognates or []):
                session.execute_write(self._write_cognate, entry.name, entry.language, cognate)
            for em in (entry.era_meanings or []):
                session.execute_write(
                    self._write_era_meaning,
                    entry.name, entry.language,
                    em["era_name"], em["meaning"],
                    em.get("usage_example"), em.get("register", "general"),
                    em.get("source", "manual"), em.get("confidence", "medium"),
                )
            for claim in self._claims_for_entry(entry):
                session.execute_write(self._write_etymology_claim, entry.name, entry.language, claim)

    @staticmethod
    def _claims_for_entry(entry: WordEntry) -> list[EtymologyClaim]:
        if entry.etymology_claims:
            return entry.etymology_claims
        if (
            entry.root_name.strip().casefold() == entry.name.strip().casefold()
            and entry.root_origin_language.strip().casefold() == "modern english"
        ):
            return []
        source_slug = "manual"
        if entry.era_meanings:
            source_slug = entry.era_meanings[0].get("source") or source_slug
        return [
            EtymologyClaim(
                source_form=entry.root_name,
                source_language=entry.root_origin_language,
                relation_type="descended_from",
                source_slug=source_slug,
                confidence="medium",
                note=entry.root_meaning,
                is_reconstructed=entry.root_origin_language.startswith("Proto-") or entry.root_name.startswith("*"),
            )
        ]

    @staticmethod
    def _write_word_and_root(tx, entry: WordEntry):
        tx.run(
            """
            MERGE (w:Word {name: $word, language: $lang})
            SET w.definition = $definition

            MERGE (r:Root {name: $root})
            ON CREATE SET r.meaning = $root_meaning, r.origin_language = $root_origin_lang
            ON MATCH  SET r.meaning = $root_meaning

            MERGE (w)-[d:DESCENDED_FROM]->(r)
            ON CREATE SET d.attested_year = $year
            """,
            word=entry.name,
            lang=entry.language,
            definition=entry.definition,
            root=entry.root_name,
            root_meaning=entry.root_meaning,
            root_origin_lang=entry.root_origin_language,
            year=entry.attested_year,
        )

    @staticmethod
    def _write_cognate(tx, word: str, language: str, cognate_name: str):
        tx.run(
            """
            MERGE (w:Word {name: $word, language: $lang})
            MERGE (c:Word {name: $cognate})
            MERGE (w)-[:COGNATE_WITH]->(c)
            MERGE (c)-[:COGNATE_WITH]->(w)
            """,
            word=word,
            lang=language,
            cognate=cognate_name,
        )

    @staticmethod
    def _claim_id(word: str, language: str, claim: EtymologyClaim) -> str:
        raw = "|".join([
            word.strip().casefold(),
            language.strip().casefold(),
            claim.source_form.strip().casefold(),
            claim.source_language.strip().casefold(),
            claim.relation_type.strip().casefold(),
            claim.source_slug.strip().casefold(),
            claim.note.strip().casefold(),
        ])
        return sha1(raw.encode("utf-8")).hexdigest()

    @classmethod
    def _write_etymology_claim(cls, tx, word: str, language: str, claim: EtymologyClaim):
        claim_id = cls._claim_id(word, language, claim)
        tx.run(
            """
            MERGE (w:Word {name: $word, language: $lang})
            MERGE (r:Root {name: $source_form})
            ON CREATE SET r.origin_language = $source_language
            ON MATCH SET r.origin_language = coalesce(r.origin_language, $source_language)
            MERGE (c:EtymologyClaim {id: $claim_id})
            SET c.relation_type = $relation_type,
                c.source_form = $source_form,
                c.original_form = $original_form,
                c.source_language = $source_language,
                c.confidence = $confidence,
                c.note = $note,
                c.is_reconstructed = $is_reconstructed,
                c.intermediate_path = $intermediate_path
            MERGE (w)-[:HAS_ETYMOLOGY_CLAIM]->(c)
            MERGE (c)-[:CLAIMS_SOURCE_FORM]->(r)
            WITH c
            OPTIONAL MATCH (s:Source {slug: $source_slug})
            FOREACH (_ IN CASE WHEN s IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:SUPPORTED_BY]->(s)
            )
            """,
            word=word,
            lang=language,
            claim_id=claim_id,
            relation_type=claim.relation_type,
            source_form=claim.source_form,
            original_form=claim.original_form,
            source_language=claim.source_language,
            confidence=claim.confidence,
            note=claim.note[:2000],
            is_reconstructed=claim.is_reconstructed,
            intermediate_path=claim.intermediate_path,
            source_slug=claim.source_slug,
        )

    def ingest_era_node(self, era: dict) -> None:
        """Upsert a single Era node. Safe to call multiple times."""
        with self.driver.session() as session:
            session.execute_write(self._ensure_era_node, era)

    @staticmethod
    def _ensure_era_node(tx, era: dict):
        tx.run(
            """
            MERGE (e:Era {name: $name})
            SET e.start_year = $start_year,
                e.end_year   = $end_year,
                e.summary    = $summary,
                e.register   = $register
            """,
            name=era["name"],
            start_year=era["start_year"],
            end_year=era["end_year"],
            summary=era.get("summary", ""),
            register=era.get("register", "general"),
        )

    @staticmethod
    def _write_era_meaning(tx, word: str, lang: str, era_name: str, meaning: str,
                            usage_example: str | None, register: str, source: str, confidence: str):
        tx.run(
            """
            MATCH (w:Word {name: $word, language: $lang})
            MATCH (e:Era {name: $era})
            MERGE (w)-[h:HAD_MEANING_IN]->(e)
            SET h.meaning       = $meaning,
                h.usage_example = $usage_example,
                h.register      = $register,
                h.source        = $source,
                h.confidence    = $confidence
            """,
            word=word, lang=lang, era=era_name,
            meaning=meaning, usage_example=usage_example,
            register=register, source=source, confidence=confidence,
        )

    def bulk_ingest(self, entries: list[WordEntry]) -> dict:
        """Ingest a list of entries, collecting any failures without stopping the batch."""
        results = {"ingested": 0, "failed": 0, "errors": []}
        for entry in entries:
            try:
                self.ingest(entry)
                results["ingested"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"word": entry.name, "error": str(e)})
        return results
