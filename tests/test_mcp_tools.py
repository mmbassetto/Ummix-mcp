import asyncio
import json

from ummix_mcp.demo import DEMO_BRIEFING, TOOLS, connect, run_demo, unpack
from ummix_mcp.models import BANNER


def test_real_stdio_discovery_and_calls(tmp_path):
    async def scenario():
        async with connect(tmp_path / "protocol.sqlite3") as session:
            result = await session.list_tools()
            assert {tool.name for tool in result.tools} == TOOLS
            for tool in result.tools:
                assert tool.inputSchema["type"] == "object"
                assert tool.outputSchema["properties"]["dados_simulados"]["const"] is True
                assert tool.description
            response = unpack(await session.call_tool("listar_mercados", {}))
            assert response["ok"] is True
            assert response["dados"]["mercados"] == ["Goiânia", "Anápolis", "Rio Verde"]
            invalid = unpack(await session.call_tool("listar_segmentos", {"mercado": "ausente"}))
            assert invalid["erro"]["codigo"] == "MERCADO_INEXISTENTE"
            denied = unpack(await session.call_tool("registrar_aprovacao", {
                "simulation_id": "ausente", "alternativa_id": "eficiencia", "confirmacao_explicita": False,
            }))
            assert denied["erro"]["codigo"] == "CONFIRMACAO_OBRIGATORIA"
            wrong_type = await session.call_tool("registrar_aprovacao", {
                "simulation_id": "ausente", "alternativa_id": "eficiencia", "confirmacao_explicita": "true",
            })
            assert unpack(wrong_type)["erro"]["codigo"] == "ENTRADA_INVALIDA"
            invalid_briefing = await session.call_tool("simular_plano", {"briefing": {}})
            assert unpack(invalid_briefing)["ok"] is False
            bad_date = unpack(await session.call_tool("simular_plano", {"briefing": {
                **DEMO_BRIEFING, "periodo": {"inicio": "2026-11-10", "fim": "2026-11-01"},
            }}))
            assert bad_date["erro"]["codigo"] == "PERIODO_INVALIDO"
            bad_budget = unpack(await session.call_tool("simular_plano", {"briefing": {**DEMO_BRIEFING, "orcamento": "-1"}}))
            assert bad_budget["erro"]["codigo"] == "ENTRADA_INVALIDA"
    asyncio.run(scenario())


def test_full_demo_real_process_restart(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    result = asyncio.run(run_demo(tmp_path / "demo.sqlite3", trace_path, approve_demo=True))
    assert result["plan_id"]
    assert result["orquestracao_llm"] is False
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert all(e["aviso"] == BANNER and e["dados_simulados"] for e in events)
    assert {e["ferramenta"] for e in events if e["evento"] == "chamada_mcp"} == TOOLS
    assert events[-1]["persistencia_apos_reinicio"] is True
