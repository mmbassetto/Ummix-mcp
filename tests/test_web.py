"""Regras HTTP/UI sem depender do LLM; o ensaio real é separado e registrado."""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from starlette.testclient import TestClient

from ummix_mcp.demo import DEMO_BRIEFING, TOOLS, unpack
from ummix_mcp.models import BANNER
from ummix_mcp.web import create_app
from ummix_mcp.web_agent import ChatSession, CodexAgent, tool_payload
from ummix_mcp.web_gateway import ApprovalPolicy


HEADERS = {"X-Ummix-Local": "1", "Origin": "http://localhost"}


class IdleAgent:
    async def health(self, force=False):
        return {"ready": False, "message": "Fixture de teste, sem LLM."}

    async def run(self, session, permit=None):
        session.busy = False
        await session.emit("done", snapshot=session.snapshot())


def test_ui_static_and_session_reload(tmp_path):
    app = create_app(tmp_path / "web.sqlite3", agent=IdleAgent())
    with TestClient(app, base_url="http://localhost") as client:
        page = client.get("/")
        assert page.status_code == 200
        assert BANNER in page.text
        assert "Seu estrategista de mídia" in page.text
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/../storage.py").status_code == 404
        assert client.get("/api/health").json()["ready"] is False
        assert client.get("/api/health?refresh=1").status_code == 403
        assert client.get("/api/health?refresh=1", headers=HEADERS).status_code == 200
        session = client.post("/api/sessions", json={}, headers=HEADERS).json()
        sid = session["id"]
        response = client.post(f"/api/sessions/{sid}/messages", json={"message": "<script>alert(1)</script>"}, headers=HEADERS)
        assert response.status_code == 202
        state = client.get(f"/api/sessions/{sid}").json()
        assert state["messages"][0]["content"] == "<script>alert(1)</script>"
        assert state["events"] and state["cursor"] >= 1
        assert client.get(f"/api/sessions/{sid}/export").json()["dados_simulados"] is True


