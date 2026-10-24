"""Interface local: HTTP loopback, chat SSE e agente externo real. Não altera o MCP original."""

import argparse
import asyncio
import json
import os
import sys
import webbrowser
from contextlib import asynccontextmanager
from importlib.resources import files
from datetime import datetime
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .models import BANNER
from .repositories import DomainError
from .storage import Storage
from .web_agent import ChatSession, CodexAgent


def create_app(db: Path | None = None, runtime: Path | None = None, agent=None, codex_path: str | None = None) -> Starlette:
    database = (db or Path(os.environ.get("UMMIX_WEB_DB_PATH", "var/web.sqlite3"))).resolve()
    storage = Storage(database)
    runner = agent or CodexAgent(database, runtime or Path("var/web-agent"), command=codex_path)
    sessions: dict[str, ChatSession] = {}

    def session_for(request: Request) -> ChatSession:
        session = sessions.get(request.path_params["sid"])
        if session is None:
            raise HTTPException(404, "Conversa não encontrada. Inicie uma nova conversa.")
        return session

    async def body(request: Request) -> dict:
        if request.headers.get("x-ummix-local") != "1":
            raise HTTPException(403, "Requisição local inválida.")
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Origem não autorizada.")
        raw = await request.body()
        if len(raw) > 12000:
            raise HTTPException(413, "Mensagem excede o limite permitido.")
        try:
            value = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "JSON inválido.")
        if not isinstance(value, dict):
            raise HTTPException(400, "Use um objeto JSON.")
        return value

    async def index(request):
        return HTMLResponse(files("ummix_mcp").joinpath("static/index.html").read_text(encoding="utf-8"))

    async def asset(request):
        name = request.path_params["name"]
        if name not in {"app.js", "app.css"}:
            raise HTTPException(404)
        return Response(files("ummix_mcp").joinpath("static/" + name).read_text(encoding="utf-8"),
                        media_type="text/javascript" if name.endswith(".js") else "text/css")

    async def health(request):
        if request.query_params.get("refresh") == "1":
            await body(request)
            result = await runner.health(force=True)
        else:
            result = await runner.health()
        return JSONResponse({**result, "aviso": BANNER, "dados_simulados": True,
                             "provider": "Codex CLI • LLM externo", "database": database.name}, headers={"Cache-Control": "no-store"})

    async def new_session(request):
        await body(request)
        if len(sessions) >= 40:
            raise HTTPException(429, "Limite de conversas desta demonstração atingido. Reinicie a aplicação para limpar sessões locais.")
        session = ChatSession()
        sessions[session.id] = session
        return JSONResponse(session.snapshot(), status_code=201)

    async def snapshot(request):
        session = session_for(request)
        return JSONResponse({**session.snapshot(), "events": session.events})

    async def message(request):
        session = session_for(request)
        data = await body(request)
        if session.busy:
            raise HTTPException(409, "Aguarde o turno atual terminar.")
        text = data.get("message")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise HTTPException(400, "Escreva uma mensagem de 1 a 4000 caracteres.")
        if len(session.messages) >= 80:
            raise HTTPException(429, "Inicie uma nova conversa para continuar o ensaio.")
        session.messages.append({"role": "user", "content": text.strip()})
        session.busy = True
        await session.emit("message", message=session.messages[-1])
        session.task = asyncio.create_task(runner.run(session))
        return JSONResponse({"accepted": True}, status_code=202)

    async def approve(request):
        session = session_for(request)
        data = await body(request)
        if session.busy:
            raise HTTPException(409, "Aguarde o agente terminar.")
        if data.get("confirmacao_explicita") is not True:
            raise HTTPException(400, "Confirme explicitamente a alternativa apresentada.")
        simulation = session.simulation
        if not simulation or data.get("simulation_id") != simulation["simulation_id"]:
            raise HTTPException(409, "Simulação desatualizada. Selecione o planejamento atual.")
        if session.plan:
            raise HTTPException(409, "Esse plano já foi registrado. Consulte o ID exibido.")
        alternative = next((a for a in simulation["alternativas"] if a["alternativa_id"] == data.get("alternativa_id")), None)
        if alternative is None:
            raise HTTPException(400, "Alternativa inválida.")
        # Validação de snapshot no armazenamento existente antes de autorizar o agente.
        with storage.connection() as conn:
            storage.read_simulation(conn, simulation["simulation_id"])
        permit = {"simulation_id": simulation["simulation_id"], "alternativa_id": alternative["alternativa_id"],
                  "chave_idempotente": "web-" + simulation["simulation_id"] + "-" + alternative["alternativa_id"]}
        session.messages.append({"role": "user", "content": f"Confirmei no botão a aprovação da simulação {permit['simulation_id']}, alternativa {permit['alternativa_id']}, custo BRL {alternative['custo_total']}. Salve somente o rascunho simulado."})
        session.busy = True
        await session.emit("message", message=session.messages[-1])
        await session.emit("approval_confirmed", simulation_id=permit["simulation_id"], alternativa_id=permit["alternativa_id"])
        session.task = asyncio.create_task(runner.run(session, permit))
        return JSONResponse({"accepted": True}, status_code=202)

    async def events(request):
        session = session_for(request)
        try:
            after = max(0, int(request.headers.get("last-event-id") or request.query_params.get("after", "0")))
        except ValueError:
            raise HTTPException(400, "Cursor inválido.")

        async def stream():
            cursor = after
            while True:
                if await request.is_disconnected():
                    break
                async with session.changed:
                    if len(session.events) <= cursor:
                        try:
                            await asyncio.wait_for(session.changed.wait(), timeout=15)
                        except TimeoutError:
                            pass
                    pending = session.events[cursor:]
                if not pending:
                    yield ": heartbeat\n\n"
                for event in pending:
                    yield f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    cursor = event["id"]
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def evidence(request):
        session = session_for(request)
        result = {**session.snapshot(), "events": session.events, "exportado_em": datetime.now().astimezone().isoformat()}
        if session.plan:
            result["plano_verificado_sqlite"] = storage.get_plan(session.plan["plan_id"])
        return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="ummix-{session.id}.json"'})

    @asynccontextmanager
    async def lifespan(app):
        yield
        tasks = [s.task for s in sessions.values() if s.task and not s.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if hasattr(runner, "close"):
            await runner.close()

    async def error_handler(request, exc):
        return JSONResponse({"error": str(exc.detail), "aviso": BANNER, "dados_simulados": True}, status_code=exc.status_code)

    async def domain_error_handler(request, exc):
        return JSONResponse({"error": str(exc), "code": exc.code, "aviso": BANNER, "dados_simulados": True}, status_code=409)

    app = Starlette(routes=[Route("/", index), Route("/static/{name}", asset), Route("/api/health", health),
                            Route("/api/sessions", new_session, methods=["POST"]),
                            Route("/api/sessions/{sid}", snapshot), Route("/api/sessions/{sid}/messages", message, methods=["POST"]),
                            Route("/api/sessions/{sid}/approve", approve, methods=["POST"]),
                            Route("/api/sessions/{sid}/events", events), Route("/api/sessions/{sid}/export", evidence)],
                    lifespan=lifespan, exception_handlers={HTTPException: error_handler, DomainError: domain_error_handler})
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
    app.state.sessions = sessions
    app.state.runner = runner
    app.state.storage = storage
    return app


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=BANNER + " — chat web com IA real")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Abre o navegador local após iniciar.")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("UMMIX_WEB_DB_PATH", "var/web.sqlite3")))
    parser.add_argument("--codex-path", help="Caminho do executável nativo Codex; também aceita UMMIX_CODEX_PATH.")
    parser.add_argument("--check-agent", action="store_true", help="Verifica executável, autenticação, modelo real e MCP, imprime diagnóstico e encerra.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use porta entre 1024 e 65535.")
    app = create_app(args.db, codex_path=args.codex_path)
    if args.check_agent:
        result = asyncio.run(app.state.runner.health(force=True))
        print(json.dumps({"aviso": BANNER, "dados_simulados": True, **result}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["ready"] else 1)
    if args.open:
        import threading
        threading.Timer(1.5, webbrowser.open, args=(f"http://127.0.0.1:{args.port}",)).start()
    print(BANNER + f"\nUmmix MCP web: http://127.0.0.1:{args.port}\nCtrl+C encerra a aplicação local.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", timeout_graceful_shutdown=3)


if __name__ == "__main__":
    main()
