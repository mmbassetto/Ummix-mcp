"""Inventário mock versionado e substituível; nenhuma API externa."""

import json
import unicodedata
from importlib.resources import files
from pathlib import Path

from pydantic import ValidationError

from .models import InventoryItem, InventoryQuery

MARKETS = ("Goiânia", "Anápolis", "Rio Verde")
SEGMENTS = ("geral", "adultos", "jovens", "familias", "empresarios")


class DomainError(Exception):
    def __init__(self, code: str, message: str, **details: object):
        super().__init__(message)
        self.code = code
        self.details = details


def normalized(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold().strip()) if not unicodedata.combining(c))


def resolve_markets(values: list[str]) -> list[str]:
    lookup = {normalized(name): name for name in MARKETS}
    result = []
    for value in values:
        canonical = lookup.get(normalized(value))
        if canonical is None:
            raise DomainError("MERCADO_INEXISTENTE", "Praça não cadastrada; consulte listar_mercados.", mercado=value)
        if canonical in result:
            raise DomainError("ENTRADA_INVALIDA", "Praças duplicadas após normalização.")
        result.append(canonical)
    return result


class MockInventoryRepository:
    def __init__(self, path: str | Path | None = None):
        try:
            raw = Path(path).read_text(encoding="utf-8") if path else files("ummix_mcp").joinpath("data/mock_inventory.json").read_text(encoding="utf-8")
            self.items = tuple(InventoryItem.model_validate(row) for row in json.loads(raw)["itens"])
            if len({item.id for item in self.items}) != len(self.items):
                raise ValueError("IDs de inventário duplicados.")
            for item in self.items:
                if item.mercado not in MARKETS:
                    raise ValueError("Praça desconhecida no inventário.")
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise DomainError("INVENTARIO_INVALIDO", "Seed ausente ou inválido; revise UMMIX_INVENTORY_PATH.") from exc

    def query(self, query: InventoryQuery) -> list[tuple[InventoryItem, int]]:
        markets = resolve_markets(query.mercados)
        unknown = sorted(set(query.restricoes.excluir_veiculos) - {i.id for i in self.items})
        if unknown:
            raise DomainError("VEICULO_INEXISTENTE", "Restrição referencia veículo não cadastrado.", veiculos=unknown)
        selected = []
        for item in self.items:
            if item.mercado not in markets or item.canal not in query.canais:
                continue
            if query.publico and query.publico not in item.segmentos:
                continue
            if item.id in query.restricoes.excluir_veiculos:
                continue
            if query.restricoes.faixa_horaria and item.faixa_horaria != query.restricoes.faixa_horaria:
                continue
            capacity = item.capacidade_diaria * query.periodo.days
            if query.restricoes.max_insercoes_por_veiculo is not None:
                capacity = min(capacity, query.restricoes.max_insercoes_por_veiculo)
            if capacity > 0:
                selected.append((item, capacity))
        return sorted(selected, key=lambda pair: pair[0].id)
