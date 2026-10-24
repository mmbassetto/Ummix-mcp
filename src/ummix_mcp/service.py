"""Casos de uso e configuração, compartilhados pelo MCP e testes."""

import os

from .domain import ASSUMPTIONS, PlanningEngine, money
from .models import Briefing, InventoryQuery
from .repositories import MARKETS, SEGMENTS, DomainError, MockInventoryRepository, normalized, resolve_markets
from .storage import Storage


class UmmixService:
    def __init__(self, inventory: MockInventoryRepository, storage: Storage):
        self.inventory = inventory
        self.storage = storage
        self.engine = PlanningEngine(inventory)

    @classmethod
    def from_env(cls) -> "UmmixService":
        return cls(MockInventoryRepository(os.getenv("UMMIX_INVENTORY_PATH")), Storage(os.getenv("UMMIX_DB_PATH", "var/ummix.sqlite3")))

    def list_markets(self, filtro: str | None = None) -> dict:
        return {"mercados": [m for m in MARKETS if not filtro or normalized(filtro) in normalized(m)], "fonte": "seed fictício v1"}

    def list_segments(self, mercado: str | None = None) -> dict:
        markets = resolve_markets([mercado]) if mercado else list(MARKETS)
        available = {segment for item in self.inventory.items if item.mercado in markets for segment in item.segmentos}
        return {"mercados": markets, "segmentos": [s for s in SEGMENTS if s in available],
                "limitacoes": "Segmentação hipotética por afinidade editorial; não representa medição de audiência."}

    def query_inventory(self, query: InventoryQuery) -> dict:
        pairs = self.inventory.query(query)
        if not pairs:
            raise DomainError("INVENTARIO_INDISPONIVEL", "Nenhum item elegível; reveja canais, público e restrições.")
        return {"periodo": query.periodo.model_dump(mode="json"), "itens": [
            {**item.model_dump(mode="json"), "capacidade_periodo": cap,
             "cpm_unitario_simulado": money(item.custo_por_insercao / item.impressoes_por_insercao * 1000) if item.impressoes_por_insercao else None}
            for item, cap in pairs
        ], "premissas": ASSUMPTIONS}

    def simulate(self, briefing: Briefing) -> dict:
        return self.storage.save_simulation(self.engine.simulate(briefing))
