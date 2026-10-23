"""
An interactive shell on the cluster, over a WebSocket, as the signed-in user.

The browser opens /v1/ssh/terminal and sends {"token", "cols", "rows"} as its first
message. The token never goes in the URL, so it stays out of access logs. The API signs
in to the cluster with the user's stored key, opens a login shell with a terminal, and
relays both ways:

  browser -> API  text frames  {"type": "input", "data": "..."}
                               {"type": "resize", "cols": N, "rows": N}
  API -> browser  binary frames, the terminal's own bytes
                  text frames  {"type": "error", "message": "..."} or {"type": "exit"}

A shell nobody has typed in for an hour is closed.
"""

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from bioinformatics_tools.api.auth import decrypt_private_key, get_current_user
from bioinformatics_tools.utilities.ssh_connection import make_user_connection

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ssh", tags=["terminal"])

IDLE_SECONDS = 60 * 60
HELLO_SECONDS = 20


def _size(msg: dict) -> tuple[int, int]:
    """Returns (cols, rows), within sane bounds."""
    def num(key: str, default: int, lo: int, hi: int) -> int:
        try:
            return max(lo, min(hi, int(msg.get(key, default))))
        except (TypeError, ValueError):
            return default
    return num("cols", 120, 20, 500), num("rows", 32, 5, 200)


async def _say(ws: WebSocket, kind: str, message: str = "") -> None:
    try:
        await ws.send_text(json.dumps({"type": kind, **({"message": message} if message else {})}))
    except Exception:
        pass


@router.websocket("/terminal")
async def terminal(ws: WebSocket):
    """Relays a login shell on the cluster to the browser until either side closes."""
    await ws.accept()
    loop = asyncio.get_running_loop()

    # The first message signs in.
    try:
        hello = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=HELLO_SECONDS))
        user = get_current_user(str(hello.get("token") or ""))
    except (asyncio.TimeoutError, ValueError, TypeError, HTTPException, WebSocketDisconnect):
        await _say(ws, "error", "Sign in again to open a terminal.")
        await ws.close(code=4401)
        return
    cols, rows = _size(hello)

    try:
        conn = make_user_connection(user["cluster_host"], user["cluster_username"],
                                    decrypt_private_key(user["private_key_encrypted"]))
        client = await loop.run_in_executor(None, lambda: conn.connect(pooled=False))
        chan = await loop.run_in_executor(
            None, lambda: client.invoke_shell(term="xterm-256color", width=cols, height=rows))
    except Exception as exc:
        LOGGER.warning("Terminal for %s could not open a shell: %s", user["username"], exc)
        await _say(ws, "error", f"Could not open a shell on {user['cluster_host']}: {exc}")
        await ws.close(code=1011)
        return
    LOGGER.info("Terminal opened for %s on %s", user["username"], user["cluster_host"])

    # The shell's output, read on a thread of its own (paramiko blocks) and handed over.
    out: asyncio.Queue[bytes | None] = asyncio.Queue()

    def read_shell() -> None:
        try:
            while True:
                data = chan.recv(32768)
                if not data:
                    break
                loop.call_soon_threadsafe(out.put_nowait, data)
        except Exception:
            pass
        finally:
            loop.call_soon_threadsafe(out.put_nowait, None)

    threading.Thread(target=read_shell, name=f"terminal-{user['username']}", daemon=True).start()

    async def to_browser() -> None:
        while True:
            data = await out.get()
            if data is None:
                return
            await ws.send_bytes(data)

    async def to_shell() -> None:
        while True:
            msg = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=IDLE_SECONDS))
            kind = msg.get("type")
            if kind == "input":
                data = str(msg.get("data", "")).encode()
                if data:
                    await loop.run_in_executor(None, chan.sendall, data)
            elif kind == "resize":
                c, r = _size(msg)
                chan.resize_pty(width=c, height=r)

    tasks = {asyncio.create_task(to_browser()), asyncio.create_task(to_shell())}
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if isinstance(exc, asyncio.TimeoutError):
                await _say(ws, "error", "Closed after an hour without typing.")
            elif exc and not isinstance(exc, WebSocketDisconnect):
                LOGGER.warning("Terminal for %s ended on an error: %s", user["username"], exc)
    finally:
        try:
            chan.close()
            client.close()
        except Exception:
            pass
        await _say(ws, "exit")
        try:
            await ws.close()
        except Exception:
            pass
        LOGGER.info("Terminal closed for %s", user["username"])
