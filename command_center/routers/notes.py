"""Notes: Tyler's own append-only thoughts (PRD §2, decision #20).

Text only -- no blob storage. Append and list; there is no edit or delete
(append-only). The author is the authenticated principal, recorded server-side
so it cannot be spoofed by the client.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from command_center.db import get_conn
from command_center.schemas import NoteCreate, NoteOut
from command_center.security import Identity, current_user
from emctl.db import Conn
from emctl.repo import notes

router = APIRouter(prefix="/api", tags=["notes"])


@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    _user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> list[NoteOut]:
    return [NoteOut.model_validate(r) for r in notes.list_(conn)]


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(
    payload: NoteCreate,
    user: Identity = Depends(current_user),
    conn: Conn = Depends(get_conn),
) -> NoteOut:
    row = notes.add(
        conn, body=payload.body, author=user.email, context=payload.context
    )
    return NoteOut.model_validate(row)
