import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from ummix_mcp.repositories import DomainError
from ummix_mcp.storage import Storage, digest


@pytest.fixture
def simulated(service, briefing):
    result = service.simulate(briefing)
    return result["simulation_id"], result["alternativas"][0]["alternativa_id"], result["alternativas"][1]["alternativa_id"]


def test_cannot_create_without_approval(service, simulated):
    sim, alt, _ = simulated
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, alt, "ausente", "chave-teste-1")
    assert error.value.code == "APROVACAO_AUSENTE"


@pytest.mark.parametrize("confirmation", [False, "sim", "true", 1, None])
def test_explicit_boolean_required(service, simulated, confirmation):
    with pytest.raises(DomainError) as error:
        service.storage.approve(simulated[0], simulated[1], confirmation)
    assert error.value.code == "CONFIRMACAO_OBRIGATORIA"


def test_wrong_alternative_approval(service, simulated):
    sim, alt, other = simulated
    approval = service.storage.approve(sim, alt, True)
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, other, approval["approval_id"], "chave-teste-2")
    assert error.value.code == "APROVACAO_INVALIDA"


def test_wrong_simulation_approval(service, simulated, briefing):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    second = service.simulate(briefing)
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(second["simulation_id"], alt, approval["approval_id"], "chave-teste-3")
    assert error.value.code == "APROVACAO_INVALIDA"


def test_expiry_at_exact_boundary(service, simulated):
    sim, alt, _ = simulated
    now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    service.storage.clock = lambda: now
    approval = service.storage.approve(sim, alt, True)
    service.storage.clock = lambda: now + timedelta(minutes=30)
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, alt, approval["approval_id"], "chave-expirada")
    assert error.value.code == "APROVACAO_EXPIRADA"


def test_idempotence_survives_expiry_and_restart(service, simulated):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    args = sim, alt, approval["approval_id"], "chave-estavel"
    first = service.storage.create_plan(*args)
    second = Storage(service.storage.path, clock=lambda: datetime.now(timezone.utc) + timedelta(days=2)).create_plan(*args)
    assert first["plan_id"] == second["plan_id"]
    assert first["reutilizado"] is False and second["reutilizado"] is True
    recovered = Storage(service.storage.path).get_plan(first["plan_id"])
    assert recovered["status"] == "RASCUNHO_APROVADO"
    assert [event["evento"] for event in recovered["auditoria"]] == ["SIMULACAO_CRIADA", "APROVACAO_REGISTRADA", "PLANO_CRIADO"]


def test_concurrent_idempotency(service, simulated):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    def create(_):
        return service.storage.create_plan(sim, alt, approval["approval_id"], "chave-concorrente")
    with ThreadPoolExecutor(max_workers=4) as pool:
        plans = list(pool.map(create, range(8)))
    assert len({plan["plan_id"] for plan in plans}) == 1
    assert sum(not plan["reutilizado"] for plan in plans) == 1
    with service.storage.connection() as conn:
        assert conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 1


def test_duplicate_with_new_key(service, simulated):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    service.storage.create_plan(sim, alt, approval["approval_id"], "primeira-chave")
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, alt, approval["approval_id"], "segunda-chave")
    assert error.value.code == "PLANO_DUPLICADO"


def test_same_key_different_request(service, simulated):
    sim, alt, other = simulated
    approval = service.storage.approve(sim, alt, True)
    service.storage.create_plan(sim, alt, approval["approval_id"], "mesma-chave-123")
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, other, approval["approval_id"], "mesma-chave-123")
    assert error.value.code == "CONFLITO_IDEMPOTENCIA"


@pytest.mark.parametrize("rewrite_hash", [False, True])
def test_tampering_invalidates_approval(service, simulated, rewrite_hash):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    with service.storage.connection() as conn:
        row = conn.execute("SELECT body FROM simulations WHERE id = ?", (sim,)).fetchone()
        body = json.loads(row[0])
        body["briefing"]["objetivo"] = "Objetivo alterado"
        conn.execute("UPDATE simulations SET body = ? WHERE id = ?", (json.dumps(body), sim))
        if rewrite_hash:
            conn.execute("UPDATE simulations SET sha256 = ? WHERE id = ?", (digest(body), sim))
    with pytest.raises(DomainError) as error:
        service.storage.create_plan(sim, alt, approval["approval_id"], "chave-alterada")
    assert error.value.code == ("APROVACAO_INVALIDA" if rewrite_hash else "SIMULACAO_ALTERADA")


def test_unknown_simulation_and_alternative(service, simulated):
    with pytest.raises(DomainError) as error:
        service.storage.approve("ausente", "eficiencia", True)
    assert error.value.code == "SIMULACAO_INEXISTENTE"
    with pytest.raises(DomainError) as error:
        service.storage.approve(simulated[0], "inexistente", True)
    assert error.value.code == "ALTERNATIVA_INVALIDA"


def test_unknown_plan_and_sql_injection_are_inert(service):
    with pytest.raises(DomainError) as error:
        service.storage.get_plan("'; DROP TABLE plans; --")
    assert error.value.code == "PLANO_INEXISTENTE"
    with service.storage.connection() as conn:
        assert conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_approval_and_simulation_persist_before_creation(service, simulated):
    sim, alt, _ = simulated
    approval = service.storage.approve(sim, alt, True)
    restarted = Storage(service.storage.path)
    plan = restarted.create_plan(sim, alt, approval["approval_id"], "chave-reinicio")
    assert restarted.get_plan(plan["plan_id"])["simulation_id"] == sim
