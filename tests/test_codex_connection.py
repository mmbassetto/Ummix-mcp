"""Regressões de descoberta e disponibilidade; mocks somente nos testes unitários."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from ummix_mcp import codex_runtime, web_agent
from ummix_mcp.codex_runtime import CodexExecutable, discover_codex
from ummix_mcp.demo import TOOLS
from ummix_mcp.web_agent import CodexAgent
from ummix_mcp.web_gateway import ApprovalPolicy


def no_path(monkeypatch, tmp_path):
    monkeypatch.delenv("UMMIX_CODEX_PATH", raising=False)
    monkeypatch.setattr(codex_runtime.shutil, "which", lambda _: None)
    monkeypatch.setattr(codex_runtime.sys, "platform", "win32")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))


def test_desktop_discovery_without_codex_in_path(monkeypatch, tmp_path):
    no_path(monkeypatch, tmp_path)
    exe = tmp_path / "local/OpenAI/Codex/bin/version-a/codex.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"fixture-not-executed")
    result = discover_codex()
    assert result.path == str(exe.resolve())
    assert result.source == "instalação desktop Codex"


def test_home_fallback_when_localappdata_is_redirected(monkeypatch, tmp_path):
    no_path(monkeypatch, tmp_path)
    exe = tmp_path / "home/AppData/Local/OpenAI/Codex/bin/version-b/codex.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"fixture-not-executed")
    assert discover_codex().path == str(exe.resolve())


def test_explicit_executable_precedes_path(monkeypatch, tmp_path):
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"fixture-not-executed")
    monkeypatch.setattr(codex_runtime.shutil, "which", lambda _: "other.exe")
    assert discover_codex(str(exe)).path == str(exe.resolve())
    monkeypatch.setenv("UMMIX_CODEX_PATH", str(exe))
    assert discover_codex().source == "configurado"


def test_invalid_override_is_not_silently_ignored(monkeypatch, tmp_path):
    no_path(monkeypatch, tmp_path)
    monkeypatch.setenv("UMMIX_CODEX_PATH", str(tmp_path / "missing.exe"))
    assert discover_codex().path is None
    shim = tmp_path / "codex.cmd"
    shim.write_text("fixture", encoding="utf-8")
    assert discover_codex(str(shim)).path is None


def test_missing_executable_reports_clear_diagnosis(monkeypatch, tmp_path):
    no_path(monkeypatch, tmp_path)
    result = discover_codex()
    assert result.path is None
    assert "--codex-path" in result.error


@pytest.mark.parametrize("authenticated,tools,called,replied,error,expected", [
    (False, TOOLS, True, True, None, "AUTENTICACAO_NECESSARIA"),
    (True, {"listar_mercados"}, True, True, None, "MCP_INDISPONIVEL"),
    (True, TOOLS, False, True, None, "MODELO_OU_MCP_FALHOU"),
    (True, TOOLS, True, False, None, "MODELO_OU_MCP_FALHOU"),
    (True, TOOLS, True, True, "Rede indisponível", "MODELO_OU_MCP_FALHOU"),
    (True, TOOLS, True, True, None, "CONEXAO_VERIFICADA"),
])
def test_health_requires_login_model_and_real_tool_evidence(monkeypatch, tmp_path, authenticated, tools, called, replied, error, expected):
    async def scenario():
        monkeypatch.setattr(web_agent, "discover_codex", lambda command=None: CodexExecutable("fixture-codex.exe", "teste"))

        class LoginProcess:
            returncode = 0 if authenticated else 1

            async def communicate(self):
                return b"", b"credentials fixture"

        async def spawn(*args, **kwargs):
            assert args[1:] == ("login", "status")
            return LoginProcess()

        @asynccontextmanager
        async def mcp_connect(db):
            class MCPFixture:
                async def list_tools(self):
                    return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in tools])
            yield MCPFixture()

        monkeypatch.setattr(web_agent.asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(web_agent, "connect", mcp_connect)
        agent = CodexAgent(tmp_path / "db.sqlite3", tmp_path / "runtime")
        probes = []

        async def model_probe(session, permit=None, *, probe=False):
            assert probe is True
            probes.append(session.id)
            session.last_error = error
            if called:
                session.events.append({"type": "tool", "tool": "listar_mercados", "status": "completed", "response": {"ok": True, "dados_simulados": True}})
            if replied:
                session.messages.append({"role": "assistant", "content": "Resposta de fixture unitária"})

        monkeypatch.setattr(agent, "run", model_probe)
        result = await agent.health()
        assert result["code"] == expected
        assert result["ready"] is (expected == "CONEXAO_VERIFICADA")
        assert result["model_verified"] is result["ready"]
        assert result["mcp_verified"] is result["ready"]
        assert result["checked_at"] and result["valid_until"]
        if not authenticated or tools != TOOLS:
            assert not probes
    asyncio.run(scenario())


def test_concurrent_checks_share_probe_and_force_refreshes(monkeypatch, tmp_path):
    async def scenario():
        monkeypatch.setattr(web_agent, "discover_codex", lambda command=None: CodexExecutable("fixture-codex.exe", "teste"))
        agent = CodexAgent(tmp_path / "db.sqlite3", tmp_path / "runtime")
        calls = []

        async def probe():
            calls.append(True)
            await asyncio.sleep(0)
            return agent.remember_health({"ready": True, "model_verified": True, "mcp_verified": True})

        monkeypatch.setattr(agent, "_probe_health", probe)
        results = await asyncio.gather(agent.health(), agent.health(), agent.health())
        assert len(calls) == 1
        assert all(r["ready"] for r in results)
        await agent.health()
        assert len(calls) == 1
        await agent.health(force=True)
        assert len(calls) == 2
        agent._health_expires = 0
        await agent.health()
        assert len(calls) == 3
    asyncio.run(scenario())


def test_health_probe_cannot_write_simulations_or_plans():
    policy = ApprovalPolicy(read_only=True)
    assert policy.check("listar_mercados", {}) is None
    for tool in ("simular_plano", "registrar_aprovacao", "criar_plano"):
        assert policy.check(tool, {})
