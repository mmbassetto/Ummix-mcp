"""Conferência de decisões públicas e filtros, exclusivamente sobre saídas MCP observadas."""

from decimal import Decimal

from .models import InventoryQuery
from .repositories import DomainError, resolve_markets


CRITERIA = {
    "menor_cpm": ("Menor CPM sintético disponível", "cpm_estimado", min),
    "menor_custo": ("Menor investimento", "custo_total", min),
    "mais_insercoes": ("Maior quantidade de inserções", "insercoes", max),
    "mais_veiculos": ("Maior diversidade de veículos", "veiculos", max),
    "mais_canais": ("Maior diversidade de canais", "canais", max),
    "mais_combinacoes_praca_canal": ("Mais combinações de cidade e canal", "combinacoes_praca_canal", max),
}


def alternative_facts(alt: dict) -> dict:
    return {"alternativa_id": alt["alternativa_id"], "nome": alt["nome"],
            "custo_total": alt["custo_total"], "saldo": alt["saldo"],
            "cpm_estimado": alt["cpm_estimado"], "impressoes_estimadas": alt["impressoes_estimadas"],
            "insercoes": sum(row["insercoes"] for row in alt["alocacao"]),
            "veiculos": len({row["veiculo_id"] for row in alt["alocacao"]}),
            "canais": len({row["canal"] for row in alt["alocacao"]}),
            "combinacoes_praca_canal": len({(row["mercado"], row["canal"]) for row in alt["alocacao"]})}


def validate_decision(simulation: dict | None, candidate: dict, source: str) -> dict:
    """O modelo escolhe; esta função apenas aceita ou rejeita a escolha, sem substituí-la."""
    if not simulation or candidate.get("simulation_id") != simulation["simulation_id"]:
        raise ValueError("A recomendação não corresponde à simulação atual.")
    criterion = candidate.get("criterio")
    if not isinstance(criterion, str) or criterion not in CRITERIA:
        raise ValueError("O agente não forneceu um critério verificável permitido.")
    label, field, optimum = CRITERIA[criterion]
    facts = [alternative_facts(a) for a in simulation["alternativas"]]
    if any(a[field] is None for a in facts):
        raise ValueError("O critério depende de uma métrica indisponível em uma das alternativas.")
    values = [Decimal(str(a[field])) for a in facts]
    winners = [a["alternativa_id"] for a, value in zip(facts, values) if value == optimum(values)]
    if candidate.get("alternativa_id") not in winners:
        raise ValueError("A alternativa indicada não atende ao critério declarado nos dados MCP.")
    return {"simulation_id": simulation["simulation_id"], "alternativa_id": candidate["alternativa_id"],
            "criterio": criterion, "criterio_label": label, "campo_comparado": field,
            "comparacao": [{"alternativa_id": a["alternativa_id"], "nome": a["nome"], "valor": a[field]} for a in facts],
            "empate": len(winners) > 1, "verificada": True, "escolha_por": "agente_ia",
            "fonte": "simular_plano", "evento_mcp": source, "dados_simulados": True}


