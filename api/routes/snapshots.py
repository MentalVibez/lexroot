"""Dataset snapshot endpoints — create and export reproducible corpus versions."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.security import require_admin_token
from db import crud

router = APIRouter(prefix="/pg", tags=["snapshots"])


class SnapshotCreateRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=120, description="Unique citable label, e.g. 'v2026-05-09' or 'thesis-ch3'")
    description: str | None = Field(default=None, max_length=500)


class SnapshotSummary(BaseModel):
    id: int
    tag: str
    description: str | None
    created_at: str
    word_count: int | None
    sense_count: int | None
    attestation_count: int | None
    schema_version: str | None

    model_config = {"from_attributes": True}


@router.post("/snapshots", response_model=SnapshotSummary, status_code=201)
async def create_snapshot(
    payload: SnapshotCreateRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """Create a citable, versioned snapshot of the full corpus. Admin only."""
    require_admin_token(authorization)
    existing = await crud.get_snapshot(session, payload.tag)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Snapshot '{payload.tag}' already exists.")
    snapshot = await crud.create_snapshot(session, tag=payload.tag, description=payload.description)
    return SnapshotSummary(
        id=snapshot.id,
        tag=snapshot.tag,
        description=snapshot.description,
        created_at=snapshot.created_at.isoformat(),
        word_count=snapshot.word_count,
        sense_count=snapshot.sense_count,
        attestation_count=snapshot.attestation_count,
        schema_version=snapshot.schema_version,
    )


@router.get("/snapshots", response_model=list[SnapshotSummary])
async def list_snapshots(session: AsyncSession = Depends(get_pg_session)):
    """List all dataset snapshots (no payload data)."""
    rows = await crud.list_snapshots(session)
    return [
        SnapshotSummary(
            id=r.id,
            tag=r.tag,
            description=r.description,
            created_at=r.created_at.isoformat(),
            word_count=r.word_count,
            sense_count=r.sense_count,
            attestation_count=r.attestation_count,
            schema_version=r.schema_version,
        )
        for r in rows
    ]


@router.get("/snapshots/{tag}")
async def get_snapshot(tag: str, session: AsyncSession = Depends(get_pg_session)):
    """Return a full snapshot record including all data."""
    snap = await crud.get_snapshot(session, tag)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{tag}' not found.")
    return {
        "id": snap.id,
        "tag": snap.tag,
        "description": snap.description,
        "created_at": snap.created_at.isoformat(),
        "word_count": snap.word_count,
        "sense_count": snap.sense_count,
        "attestation_count": snap.attestation_count,
        "schema_version": snap.schema_version,
        "snapshot_data": snap.snapshot_data,
    }


@router.get("/snapshots/{tag}/export")
async def export_snapshot(
    tag: str,
    format: str = Query(default="jsonl", description="jsonl | csv"),
    session: AsyncSession = Depends(get_pg_session),
):
    """Stream a snapshot as JSONL (one JSON object per line) or CSV (senses only)."""
    snap = await crud.get_snapshot(session, tag)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{tag}' not found.")

    data = snap.snapshot_data

    if format == "jsonl":
        def _jsonl_stream():
            for table_name, rows in data.items():
                for row in rows:
                    row["_table"] = table_name
                    yield json.dumps(row, default=str) + "\n"

        return StreamingResponse(
            _jsonl_stream(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{tag}.jsonl"'},
        )

    if format == "csv":
        # Export senses only for CSV — most useful for linguistic analysis
        senses = data.get("senses", [])
        if not senses:
            raise HTTPException(status_code=404, detail="No senses in this snapshot.")

        def _csv_stream():
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(senses[0].keys()))
            writer.writeheader()
            yield buf.getvalue()
            for row in senses:
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=list(senses[0].keys()))
                writer.writerow(row)
                yield buf.getvalue()

        return StreamingResponse(
            _csv_stream(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{tag}-senses.csv"'},
        )

    raise HTTPException(status_code=422, detail="format must be 'jsonl' or 'csv'")