def test_http_origin_and_input_guards(tmp_path):
    with TestClient(create_app(tmp_path / "web.sqlite3", agent=IdleAgent()), base_url="http://localhost") as client:
        assert client.post("/api/sessions", json={}).status_code == 403
        assert client.post("/api/sessions", json={}, headers={**HEADERS, "Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/sessions", json={}, headers={**HEADERS, "Host": "evil.example"}).status_code == 400
        sid = client.post("/api/sessions", json={}, headers=HEADERS).json()["id"]
        for text in ("", "a" * 4001, 42):
            assert client.post(f"/api/sessions/{sid}/messages", json={"message": text}, headers=HEADERS).status_code == 400
        assert client.post(f"/api/sessions/{sid}/approve", json={"confirmacao_explicita": "true"}, headers=HEADERS).status_code == 400
        assert client.post(f"/api/sessions/{sid}/approve", json={"confirmacao_explicita": True, "simulation_id": "inexistente"}, headers=HEADERS).status_code == 409


def test_web_approval_is_exact_and_requires_ui_confirmation(tmp_path, service, briefing):
    app = create_app(service.storage.path, agent=IdleAgent())
    with TestClient(app, base_url="http://localhost") as client:
        sid = client.post("/api/sessions", json={}, headers=HEADERS).json()["id"]
        session = app.state.sessions[sid]
        session.simulation = service.simulate(briefing)
        session.simulation_ids.add(session.simulation["simulation_id"])
        data = {"simulation_id": session.simulation["simulation_id"], "alternativa_id": session.simulation["alternativas"][0]["alternativa_id"], "confirmacao_explicita": True}
        assert client.post(f"/api/sessions/{sid}/approve", json={**data, "alternativa_id": "errada"}, headers=HEADERS).status_code == 400
        assert client.post(f"/api/sessions/{sid}/approve", json={**data, "simulation_id": "outra"}, headers=HEADERS).status_code == 409
        assert client.post(f"/api/sessions/{sid}/approve", json={**data, "confirmacao_explicita": False}, headers=HEADERS).status_code == 400
        assert client.post(f"/api/sessions/{sid}/approve", json=data, headers=HEADERS).status_code == 202
        with service.storage.connection() as conn:
            # A rota só autoriza o agente; nunca cria aprovação/plano por fora do MCP.
            assert conn.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_gateway_policy_cannot_be_bypassed_by_chat():
    policy = ApprovalPolicy({"sim-1"})
    args = {"simulation_id": "sim-1", "alternativa_id": "eficiencia", "confirmacao_explicita": True}
    assert policy.check("registrar_aprovacao", args)
    policy.permit = {"simulation_id": "sim-1", "alternativa_id": "eficiencia", "chave_idempotente": "chave-estavel"}
    assert policy.check("registrar_aprovacao", args) is None
    assert policy.check("registrar_aprovacao", {**args, "alternativa_id": "diversificacao"})
    assert policy.check("registrar_aprovacao", {**args, "simulation_id": "sim-2"})
    assert policy.check("registrar_aprovacao", {**args, "confirmacao_explicita": 1})
    create = {**args, "approval_id": "approval-1", "chave_idempotente": "chave-estavel"}
    assert policy.check("criar_plano", create)
    policy.observe("registrar_aprovacao", {"ok": True, "dados": {"approval_id": "approval-1"}})
    assert policy.check("criar_plano", create) is None
    assert policy.check("criar_plano", {**create, "chave_idempotente": "outra"})
    assert policy.check("simular_plano", {})
    assert policy.check("consultar_plano", {"plan_id": "outro-plano"})
    policy.observe("criar_plano", {"ok": True, "dados": {"plan_id": "plano-1"}})
    assert policy.check("consultar_plano", {"plan_id": "plano-1"}) is None
    assert policy.check("comprar_campanha", {})


def test_new_simulation_gets_new_key_and_tampering_is_reported(service, briefing):
    class CaptureAgent(IdleAgent):
        def __init__(self):
            self.permits = []

        async def run(self, session, permit=None):
            self.permits.append(permit)
            await super().run(session, permit)

    agent = CaptureAgent()
    app = create_app(service.storage.path, agent=agent)
    with TestClient(app, base_url="http://localhost") as client:
        sid = client.post("/api/sessions", json={}, headers=HEADERS).json()["id"]
        session = app.state.sessions[sid]
        for _ in range(2):
            session.simulation = service.simulate(briefing)
            session.simulation_ids.add(session.simulation["simulation_id"])
            data = {"simulation_id": session.simulation["simulation_id"], "alternativa_id": session.simulation["alternativas"][0]["alternativa_id"], "confirmacao_explicita": True}
            assert client.post(f"/api/sessions/{sid}/approve", json=data, headers=HEADERS).status_code == 202
            client.get(f"/api/sessions/{sid}")
        assert len(agent.permits) == 2
        assert agent.permits[0]["chave_idempotente"] != agent.permits[1]["chave_idempotente"]
        with service.storage.connection() as conn:
            conn.execute("UPDATE simulations SET sha256 = ? WHERE id = ?", ("alterado", data["simulation_id"]))
        invalid = client.post(f"/api/sessions/{sid}/approve", json=data, headers=HEADERS)
        assert invalid.status_code == 409
        assert invalid.json()["code"] == "SIMULACAO_ALTERADA"


def test_agent_reads_real_structured_events_without_inventing_state(tmp_path):
    async def scenario():
        agent = CodexAgent(tmp_path / "db.sqlite3", tmp_path / "runtime", command="codex")
        session = ChatSession()
        item = {"id": "call-1", "type": "mcp_tool_call", "server": "ummix", "tool": "simular_plano", "arguments": {},
                "result": {"structured_content": {"ok": True, "dados": {"simulation_id": "sim-1", "alternativas": []}}}}
        await agent.handle_event(session, {"type": "item.started", "item": {**item, "result": None}}, "turn-1")
        assert session.simulation is None
        await agent.handle_event(session, {"type": "item.completed", "item": item}, "turn-1")
        assert session.simulation["simulation_id"] == "sim-1"
        assert len(session.events) == 3
        failed = {**item, "tool": "criar_plano", "result": {"structured_content": {"ok": False, "erro": {"codigo": "APROVACAO_AUSENTE"}}}}
        await agent.handle_event(session, {"type": "item.completed", "item": failed}, "turn-1")
        assert session.plan is None
        assert session.events[-1]["status"] == "error"
        await agent.handle_event(session, {"type": "item.completed", "item": {**failed, "result": None}}, "turn-1")
        assert session.events[-1]["status"] == "error"
        assert "--ephemeral" in agent.command_args(session, None)
        assert "shell_tool" in agent.command_args(session, None)
        assert "mcp_servers.ummix.required=true" in agent.command_args(session, None)
        assert "mcp_optional_startup_grace_ms=0" in agent.command_args(session, None)
    asyncio.run(scenario())


def test_missing_client_produces_failure_not_fake_reply(tmp_path):
    async def scenario():
        agent = CodexAgent(tmp_path / "db.sqlite3", tmp_path / "runtime", command=str(tmp_path / "missing-codex.exe"))
        session = ChatSession(busy=True)
        await agent.run(session)
        assert not session.busy
        assert session.last_error
        assert not session.messages
        assert session.simulation is None and session.plan is None
        assert any(e["type"] == "failure" for e in session.events)
    asyncio.run(scenario())


@asynccontextmanager
async def gateway(db, context):
    params = StdioServerParameters(command=sys.executable, args=["-m", "ummix_mcp.web_gateway"], env={
        **os.environ, "PYTHONUTF8": "1", "UMMIX_DB_PATH": str(db), "UMMIX_WEB_CONTEXT": json.dumps(context),
    })
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def test_gateway_forwards_real_mcp_and_blocks_premature_approval(tmp_path):
    async def scenario():
        db = tmp_path / "gateway.sqlite3"
        async with gateway(db, {"read_only": True}) as session:
            assert unpack(await session.call_tool("listar_mercados", {}))["ok"] is True
            blocked = unpack(await session.call_tool("simular_plano", {"briefing": DEMO_BRIEFING}))
            assert blocked["ok"] is False
        async with gateway(db, {}) as session:
            assert {t.name for t in (await session.list_tools()).tools} == TOOLS
            simulated = unpack(await session.call_tool("simular_plano", {"briefing": DEMO_BRIEFING}))["dados"]
            sid = simulated["simulation_id"]
            aid = simulated["alternativas"][0]["alternativa_id"]
            rejected = unpack(await session.call_tool("registrar_aprovacao", {"simulation_id": sid, "alternativa_id": aid, "confirmacao_explicita": True}))
            assert rejected["erro"]["codigo"] == "APROVACAO_UI_OBRIGATORIA"
        permit = {"simulation_id": sid, "alternativa_id": aid, "chave_idempotente": "chave-teste-web"}
        async with gateway(db, {"simulation_ids": [sid], "permit": permit}) as session:
            approval = unpack(await session.call_tool("registrar_aprovacao", {"simulation_id": sid, "alternativa_id": aid, "confirmacao_explicita": True}))["dados"]
            plan = unpack(await session.call_tool("criar_plano", {**permit, "approval_id": approval["approval_id"]}))["dados"]
            recovered = unpack(await session.call_tool("consultar_plano", {"plan_id": plan["plan_id"]}))["dados"]
            assert recovered["status"] == "RASCUNHO_APROVADO"
            assert len(recovered["auditoria"]) == 3
    asyncio.run(scenario())
