"""Chat with the genome, for the website (api/services/genome_chat.py).

  GET    /v1/chat?genome=g   -> {settings, keys (last four and expiry only), expired, keyDays, providers, builtin, history}
  PUT    /v1/chat            {provider?, model?, baseUrl?, budget?, answerTokens?, consented?, key?, keyFor?, keyDays?}
  POST   /v1/chat            {genome, question, context?, remote: {roots, table}} -> {answer}
  DELETE /v1/chat?genome=g   -> forgets that genome's conversation

Everything is read and written in the user's own cluster account over their SSH connection.
"""

from fastapi import APIRouter, Depends, HTTPException

from bioinformatics_tools.api.auth import get_current_user
from bioinformatics_tools.api.routers.ssh import _build_connection
from bioinformatics_tools.api.services import genome_chat

router = APIRouter(prefix="/v1/chat", tags=["chat"])


def _call(fn, *args):
    try:
        return fn(*args)
    except genome_chat.ChatError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))


@router.get("")
def get_chat(genome: str = "", current_user: dict = Depends(get_current_user)):
    conn = _build_connection(current_user)
    home = current_user["home_dir"]
    info = _call(genome_chat.public_settings, conn, home)
    return {**info, "history": _call(genome_chat.read_history, conn, home, genome) if genome else []}


@router.put("")
def put_chat(body: dict, current_user: dict = Depends(get_current_user)):
    return _call(genome_chat.update_settings, _build_connection(current_user), current_user["home_dir"], body or {})


@router.post("")
def ask_chat(body: dict, current_user: dict = Depends(get_current_user)):
    body = body or {}
    answer = _call(genome_chat.ask, _build_connection(current_user), current_user["home_dir"],
                   body.get("genome"), body.get("question"), body.get("context"), body.get("remote"))
    return {"answer": answer}


@router.delete("")
def forget_chat(genome: str, current_user: dict = Depends(get_current_user)):
    _call(genome_chat.clear_history, _build_connection(current_user), current_user["home_dir"], genome)
    return {"ok": True}
