"""SQLite transacional: snapshots imutáveis, aprovações e criação idempotente."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4

from .models import BANNER
from .repositories import DomainError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def encode(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: dict) -> str:
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


class Storage:
    def __init__(self, path: str | Path, clock: Callable[[], datetime] = utcnow):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    simulation_id TEXT NOT NULL REFERENCES simulations(id),
                    alternative_id TEXT NOT NULL, simulation_hash TEXT NOT NULL,
                    explicit_confirmation INTEGER NOT NULL CHECK(explicit_confirmation = 1),
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    simulation_id TEXT NOT NULL REFERENCES simulations(id),
                    alternative_id TEXT NOT NULL,
                    approval_id TEXT NOT NULL REFERENCES approvals(id),
                    idempotency_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
                    created_at TEXT NOT NULL, UNIQUE(simulation_id, alternative_id)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id TEXT PRIMARY KEY, simulation_id TEXT NOT NULL REFERENCES simulations(id),
                    event TEXT NOT NULL, entity_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, details TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_simulation ON audit(simulation_id);
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def audit(self, conn: sqlite3.Connection, simulation_id: str, event: str, entity_id: str, details: dict) -> None:
        conn.execute("INSERT INTO audit VALUES (?, ?, ?, ?, ?, ?)", (
            str(uuid4()), simulation_id, event, entity_id, self.clock().isoformat(), encode(details),
        ))

    def save_simulation(self, result: dict) -> dict:
        simulation_id = str(uuid4())
        body = {**result, "simulation_id": simulation_id, "criada_em": self.clock().isoformat(), "aviso": BANNER, "dados_simulados": True}
        with self.connection() as conn:
            conn.execute("INSERT INTO simulations VALUES (?, ?, ?, ?)", (simulation_id, encode(body), digest(body), body["criada_em"]))
            self.audit(conn, simulation_id, "SIMULACAO_CRIADA", simulation_id, {"alternativas": [a["alternativa_id"] for a in result["alternativas"]]})
        return body

    @staticmethod
    def read_simulation(conn: sqlite3.Connection, simulation_id: str) -> tuple[dict, str]:
        row = conn.execute("SELECT * FROM simulations WHERE id = ?", (simulation_id,)).fetchone()
        if row is None:
            raise DomainError("SIMULACAO_INEXISTENTE", "Simulação não encontrada; execute simular_plano.")
        body = json.loads(row["body"])
        if digest(body) != row["sha256"]:
            raise DomainError("SIMULACAO_ALTERADA", "Integridade da simulação inválida; simule e aprove novamente.")
        return body, row["sha256"]

    @staticmethod
    def alternative(body: dict, alternative_id: str) -> dict:
        for item in body["alternativas"]:
            if item["alternativa_id"] == alternative_id:
                return item
        raise DomainError("ALTERNATIVA_INVALIDA", "Alternativa não pertence à simulação informada.")

    def approve(self, simulation_id: str, alternative_id: str, explicit: bool) -> dict:
        if explicit is not True:
            raise DomainError("CONFIRMACAO_OBRIGATORIA", "Obtenha confirmação humana explícita para a simulação e alternativa exatas.")
        approval_id = str(uuid4())
        now = self.clock()
        expires = now + timedelta(minutes=30)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            body, checksum = self.read_simulation(conn, simulation_id)
            self.alternative(body, alternative_id)
            conn.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?)", (
                approval_id, simulation_id, alternative_id, checksum, 1, now.isoformat(), expires.isoformat(),
            ))
            self.audit(conn, simulation_id, "APROVACAO_REGISTRADA", approval_id, {"alternativa_id": alternative_id})
        return {"approval_id": approval_id, "simulation_id": simulation_id, "alternativa_id": alternative_id,
                "criada_em": now.isoformat(), "expira_em": expires.isoformat(), "confirmacao_explicita": True}

    def create_plan(self, simulation_id: str, alternative_id: str, approval_id: str, idempotency_key: str) -> dict:
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key.strip()) <= 100:
            raise DomainError("CHAVE_INVALIDA", "Chave idempotente deve ter de 8 a 100 caracteres.")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM plans WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            if existing:
                expected = (simulation_id, alternative_id, approval_id)
                if expected != (existing["simulation_id"], existing["alternative_id"], existing["approval_id"]):
                    raise DomainError("CONFLITO_IDEMPOTENCIA", "Chave já utilizada com parâmetros diferentes; escolha outra chave.")
                return {**json.loads(existing["body"]), "reutilizado": True}
            body, checksum = self.read_simulation(conn, simulation_id)
            alternative = self.alternative(body, alternative_id)
            approval = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if approval is None:
                raise DomainError("APROVACAO_AUSENTE", "Aprovação não encontrada; peça confirmação e registre aprovação.")
            if (approval["simulation_id"], approval["alternative_id"]) != (simulation_id, alternative_id):
                raise DomainError("APROVACAO_INVALIDA", "Aprovação pertence a outra simulação ou alternativa.")
            if approval["simulation_hash"] != checksum:
                raise DomainError("APROVACAO_INVALIDA", "Simulação foi alterada desde a aprovação; simule e aprove novamente.")
            if datetime.fromisoformat(approval["expires_at"]) <= self.clock():
                raise DomainError("APROVACAO_EXPIRADA", "Aprovação expirou após 30 minutos; solicite nova confirmação.")
            if conn.execute("SELECT id FROM plans WHERE simulation_id = ? AND alternative_id = ?", (simulation_id, alternative_id)).fetchone():
                raise DomainError("PLANO_DUPLICADO", "Alternativa já registrada; repita a chave original ou consulte o plano existente.")
            plan_id = str(uuid4())
            now = self.clock().isoformat()
            plan = {"plan_id": plan_id, "simulation_id": simulation_id, "alternativa_id": alternative_id,
                    "approval_id": approval_id, "status": "RASCUNHO_APROVADO", "criado_em": now,
                    "briefing": body["briefing"], "alternativa": alternative,
                    "premissas": body["premissas"], "alertas": body["alertas"],
                    "aviso": BANNER, "dados_simulados": True}
            conn.execute("INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?)", (
                plan_id, simulation_id, alternative_id, approval_id, idempotency_key, encode(plan), now,
            ))
            self.audit(conn, simulation_id, "PLANO_CRIADO", plan_id, {"alternativa_id": alternative_id, "status": "RASCUNHO_APROVADO"})
            return {**plan, "reutilizado": False}

    def get_plan(self, plan_id: str) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if row is None:
                raise DomainError("PLANO_INEXISTENTE", "Plano não encontrado; verifique o plan_id.")
            events = conn.execute("SELECT * FROM audit WHERE simulation_id = ? ORDER BY created_at, rowid", (row["simulation_id"],)).fetchall()
            return {**json.loads(row["body"]), "auditoria": [
                {"id": event["id"], "evento": event["event"], "entidade_id": event["entity_id"],
                 "criado_em": event["created_at"], "detalhes": json.loads(event["details"])} for event in events
            ]}
