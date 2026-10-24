"""Ensaio opcional com Codex CLI autenticado; backend/testes não dependem dele.

Usa sessões efêmeras, configuração apenas desta invocação e nenhum pagamento/API key.
O acesso ao modelo usa a conta já autenticada e está sujeito aos limites dessa conta.
"""

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_phase(command: str, db: Path, output: Path, phase: str, prompt: str) -> list[dict]:
    args = [command, "exec", "--ignore-user-config", "--ephemeral", "--json", "--sandbox", "read-only",
            "-C", str(ROOT), "-c", 'approval_policy="never"']
    config = {
        "mcp_servers.ummix.command": sys.executable,
        "mcp_servers.ummix.args": ["-m", "ummix_mcp.server"],
        "mcp_servers.ummix.cwd": str(ROOT),
        "mcp_servers.ummix.env.UMMIX_DB_PATH": str(db),
        "mcp_servers.ummix.env.PYTHONUTF8": "1",
        "mcp_servers.ummix.startup_timeout_sec": 30,
        "mcp_servers.ummix.tool_timeout_sec": 30,
    }
    for key, value in config.items():
        args.extend(["-c", key + "=" + json.dumps(value)])
    args.append(prompt)
    output.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180)
    except subprocess.TimeoutExpired as exc:
        (output / f"{phase}.stdout.jsonl").write_bytes(exc.stdout or b"")
        (output / f"{phase}.stderr.txt").write_bytes(exc.stderr or b"")
        raise RuntimeError("Cliente LLM excedeu 180 s; integração não comprovada.") from exc
    (output / f"{phase}.stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
    (output / f"{phase}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    events = []
    for line in completed.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if completed.returncode != 0 or not any(e.get("type") == "turn.completed" for e in events):
        raise RuntimeError(f"Cliente LLM falhou (exit={completed.returncode}); consulte {output}.")
    return events


def called_tools(events: list[dict]) -> set[str]:
    return {e["item"]["tool"] for e in events if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") == "mcp_tool_call" and e["item"].get("server") == "ummix"
            and e["item"].get("status") == "completed"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="DEMONSTRAÇÃO COM DADOS SIMULADOS — teste opcional com LLM real")
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--aprovar-ensaio", action="store_true", help="Autoriza confirmação de teste para a alternativa retornada pelo LLM; nenhum cliente real.")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/llm")
    args = parser.parse_args()
    if not args.codex:
        parser.error("Codex CLI não instalado; use a demo sem LLM.")
    db = (args.output / "llm.sqlite3").resolve()
    if db.exists():
        parser.error("Use --output com uma pasta nova para manter a evidência isolada.")
    db.parent.mkdir(parents=True, exist_ok=True)
    print("DEMONSTRAÇÃO COM DADOS SIMULADOS", flush=True)
    print("Ensaio LLM opcional via conta já autenticada; duas sessões efêmeras, sem alterar configuração global.", flush=True)
    first = run_phase(args.codex, db, args.output, "01_simulacao", (
        "Você é o cliente de um ensaio do Ummix MCP. Use exclusivamente as ferramentas MCP do servidor ummix; "
        "não use shell, não leia arquivos e não altere código. Todos os dados são simulados. "
        "Consulte mercados, segmentos e inventário. Simule para divulgar um produto fictício, público adultos, "
        "Goiânia, Anápolis e Rio Verde, orçamento BRL 5000.00, 2026-11-01 a 2026-11-07, canais radio e tv, sem restrições. "
        "Compare as alternativas retornadas com custos e premissas. Não registre aprovação e não crie plano. "
        "Ao final peça confirmação explícita indicando simulation_id e alternativa_id. "
        "Mostre DEMONSTRAÇÃO COM DADOS SIMULADOS e não prometa alcance único ou compra."
    ))
    tools = called_tools(first)
    if not {"listar_mercados", "listar_segmentos", "consultar_inventario", "simular_plano"} <= tools:
        raise RuntimeError(f"Chamadas MCP insuficientes na evidência: {tools}")
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT body FROM simulations").fetchall()
        if len(rows) != 1 or conn.execute("SELECT count(*) FROM approvals").fetchone()[0] != 0 or conn.execute("SELECT count(*) FROM plans").fetchone()[0] != 0:
            raise RuntimeError("Fase 1 não produziu exatamente uma simulação sem aprovação/plano.")
        simulation = json.loads(rows[0][0])
    sim_id = simulation["simulation_id"]
    alt_id = simulation["alternativas"][0]["alternativa_id"]
    print(f"LLM utilizou {len(tools)} ferramentas distintas; simulation_id={sim_id}.", flush=True)
    if not args.aprovar_ensaio:
        print("Ensaio interrompido antes da aprovação. Para ensaio completo, use --aprovar-ensaio em nova pasta.")
        return
    second = run_phase(args.codex, db, args.output, "02_aprovacao", (
        "Você é o cliente de um ensaio do Ummix MCP. Use exclusivamente ferramentas MCP do servidor ummix. "
        "Não use shell nem leia arquivos. Esta é a confirmação de teste do operador (--aprovar-ensaio), "
        "não de um anunciante real. Na etapa anterior foi simulada campanha fictícia para adultos em Goiânia, "
        "Anápolis e Rio Verde, BRL 5000.00, de 2026-11-01 a 2026-11-07. "
        f"Aprovo explicitamente a simulação {sim_id}, alternativa {alt_id}, para salvar somente rascunho simulado. "
        "Registre essa aprovação usando exatamente os IDs informados, crie o plano com uma chave idempotente "
        "e consulte o plano salvo. Apresente plan_id, status, custo e limitações retornadas. "
        "Mostre DEMONSTRAÇÃO COM DADOS SIMULADOS. Não faça nova simulação nem prometa veiculação."
    ))
    if not {"registrar_aprovacao", "criar_plano", "consultar_plano"} <= called_tools(second):
        raise RuntimeError("LLM não completou aprovação, criação e consulta por MCP.")
    with sqlite3.connect(db) as conn:
        plans = conn.execute("SELECT body FROM plans WHERE simulation_id = ? AND alternative_id = ?", (sim_id, alt_id)).fetchall()
        if len(plans) != 1:
            raise RuntimeError("Plano persistido não foi comprovado.")
        plan = json.loads(plans[0][0])
    report = {"aviso": "DEMONSTRAÇÃO COM DADOS SIMULADOS", "dados_simulados": True,
              "cliente": "Codex CLI", "sessoes_efemeras": 2, "confirmacao": "fixture de teste autorizada por --aprovar-ensaio",
              "simulation_id": sim_id, "plan_id": plan["plan_id"], "status": plan["status"],
              "ferramentas": sorted(tools | called_tools(second)), "orquestracao_llm": True}
    (args.output / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
