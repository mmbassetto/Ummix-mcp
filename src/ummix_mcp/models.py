"""Contratos tipados; textos recebidos são dados, nunca comandos."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BANNER = "DEMONSTRAÇÃO COM DADOS SIMULADOS"
Channel = Literal["radio", "tv"]
Segment = Literal["geral", "adultos", "jovens", "familias", "empresarios"]
Money = Annotated[Decimal, Field(ge=0, le=1_000_000, decimal_places=2)]
Identifier = Annotated[str, Field(min_length=1, max_length=100)]


def money_input(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Use um valor monetário numérico, com no máximo 2 casas decimais.")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Valor monetário inválido.") from exc
    if not result.is_finite():
        raise ValueError("Valor monetário deve ser finito.")
    return result


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Period(Model):
    inicio: date = Field(strict=False, description="Data ISO YYYY-MM-DD, inclusiva.")
    fim: date = Field(strict=False, description="Data ISO YYYY-MM-DD, inclusiva.")

    @field_validator("inicio", "fim", mode="before")
    @classmethod
    def iso_dates_only(cls, value: Any) -> Any:
        if type(value) is date:
            return value
        if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise ValueError("PERIODO_INVALIDO: use datas ISO YYYY-MM-DD.")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("PERIODO_INVALIDO: data inexistente ou formato inválido.") from exc

    @model_validator(mode="after")
    def valid_period(self) -> "Period":
        if self.fim < self.inicio or self.days > 90:
            raise ValueError("PERIODO_INVALIDO: fim >= início e duração máxima de 90 dias.")
        if self.inicio.year < 2020 or self.fim.year > 2100:
            raise ValueError("PERIODO_INVALIDO: anos permitidos de 2020 a 2100.")
        return self

    @property
    def days(self) -> int:
        return (self.fim - self.inicio).days + 1


class Restrictions(Model):
    excluir_veiculos: list[Identifier] = Field(default_factory=list, max_length=100)
    faixa_horaria: Literal["manha", "tarde", "noite"] | None = None
    max_insercoes_por_veiculo: int | None = Field(default=None, ge=1, le=100_000)


class Briefing(Model):
    objetivo: str = Field(min_length=3, max_length=1000)
    publico: Segment
    mercados: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=1, max_length=3)
    orcamento: Annotated[Money, Field(gt=0)]
    periodo: Period
    canais: list[Channel] = Field(default_factory=lambda: ["radio", "tv"], min_length=1, max_length=2)
    restricoes: Restrictions = Field(default_factory=Restrictions)

    @field_validator("orcamento", mode="before")
    @classmethod
    def parse_money(cls, value: Any) -> Decimal:
        return money_input(value)

    @field_validator("mercados", "canais")
    @classmethod
    def no_duplicates(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Valores duplicados não são permitidos.")
        return value


class InventoryQuery(Model):
    mercados: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=1, max_length=3)
    periodo: Period
    canais: list[Channel] = Field(default_factory=lambda: ["radio", "tv"], min_length=1, max_length=2)
    publico: Segment | None = None
    restricoes: Restrictions = Field(default_factory=Restrictions)


class InventoryItem(Model):
    id: Identifier
    nome: str = Field(min_length=1, max_length=200)
    descricao: str = Field(max_length=2000)
    mercado: str = Field(min_length=1, max_length=80)
    canal: Channel
    faixa_horaria: Literal["manha", "tarde", "noite"]
    segmentos: list[Segment] = Field(min_length=1, max_length=5)
    custo_por_insercao: Annotated[Money, Field(gt=0)]
    capacidade_diaria: int = Field(ge=0, le=1000)
    impressoes_por_insercao: int | None = Field(default=None, ge=1, le=100_000_000)
    dados_simulados: Literal[True]

    @field_validator("custo_por_insercao", mode="before")
    @classmethod
    def parse_money(cls, value: Any) -> Decimal:
        return money_input(value)


class ErrorInfo(Model):
    codigo: str
    mensagem: str
    detalhes: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(Model):
    ok: bool
    aviso: Literal["DEMONSTRAÇÃO COM DADOS SIMULADOS"] = BANNER
    dados_simulados: Literal[True] = True
    dados: dict[str, Any] | None = None
    erro: ErrorInfo | None = None
