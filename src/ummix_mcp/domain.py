"""Motor puro, determinístico e sem dependência de MCP ou SQLite."""

from decimal import Decimal, ROUND_HALF_UP

from .models import Briefing, InventoryItem, InventoryQuery
from .repositories import DomainError, MockInventoryRepository, resolve_markets

CENT = Decimal("0.01")
ASSUMPTIONS = [
    "Todos os veículos, preços, capacidades e impressões são fictícios; moeda ilustrativa BRL.",
    "Capacidade do período = capacidade diária × dias inclusivos; distribuição diária uniforme possível.",
    "Cada praça solicitada recebe pelo menos uma inserção; canais são elegíveis, não cotas obrigatórias.",
    "Impressões brutas sintéticas = inserções × impressões por inserção, constantes e aditivas, sem promessa de entrega.",
    "CPM = custo / impressões estimadas × 1000, somente com impressões conhecidas em todos os itens.",
    "Alcance único e frequência omitidos: não há dados de deduplicação ou modelo de sobreposição validado.",
    "Objetivo é contexto textual; público filtra segmentos exatos do seed, sem inferência semântica.",
    "Heurística de eficiência usa CPM unitário; não garante ótimo global nem precisão estatística.",
    "Planos são rascunhos independentes: não reservam nem consomem inventário entre simulações.",
]


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


class PlanningEngine:
    def __init__(self, inventory: MockInventoryRepository):
        self.inventory = inventory

    def simulate(self, briefing: Briefing) -> dict:
        markets = resolve_markets(briefing.mercados)
        pairs = self.inventory.query(InventoryQuery(
            mercados=markets, periodo=briefing.periodo, canais=briefing.canais,
            publico=briefing.publico, restricoes=briefing.restricoes,
        ))
        by_id = {item.id: item for item, _ in pairs}
        caps = {item.id: cap for item, cap in pairs}
        cheapest: dict[str, InventoryItem] = {}
        for market in markets:
            candidates = [item for item, _ in pairs if item.mercado == market]
            if not candidates:
                raise DomainError("INVENTARIO_INDISPONIVEL", "Nenhum item elegível para uma das praças; reveja público, canais e restrições.", mercado=market)
            cheapest[market] = min(candidates, key=lambda item: (item.custo_por_insercao, item.id))
        minimum = sum((item.custo_por_insercao for item in cheapest.values()), Decimal(0))
        if minimum > briefing.orcamento:
            raise DomainError("ORCAMENTO_INSUFICIENTE", "Orçamento não cobre uma inserção por praça solicitada.", minimo_simulado=money(minimum), orcamento=money(briefing.orcamento))
        base = {item.id: 1 for item in cheapest.values()}

        def cost(allocation: dict[str, int]) -> Decimal:
            return sum((by_id[key].custo_por_insercao * qty for key, qty in allocation.items()), Decimal(0))

        def unit_efficiency(item: InventoryItem) -> tuple:
            cpm = item.custo_por_insercao / item.impressoes_por_insercao if item.impressoes_por_insercao else Decimal("Infinity")
            return cpm, item.custo_por_insercao, item.id

        def fill(seed: dict[str, int], diversify: bool) -> dict[str, int]:
            allocation = dict(seed)
            remaining = briefing.orcamento - cost(allocation)
            items = sorted(by_id.values(), key=unit_efficiency)
            # Em diversificação: uma inserção em cada veículo elegível antes de concentrar.
            if diversify:
                for item in sorted(items, key=lambda i: (i.id in allocation, i.custo_por_insercao, i.id)):
                    if item.id not in allocation and remaining >= item.custo_por_insercao:
                        allocation[item.id] = 1
                        remaining -= item.custo_por_insercao
            for item in items:
                extra = min(caps[item.id] - allocation.get(item.id, 0), int(remaining // item.custo_por_insercao))
                if extra:
                    allocation[item.id] = allocation.get(item.id, 0) + extra
                    remaining -= item.custo_por_insercao * extra
            return allocation

        candidates = [
            ("eficiencia", "Eficiência ilustrativa", fill(base, False), "Mantém presença mínima por praça e concentra saldo por CPM unitário conhecido; desempate por preço e ID."),
            ("diversificacao", "Diversificação ilustrativa", fill(base, True), "Prioriza uma inserção por veículo elegível que caiba no saldo e depois preenche por CPM unitário."),
            ("economico", "Presença mínima", base, "Usa apenas a inserção mais barata em cada praça e preserva o restante do orçamento."),
        ]
        unique = []
        seen = set()
        for alt_id, name, allocation, reason in candidates:
            signature = tuple(sorted(allocation.items()))
            if signature not in seen:
                seen.add(signature)
                unique.append((alt_id, name, allocation, reason))
        # Se o mínimo for a única alocação encontrada, qualquer outra solução
        # tem um acréscimo ou troca unitária viável a partir dele (custos positivos).
        if len(unique) == 1:
            for item in sorted(by_id.values(), key=lambda i: (i.custo_por_insercao, i.id)):
                alternative = dict(base)
                origin = cheapest[item.mercado]
                if item.id == origin.id:
                    alternative[item.id] += 1
                else:
                    alternative.pop(origin.id)
                    alternative[item.id] = 1
                if alternative.get(item.id, 0) <= caps[item.id] and cost(alternative) <= briefing.orcamento:
                    signature = tuple(sorted(alternative.items()))
                    if signature not in seen:
                        unique.append(("variacao", "Variação viável", alternative, "Troca ou acréscimo unitário sobre a presença mínima, respeitando orçamento e capacidade."))
                        break
        warnings = []
        if len(unique) == 1:
            warnings.append("Somente uma alocação viável sob os filtros, orçamento e capacidades informados.")
        if any(item.impressoes_por_insercao is None for item, _ in pairs):
            warnings.append("Itens sem impressões sintéticas não têm CPM; totais incompletos são omitidos.")
        alternatives = []
        for alt_id, name, allocation, reason in unique[:2]:
            total = cost(allocation)
            rows = []
            for key, qty in sorted(allocation.items()):
                item = by_id[key]
                rows.append({
                    "veiculo_id": key, "nome": item.nome, "mercado": item.mercado,
                    "canal": item.canal, "faixa_horaria": item.faixa_horaria,
                    "insercoes": qty, "capacidade_periodo": caps[key],
                    "capacidade_diaria": item.capacidade_diaria,
                    "distribuicao_diaria": {"base": qty // briefing.periodo.days, "dias_com_uma_extra": qty % briefing.periodo.days},
                    "custo_unitario": money(item.custo_por_insercao), "custo_total": money(item.custo_por_insercao * qty),
                    "impressoes_estimadas": item.impressoes_por_insercao * qty if item.impressoes_por_insercao is not None else None,
                })
            impressions = sum(row["impressoes_estimadas"] for row in rows) if all(row["impressoes_estimadas"] is not None for row in rows) else None
            alternatives.append({
                "alternativa_id": alt_id, "nome": name, "alocacao": rows,
                "custo_total": money(total), "saldo": money(briefing.orcamento - total),
                "impressoes_estimadas": impressions,
                "cpm_estimado": money(total / impressions * 1000) if impressions else None,
                "alcance_unico_estimado": None, "frequencia_media": None,
                "justificativa": reason,
            })
        canonical = briefing.model_dump(mode="json")
        canonical["mercados"] = markets
        return {"briefing": canonical, "alternativas": alternatives, "premissas": ASSUMPTIONS, "alertas": warnings}
