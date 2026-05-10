"""
Abstract base class for all Living Lexicon data importers.

Subclasses implement load() and ingest(); get run_cli() for free.

Usage — creating a new importer:

    from pathlib import Path
    from ingestor.base import BaseImporter, ImportResult
    from ingestor.utils import clean_str, WORD_PATTERN

    class MyImporter(BaseImporter):
        default_path = Path("Words/sources/my_data.csv")
        source_name = "my-source"
        cli_description = "Import My Source data into the lexicon."

        def load(self, path: Path) -> list:
            ...  # parse CSV/JSON, return raw records, no DB calls

        def ingest(self, records: list, *, dry_run: bool = False) -> ImportResult:
            result = ImportResult(dry_run=dry_run)
            for record in records:
                try:
                    if not dry_run:
                        ...  # write to Neo4j or Postgres
                    result.ingested += 1
                except Exception as exc:
                    result.failed += 1
                    result.errors.append(str(exc))
            return result

    if __name__ == "__main__":
        MyImporter().run_cli()
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ingestor.utils import build_arg_parser


@dataclass
class ImportResult:
    """
    Standard result object returned by BaseImporter.ingest().

    Attributes
    ----------
    ingested : int
        Records successfully written (or that would be written in dry_run mode).
    skipped : int
        Records parsed but deliberately skipped (duplicates, below threshold, etc.).
    failed : int
        Records that raised an exception during ingestion.
    errors : list[str]
        Human-readable error descriptions. Keep each under ~200 chars.
    dry_run : bool
        Whether this result came from a dry run (no actual writes).
    """

    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def report(self) -> str:
        """Return a compact multi-line summary suitable for print()."""
        mode = " [dry run]" if self.dry_run else ""
        lines = [
            f"Import result{mode}",
            f"  ingested : {self.ingested:,}",
            f"  skipped  : {self.skipped:,}",
            f"  failed   : {self.failed:,}",
        ]
        if self.errors:
            lines.append("  errors (first 5):")
            for err in self.errors[:5]:
                lines.append(f"    - {err}")
            if len(self.errors) > 5:
                lines.append(f"    ... and {len(self.errors) - 5} more")
        return "\n".join(lines)

    @property
    def ok(self) -> bool:
        """True if no records failed."""
        return self.failed == 0


class BaseImporter(ABC):
    """
    Abstract base class for all Living Lexicon importers.

    Subclasses must implement:
        load(path: Path) -> list[Any]
            Parse the source file and return raw records. Raise FileNotFoundError
            if path does not exist. Do NOT connect to any database here.

        ingest(records: list[Any], *, dry_run: bool = False) -> ImportResult
            Write records to the target store. If dry_run=True, perform all
            validation but make no writes. Return an ImportResult.

    Subclasses may set as class attributes:
        default_path : Path | None
            Sets the --path default in run_cli(). If None, --path is required.
        source_name : str
            Used in log messages. Defaults to the class name.
        cli_description : str
            argparse description string for run_cli().
        extra_cli_args : list[tuple]
            Additional ([arg_names], {kwargs}) pairs for build_arg_parser().
    """

    default_path: Path | None = None
    source_name: str = ""
    cli_description: str = "Import data into the Living Lexicon."
    extra_cli_args: list[tuple] = []

    @abstractmethod
    def load(self, path: Path) -> list[Any]:
        """
        Parse the source file and return a list of raw records.

        Raise FileNotFoundError if path does not exist.
        Do NOT connect to any database here.
        """
        ...

    @abstractmethod
    def ingest(self, records: list[Any], *, dry_run: bool = False) -> ImportResult:
        """
        Write records to the target store, returning a result summary.

        If dry_run=True: validate but make no writes; set ImportResult.dry_run=True.
        """
        ...

    def run_cli(self) -> None:
        """
        Standard CLI entry point. Parses args, calls load() + ingest(), prints report.

        Exit code: 0 on success, 1 if any records failed.
        """
        name = self.source_name or type(self).__name__
        parser = build_arg_parser(
            description=self.cli_description,
            default_path=self.default_path,
            include_limit=True,
            include_dry_run=True,
            extra_args=self.extra_cli_args or [],
        )
        args = parser.parse_args()
        path = Path(args.path)
        limit: int = getattr(args, "limit", 0)
        dry_run: bool = getattr(args, "dry_run", False)

        print(f"[{name}] Loading from {path} ...")
        records = self.load(path)
        print(f"[{name}] Loaded {len(records):,} records.")

        if limit and limit > 0:
            records = records[:limit]
            print(f"[{name}] Limiting to {limit:,} records.")

        result = self.ingest(records, dry_run=dry_run)
        print(result.report())

        if not result.ok:
            sys.exit(1)
