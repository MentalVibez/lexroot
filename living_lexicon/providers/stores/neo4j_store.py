"""
Neo4j implementation of EtymologyStore.
All Cypher queries extracted from api/graph_client.py into the installable SDK.
"""
from __future__ import annotations
from neo4j import GraphDatabase, Driver

from living_lexicon.config import LexiconConfig


class Neo4jStore:
    """Read-only Neo4j query layer satisfying the EtymologyStore protocol."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    @classmethod
    def from_env(cls) -> "Neo4jStore":
        cfg = LexiconConfig()
        return cls(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)

    def close(self) -> None:
        self._driver.close()

    def ping(self) -> bool:
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    # ── Word queries ──────────────────────────────────────────────────────────

    def get_word(self, word: str) -> dict | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})
                OPTIONAL MATCH (w)-[:DESCENDED_FROM]->(r:Root)
                OPTIONAL MATCH (w)-[:COGNATE_WITH]->(cog:Word)
                RETURN
                    w.name        AS name,
                    w.language    AS language,
                    w.definition  AS definition,
                    r.name        AS root,
                    r.meaning     AS root_meaning,
                    r.origin_language AS root_origin,
                    collect(DISTINCT cog.name) AS cognates
                """,
                word=word.lower(),
            )
            record = result.single()
            return dict(record) if record else None

    def get_word_tree(self, word: str) -> dict:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[:DESCENDED_FROM]->(r:Root)
                MATCH (sibling:Word)-[:DESCENDED_FROM]->(r)
                OPTIONAL MATCH (sibling)-[:COGNATE_WITH]->(cousin:Word)
                RETURN
                    r.name            AS root,
                    r.meaning         AS root_meaning,
                    r.origin_language AS root_origin,
                    collect(DISTINCT {
                        name:       sibling.name,
                        language:   sibling.language,
                        definition: sibling.definition
                    }) AS family,
                    collect(DISTINCT cousin.name) AS extended_cognates
                """,
                word=word.lower(),
            )
            record = result.single()
            return dict(record) if record else {}

    def get_cognates(self, word: str) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[:DESCENDED_FROM]->(r:Root)
                      <-[:DESCENDED_FROM]-(sibling:Word)
                WHERE sibling.name <> $word
                RETURN DISTINCT
                    sibling.name       AS name,
                    sibling.language   AS language,
                    sibling.definition AS definition,
                    r.name             AS shared_root
                ORDER BY sibling.name
                """,
                word=word.lower(),
            )
            return [dict(r) for r in result]

    def get_etymology_claims(self, word: str) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[:HAS_ETYMOLOGY_CLAIM]->(c:EtymologyClaim)
                OPTIONAL MATCH (c)-[:CLAIMS_SOURCE_FORM]->(r:Root)
                OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(s:Source)
                RETURN
                    c.id                AS id,
                    c.relation_type     AS relation_type,
                    c.source_form       AS source_form,
                    c.original_form     AS original_form,
                    c.source_language   AS source_language,
                    c.confidence        AS confidence,
                    c.note              AS note,
                    c.is_reconstructed  AS is_reconstructed,
                    c.intermediate_path AS intermediate_path,
                    r.meaning           AS source_meaning,
                    s.slug              AS source_slug,
                    s.short_name        AS source_short_name,
                    s.authority_tier    AS source_tier
                ORDER BY s.authority_tier ASC, c.confidence DESC, c.source_language, c.source_form
                """,
                word=word.lower(),
            )
            return [dict(r) for r in result]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('word_search', $query)
                YIELD node, score
                RETURN
                    node.name       AS name,
                    node.language   AS language,
                    node.definition AS definition,
                    score
                ORDER BY score DESC
                LIMIT $limit
                """,
                query=query,
                limit=limit,
            )
            return [dict(r) for r in result]

    # ── Era queries ───────────────────────────────────────────────────────────

    def get_word_era_meanings(self, word: str) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[h:HAD_MEANING_IN]->(e:Era)
                OPTIONAL MATCH (s:Source {slug: h.source})
                RETURN
                    e.name              AS era_name,
                    e.start_year        AS era_start,
                    e.end_year          AS era_end,
                    e.summary           AS era_summary,
                    h.meaning           AS meaning,
                    h.usage_example     AS usage_example,
                    h.register          AS register,
                    h.source            AS source_slug,
                    s.short_name        AS source_short_name,
                    s.authority_tier    AS source_tier
                ORDER BY e.start_year ASC
                """,
                word=word.lower(),
            )
            return [dict(r) for r in result]

    def get_era_timeline(self, word: str) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Era)
                OPTIONAL MATCH (w:Word {name: $word})-[h:HAD_MEANING_IN]->(e)
                RETURN
                    e.name          AS era_name,
                    e.start_year    AS era_start,
                    e.end_year      AS era_end,
                    h.meaning       AS meaning,
                    h.usage_example AS usage_example
                ORDER BY e.start_year ASC
                """,
                word=word.lower(),
            )
            return [dict(r) for r in result]

    def get_word_in_era(self, word: str, era_name: str) -> dict | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[h:HAD_MEANING_IN]->(e:Era {name: $era})
                OPTIONAL MATCH (w)-[:DESCENDED_FROM]->(r:Root)
                OPTIONAL MATCH (s:Source {slug: h.source})
                RETURN
                    w.name              AS name,
                    w.definition        AS modern_definition,
                    e.name              AS era_name,
                    e.start_year        AS era_start,
                    e.end_year          AS era_end,
                    e.summary           AS era_summary,
                    h.meaning           AS historical_meaning,
                    h.usage_example     AS usage_example,
                    r.name              AS root,
                    r.meaning           AS root_meaning,
                    s.short_name        AS source_short_name
                """,
                word=word.lower(),
                era=era_name,
            )
            record = result.single()
            return dict(record) if record else None

    def get_era_by_year(self, year: int) -> dict | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Era)
                WHERE e.start_year <= $year <= e.end_year
                RETURN
                    e.name          AS name,
                    e.start_year    AS start_year,
                    e.end_year      AS end_year,
                    e.summary       AS summary
                ORDER BY e.start_year DESC
                LIMIT 1
                """,
                year=year,
            )
            record = result.single()
            return dict(record) if record else None

    def get_words_by_era(self, era_name: str, limit: int = 20) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word)-[h:HAD_MEANING_IN]->(e:Era {name: $era})
                RETURN
                    w.name          AS name,
                    w.definition    AS modern_definition,
                    h.meaning       AS historical_meaning
                ORDER BY w.name
                LIMIT $limit
                """,
                era=era_name,
                limit=limit,
            )
            return [dict(r) for r in result]

    # ── Source queries ────────────────────────────────────────────────────────

    def get_all_sources(self) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Source)
                RETURN
                    s.slug           AS slug,
                    s.short_name     AS short_name,
                    s.full_name      AS full_name,
                    s.author         AS author,
                    s.year           AS year,
                    s.category       AS category,
                    s.authority_tier AS authority_tier,
                    s.description    AS description
                ORDER BY s.authority_tier ASC, s.year ASC
                """
            )
            return [dict(r) for r in result]

    def get_source(self, slug: str) -> dict | None:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Source {slug: $slug})
                RETURN
                    s.slug           AS slug,
                    s.short_name     AS short_name,
                    s.full_name      AS full_name,
                    s.author         AS author,
                    s.year           AS year,
                    s.publisher      AS publisher,
                    s.category       AS category,
                    s.authority_tier AS authority_tier,
                    s.description    AS description
                """,
                slug=slug,
            )
            record = result.single()
            return dict(record) if record else None

    def get_word_sources(self, word: str) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word {name: $word})-[a:ATTESTED_IN]->(s:Source)
                RETURN
                    s.slug           AS slug,
                    s.short_name     AS short_name,
                    s.full_name      AS full_name,
                    s.author         AS author,
                    s.year           AS year,
                    s.authority_tier AS authority_tier,
                    s.category       AS category,
                    a.context        AS context
                ORDER BY s.authority_tier ASC, s.year ASC
                """,
                word=word.lower(),
            )
            return [dict(r) for r in result]

    def get_words_by_source(self, slug: str, limit: int = 20) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (w:Word)-[:ATTESTED_IN]->(s:Source {slug: $slug})
                RETURN
                    w.name       AS name,
                    w.definition AS definition
                ORDER BY w.name
                LIMIT $limit
                """,
                slug=slug,
                limit=limit,
            )
            return [dict(r) for r in result]