def briefing_evidence(simulation: dict | None, events: list[dict]) -> list[dict]:
    if not simulation:
        return []
    briefing = simulation["briefing"]
    completed = [e for e in events if e.get("type") == "tool" and e.get("status") == "completed"]
    sim_event = next((e for e in reversed(completed) if e.get("tool") == "simular_plano"
                      and (e.get("response", {}).get("dados") or {}).get("simulation_id") == simulation["simulation_id"]), None)
    # Só usa inventário consultado antes desta simulação, com os mesmos filtros completos.
    inventory = None
    for event in reversed(completed[:completed.index(sim_event)] if sim_event else []):
        if event.get("tool") != "consultar_inventario":
            continue
        query = (event.get("arguments") or {}).get("consulta", {})
        try:
            query = InventoryQuery.model_validate(query).model_dump(mode="json")
            query["mercados"] = resolve_markets(query["mercados"])
        except (ValueError, TypeError, DomainError):
            continue
        if (set(query["mercados"]) == set(briefing["mercados"]) and query["periodo"] == briefing["periodo"]
                and set(query["canais"]) == set(briefing["canais"]) and query["publico"] == briefing["publico"]
                and query["restricoes"] == briefing["restricoes"]):
            inventory = event
            break
    catalog = {r["id"]: r for r in (inventory or {}).get("response", {}).get("dados", {}).get("itens", [])}
    result = []
    for alt in simulation["alternativas"]:
        rows = alt["alocacao"]

        def add(filter_name, ok, detail, *, known=True, source="simular_plano"):
            result.append({"alternativa_id": alt["alternativa_id"], "filtro": filter_name,
                           "status": ("atendido_no_seed" if ok else "nao_atendido") if known else "nao_comprovado",
                           "detalhe": detail, "fonte": source,
                           "evento_mcp": (inventory or {}).get("key") if source == "consultar_inventario" else (sim_event or {}).get("key")})

        markets = {r["mercado"] for r in rows}
        missing = set(briefing["mercados"]) - markets
        add("Cidades", not missing, "Praças alocadas: " + ", ".join(sorted(markets)) + (". Ausentes: " + ", ".join(sorted(missing)) if missing else "."))
        add("Orçamento", Decimal(alt["custo_total"]) <= Decimal(briefing["orcamento"]),
            f"Investimento BRL {alt['custo_total']} de BRL {briefing['orcamento']}; saldo BRL {alt['saldo']}.")
        channels = {r["canal"] for r in rows}
        missing_channels = set(briefing["canais"]) - channels
        add("Canais solicitados", not missing_channels,
            "Alocados: " + ", ".join(sorted(channels)) + (". Sem inserções: " + ", ".join(sorted(missing_channels)) if missing_channels else ".")
            + " O motor trata canais como elegibilidade, sem cota obrigatória.")
        missing_pairs = {(m, c) for m in briefing["mercados"] for c in briefing["canais"]} - {(r["mercado"], r["canal"]) for r in rows}
        add("Canais em cada cidade", not missing_pairs,
            "Todas as combinações cidade/canal têm inserções." if not missing_pairs else
            "Sem inserções para: " + ", ".join(m + "/" + c for m, c in sorted(missing_pairs)) + ". Ter os dois canais no plano não comprova os dois em cada cidade.")
        add("Período e capacidade", all(0 < r["insercoes"] <= r["capacidade_periodo"] for r in rows),
            f"{briefing['periodo']['inicio']} a {briefing['periodo']['fim']}; inserções dentro da capacidade fictícia. Sem reserva real.")
        known = bool(rows) and all(r["veiculo_id"] in catalog for r in rows)
        add("Segmento do catálogo", all(briefing["publico"] in catalog.get(r["veiculo_id"], {}).get("segmentos", []) for r in rows),
            f"Segmento estruturado: {briefing['publico']}. Afinidade editorial hipotética; não comprova audiência real."
            if known else "Falta consulta de inventário com os mesmos filtros para conferir os segmentos dos veículos.",
            known=known, source="consultar_inventario")
        restrictions = briefing["restricoes"]
        ok = all(r["veiculo_id"] not in restrictions["excluir_veiculos"]
                 and (not restrictions["faixa_horaria"] or r["faixa_horaria"] == restrictions["faixa_horaria"])
                 and (restrictions["max_insercoes_por_veiculo"] is None or r["insercoes"] <= restrictions["max_insercoes_por_veiculo"]) for r in rows)
        add("Restrições estruturadas", ok, "Conferidos veículos excluídos, faixa horária e limite de inserções informados no briefing estruturado.")
        add("Objetivo e público real", False, "Objetivo: " + briefing["objetivo"]
            + ". O seed não comprova conversões, vendas, perfil demográfico detalhado, renda ou entrega ao público pretendido.", known=False)
        add("Alcance único e frequência", False, "Indisponíveis: não há deduplicação nem modelo de sobreposição validado.", known=False)
    return result
