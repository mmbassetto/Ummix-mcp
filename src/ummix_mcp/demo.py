"""Cliente MCP real sem LLM; a opção de aprovação é exclusivamente de teste."""

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .models import BANNER

TOOLS = {"listar_mercados", "listar_segmentos", "consultar_inventario", "simular_plano", "registrar_aprovacao", "criar_plano", "consultar_plano"}
DEMO_BRIEFING = {
    "objetivo": "Divulgar um produto fictício no comércio regional",
    "publico": "adultos", "mercados": ["Goiânia", "Anápolis", "Rio Verde"],
    "orcamento": "5000.00", "periodo": {"inicio": "2026-11-01", "fim": "2026-11-07"},
    "canais": ["radio", "tv"], "restricoes": {},
}


@asynccontextmanager
async def connect(db: Path):
    params = StdioServerParameters(command=sys.executable, args=["-m", "ummix_mcp.server"],
                                   env={**os.environ, "UMMIX_DB_PATH": str(db.resolve()), "PYTHONUTF8": "1"})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            yield session


def unpack(result) -> dict:
    if result.isError:
        raise RuntimeError("Erro MCP: " + str(result.content))
    if result.structuredContent is None:
        raise RuntimeError("Servidor não retornou saída estruturada.")
    payload = result.structuredContent
    if payload.get("aviso") != BANNER or payload.get("dados_simulados") is not True:
        raise RuntimeError("Saída sem identificação de dados simulados.")
    return payload


async def run_demo(db: Path, output: Path, approve_demo: bool) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as trace:
        def record(event: str, **data):
            trace.write(json.dumps({"evento": event, "horario_utc": datetime.now(timezone.utc).isoformat(),
                                    "aviso": BANNER, "dados_simulados": True, **data}, ensure_ascii=False) + "\n")
            trace.flush()

        async def call(session, name, arguments, expected_error=None):
            result = unpack(await asyncio.wait_for(session.call_tool(name, arguments=arguments), timeout=30))
            record("chamada_mcp", ferramenta=name, argumentos=arguments, resposta=result)
            if expected_error:
                if result["ok"] or result["erro"]["codigo"] != expected_error:
                    raise RuntimeError(f"Esperado {expected_error}; recebido {result}")
            elif not result["ok"]:
                raise RuntimeError(str(result["erro"]))
            return result.get("dados")

        print(BANNER)
        print("Cliente roteirizado sem LLM; aprovação deste ensaio é uma confirmação de teste.")
        async with connect(db) as session:
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            if names != TOOLS:
                raise RuntimeError(f"Ferramentas inesperadas: {names}")
            record("descoberta_mcp", ferramentas=sorted(names), schemas=[t.model_dump(mode="json") for t in listing.tools])
            print("Descobertas 7 ferramentas MCP por stdio.")
            await call(session, "listar_mercados", {})
            await call(session, "listar_segmentos", {"mercado": "Goiânia"})
            await call(session, "consultar_inventario", {"consulta": {
                key: DEMO_BRIEFING[key] for key in ["mercados", "periodo", "canais", "publico", "restricoes"]
            }})
            await call(session, "simular_plano", {"briefing": {**DEMO_BRIEFING, "orcamento": "1.00"}}, "ORCAMENTO_INSUFICIENTE")
            simulation = await call(session, "simular_plano", {"briefing": DEMO_BRIEFING})
            sim_id = simulation["simulation_id"]
            for alt in simulation["alternativas"]:
                print(f"{alt['alternativa_id']}: R$ {alt['custo_total']}; saldo R$ {alt['saldo']}; CPM sintético {alt['cpm_estimado']}")
            alternative_id = simulation["alternativas"][0]["alternativa_id"]
            creation = {"simulation_id": sim_id, "alternativa_id": alternative_id,
                        "approval_id": "ausente", "chave_idempotente": str(uuid4())}
            await call(session, "criar_plano", creation, "APROVACAO_AUSENTE")
            if not approve_demo:
                print(f"Para este ensaio: simulation_id={sim_id}, alternativa_id={alternative_id}.")
                if not sys.stdin.isatty() or input("Digite APROVAR para salvar o rascunho simulado: ").strip() != "APROVAR":
                    record("ensaio_sem_aprovacao", simulation_id=sim_id)
                    print("Simulação concluída; nenhum plano criado. Use --aprovar-demo somente para ensaio automatizado.")
                    return {"simulation_id": sim_id, "plan_id": None}
            record("confirmacao_de_teste", simulation_id=sim_id, alternativa_id=alternative_id,
                   origem="flag --aprovar-demo" if approve_demo else "entrada APROVAR no terminal")
            approval = await call(session, "registrar_aprovacao", {"simulation_id": sim_id,
                                  "alternativa_id": alternative_id, "confirmacao_explicita": True})
            creation["approval_id"] = approval["approval_id"]
            plan = await call(session, "criar_plano", creation)
            replay = await call(session, "criar_plano", creation)
            if plan["plan_id"] != replay["plan_id"] or replay["reutilizado"] is not True:
                raise RuntimeError("Idempotência não comprovada.")
            await call(session, "consultar_plano", {"plan_id": plan["plan_id"]})
        # Processo anterior terminou: novo servidor, mesmo SQLite.
        async with connect(db) as restarted:
            recovered = await call(restarted, "consultar_plano", {"plan_id": plan["plan_id"]})
            if recovered["status"] != "RASCUNHO_APROVADO":
                raise RuntimeError("Plano não persistiu após reinício.")
        record("ensaio_concluido", plan_id=plan["plan_id"], persistencia_apos_reinicio=True, orquestracao_llm=False)
        print(f"Plano {plan['plan_id']}: RASCUNHO_APROVADO; idempotência e recuperação após reinício verificadas.")
        print(f"Registro: {output.resolve()}")
        return {"simulation_id": sim_id, "plan_id": plan["plan_id"], "orquestracao_llm": False}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=BANNER + " — cliente de teste sem LLM")
    parser.add_argument("--db", type=Path, default=Path("var/demo.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo_trace.jsonl"))
    parser.add_argument("--aprovar-demo", action="store_true", help="Confirmação simulada para ensaio automatizado; não representa aprovação de cliente real.")
    args = parser.parse_args()
    asyncio.run(run_demo(args.db, args.output, args.aprovar_demo))


if __name__ == "__main__":
    main()
