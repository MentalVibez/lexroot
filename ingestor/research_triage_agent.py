"""
Ethical research triage for PensiveApe resource recommendations.

This is intentionally not a bulk scraper. It classifies resource metadata and,
optionally, checks robots.txt for public URLs. It does not fetch page bodies,
download books, bypass paywalls, store transcripts, or publish claims.

Usage:
  python -m ingestor.research_triage_agent
  python -m ingestor.research_triage_agent --format markdown
  python -m ingestor.research_triage_agent --check-robots
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "Words" / "sources" / "research_resources.csv"
DEFAULT_OUTPUT = ROOT / "Words" / "build" / "research_triage_report.json"

USER_AGENT = "PensiveApeResearchTriage/1.0 (+https://pensiveape.com)"

TOPIC_TAGS = {
    "Old English",
    "Middle English",
    "Indo-European",
    "Latin/Greek",
    "alphabet",
    "word history",
    "writing",
    "public linguistics",
}
AUDIENCES = {"student", "writer", "teacher", "scholar", "curious reader"}
ACCESS_TYPES = {"public", "library", "paid", "subscription", "unknown"}
LICENSE_STATUSES = {
    "link only",
    "metadata only",
    "quotable short excerpts",
    "public domain",
    "open license",
    "needs permission",
}
SITE_USES = {"resource card", "citation lead", "editor research only", "not suitable"}


@dataclass(frozen=True)
class ResourceInput:
    title: str
    creator: str = ""
    type: str = "reference"
    publisher: str = ""
    year: str = ""
    url: str = ""


@dataclass
class TriagedResource:
    title: str
    author_host_publisher: str
    type: str
    topic_tags: list[str]
    audience_fit: list[str]
    access_type: str
    license_use_status: str
    recommended_site_use: str
    safe_use_note: str
    url: str = ""
    year: str = ""
    publisher: str = ""
    robots_allowed: bool | None = None
    review_status: str = "needs human review"
    warnings: list[str] = field(default_factory=list)


def load_resources(path: Path = DEFAULT_INPUT) -> list[ResourceInput]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [
            ResourceInput(
                title=(row.get("title") or "").strip(),
                creator=(row.get("creator") or "").strip(),
                type=(row.get("type") or "reference").strip() or "reference",
                publisher=(row.get("publisher") or "").strip(),
                year=(row.get("year") or "").strip(),
                url=(row.get("url") or "").strip(),
            )
            for row in reader
            if (row.get("title") or "").strip()
        ]


def triage_resource(resource: ResourceInput, robots_allowed: bool | None = None) -> TriagedResource:
    title = resource.title
    kind = normalize_type(resource.type)
    topics = classify_topics(title, kind)
    audiences = classify_audience(title, kind, topics)
    access_type = classify_access(resource, kind)
    license_status = classify_license(resource, kind)
    site_use = classify_site_use(kind, topics, access_type, license_status)
    warnings = build_warnings(resource, access_type, license_status, robots_allowed)

    return TriagedResource(
        title=title,
        author_host_publisher=resource.creator or resource.publisher or "Unknown",
        type=kind,
        topic_tags=topics,
        audience_fit=audiences,
        access_type=access_type,
        license_use_status=license_status,
        recommended_site_use=site_use,
        safe_use_note=safe_use_note(kind, license_status, site_use),
        url=resource.url,
        year=resource.year,
        publisher=resource.publisher,
        robots_allowed=robots_allowed,
        warnings=warnings,
    )


def normalize_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if normalized in {"book", "podcast", "website", "dictionary", "corpus", "reference"}:
        return normalized
    return "reference"


def classify_topics(title: str, kind: str) -> list[str]:
    text = title.casefold()
    topics: set[str] = set()
    if any(token in text for token in ["anglo-saxon", "old english"]):
        topics.add("Old English")
    if "middle english" in text:
        topics.add("Middle English")
    if any(token in text for token in ["indo-european", "horse the wheel", "roots"]):
        topics.add("Indo-European")
    if any(token in text for token in ["latin", "greek", "classical"]):
        topics.add("Latin/Greek")
    if any(token in text for token in ["alphabet", "alpha beta", "roman alphabet"]):
        topics.add("alphabet")
    if any(token in text for token in ["word", "etymologicon", "etymonline", "lexicon"]):
        topics.add("word history")
    if any(token in text for token in ["writing", "grammar girl", "works"]):
        topics.add("writing")
    if kind in {"podcast", "website"} or any(
        token in text for token in ["adventure", "story", "mother tongue", "blooming", "unexpected"]
    ):
        topics.add("public linguistics")
    if not topics:
        topics.add("word history")
    return sorted(topics)


def classify_audience(title: str, kind: str, topics: list[str]) -> list[str]:
    text = title.casefold()
    audience: set[str] = {"curious reader"}
    if kind in {"podcast", "website"} or "public linguistics" in topics:
        audience.add("student")
    if any(topic in topics for topic in ["writing", "word history", "Latin/Greek"]):
        audience.add("writer")
    if any(topic in topics for topic in ["Old English", "Middle English", "Indo-European", "Latin/Greek"]):
        audience.update({"teacher", "scholar"})
    if any(token in text for token in ["introduction", "book of middle english", "anthology"]):
        audience.update({"student", "teacher"})
    return sorted(audience)


def classify_access(resource: ResourceInput, kind: str) -> str:
    if resource.url and kind in {"podcast", "website"}:
        return "public"
    if resource.url and kind in {"dictionary", "corpus", "reference"}:
        return "public"
    if kind == "book":
        return "library"
    return "unknown"


def classify_license(resource: ResourceInput, kind: str) -> str:
    title = resource.title.casefold()
    if kind == "book":
        return "metadata only"
    if "endless knot" in title:
        return "link only"
    if kind in {"podcast", "website"}:
        return "link only"
    if kind in {"dictionary", "corpus", "reference"}:
        return "metadata only"
    return "link only"


def classify_site_use(kind: str, topics: list[str], access_type: str, license_status: str) -> str:
    if license_status == "needs permission":
        return "not suitable"
    if kind in {"podcast", "website"}:
        return "resource card"
    if kind == "book" and "public linguistics" in topics:
        return "resource card"
    if kind in {"dictionary", "corpus", "reference"}:
        return "citation lead"
    if access_type in {"library", "paid", "subscription"}:
        return "editor research only"
    return "resource card"


def safe_use_note(kind: str, license_status: str, site_use: str) -> str:
    if kind == "book":
        return "Use original description and bibliographic metadata only; verify claims against citation-grade sources."
    if kind == "podcast":
        return "Link to the show and describe its focus; do not ingest transcripts or episode text without permission."
    if site_use == "citation lead":
        return "Use as a lead for human verification; cite exact dictionary/corpus evidence before publishing claims."
    if license_status == "link only":
        return "Link and summarize in original language; do not copy site body text."
    return "Human review required before publishing any derived claim."


def build_warnings(
    resource: ResourceInput,
    access_type: str,
    license_status: str,
    robots_allowed: bool | None,
) -> list[str]:
    warnings: list[str] = []
    if not resource.url:
        warnings.append("No public URL supplied; use library/catalog metadata only.")
    if access_type in {"library", "paid", "subscription"}:
        warnings.append("Do not bypass purchase, library, login, or subscription access.")
    if license_status in {"metadata only", "link only"}:
        warnings.append("Do not store copyrighted body text or transcripts.")
    if robots_allowed is False:
        warnings.append("robots.txt disallows automated fetch; keep this as manual/link-only research.")
    return warnings


async def check_robots_allowed(url: str, client: httpx.AsyncClient) -> bool | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = await client.get(
            robots_url,
            headers={"User-Agent": USER_AGENT},
            timeout=8.0,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


async def triage_resources(
    resources: list[ResourceInput],
    check_robots: bool = False,
) -> list[TriagedResource]:
    if not check_robots:
        return [triage_resource(resource) for resource in resources]

    async with httpx.AsyncClient() as client:
        triaged: list[TriagedResource] = []
        for resource in resources:
            robots_allowed = await check_robots_allowed(resource.url, client)
            triaged.append(triage_resource(resource, robots_allowed=robots_allowed))
        return triaged


def report_payload(records: list[TriagedResource]) -> dict[str, Any]:
    return {
        "guardrails": [
            "No copyrighted body text, book scans, or podcast transcripts are stored.",
            "Public URLs are used for metadata and links only unless a license says otherwise.",
            "Human review is required before a resource supports a published word claim.",
            "Citation-grade claims should prefer historical dictionaries, corpora, or primary texts.",
        ],
        "record_count": len(records),
        "records": [asdict(record) for record in records],
    }


def write_json(records: list[TriagedResource], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_payload(records), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_markdown(records: list[TriagedResource]) -> str:
    lines = [
        "# Research Triage Report",
        "",
        "Guardrail: this report stores metadata and recommendations only, not copyrighted body text.",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"## {record.title}",
                f"- Type: {record.type}",
                f"- Topics: {', '.join(record.topic_tags)}",
                f"- Audience: {', '.join(record.audience_fit)}",
                f"- Access: {record.access_type}",
                f"- License/use: {record.license_use_status}",
                f"- Recommended use: {record.recommended_site_use}",
                f"- Safe-use note: {record.safe_use_note}",
            ]
        )
        if record.url:
            lines.append(f"- URL: {record.url}")
        if record.warnings:
            lines.append(f"- Warnings: {'; '.join(record.warnings)}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify learning/citation resources without scraping bodies.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV resource list.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report output path.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--check-robots", action="store_true", help="Fetch only robots.txt for supplied URLs.")
    args = parser.parse_args()

    import asyncio

    resources = load_resources(args.input)
    records = asyncio.run(triage_resources(resources, check_robots=args.check_robots))
    if args.format == "markdown":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_markdown(records), encoding="utf-8")
    else:
        write_json(records, args.output)
    print(f"[research-triage] wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
