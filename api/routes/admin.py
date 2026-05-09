from fastapi import APIRouter, Header

from api.schemas import IngestPayload
from api.security import require_admin_token
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
