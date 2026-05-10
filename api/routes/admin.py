from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_pg_session
from api.schemas import IngestPayload
from api.security import require_admin_token
from db import crud
from ingestor.graph_loader import LexiconIngestor, WordEntry


router = APIRouter(tags=["admin"])


@router.post("/ingest", status_code=201)
def ingest_word(payload: IngestPayload, authorization: str | None = Header(default=None)):
    require_admin_token(authorization)
    ingestor = LexiconIngestor()
    ingestor.ensure_indexes()
    entry = WordEntry(**payload.model_dump())
    ingestor.ingest(entry)
    ingestor.close()
    return {"message": f"'{payload.name}' ingested successfully"}


# ---------------------------------------------------------------------------
# Contribution review
# ---------------------------------------------------------------------------

class ReviewAction(BaseModel):
    action: str  # "approve" | "reject"
    reviewer_notes: str | None = None


@router.get("/admin/review/pending")
async def list_pending_contributions(
    word: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """List all senses pending review. Admin only."""
    require_admin_token(authorization)
    senses = await crud.list_senses_by_review_status(
        session, review_status="pending", word=word, offset=offset, limit=limit
    )
    return {
        "count": len(senses),
        "senses": [
            {
                "sense_id": s.sense_id,
                "word": s.word,
                "definition": s.definition,
                "era_name": s.era_name,
                "evidence_grade": s.evidence_grade,
                "submitted_by": s.submitted_by,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            }
            for s in senses
        ],
    }


@router.patch("/admin/review/sense/{sense_id}")
async def review_sense(
    sense_id: str,
    payload: ReviewAction,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_pg_session),
):
    """Approve or reject a contributed sense. Admin only."""
    require_admin_token(authorization)
    if payload.action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'approve' or 'reject'")

    new_status = "approved" if payload.action == "approve" else "rejected"
    sense = await crud.update_sense_review_status(
        session, sense_id=sense_id, review_status=new_status, reviewer_notes=payload.reviewer_notes
    )
    if sense is None:
        raise HTTPException(status_code=404, detail=f"Sense '{sense_id}' not found.")

    return {"sense_id": sense_id, "review_status": new_status, "reviewer_notes": payload.reviewer_notes}
