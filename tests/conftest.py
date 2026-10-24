import json
from copy import deepcopy
from importlib.resources import files

import pytest

from ummix_mcp.demo import DEMO_BRIEFING
from ummix_mcp.models import Briefing
from ummix_mcp.repositories import MockInventoryRepository
from ummix_mcp.service import UmmixService
from ummix_mcp.storage import Storage


@pytest.fixture
def raw_briefing():
    return deepcopy(DEMO_BRIEFING)


@pytest.fixture
def briefing(raw_briefing):
    return Briefing.model_validate(raw_briefing)


@pytest.fixture
def inventory():
    return MockInventoryRepository()


@pytest.fixture
def service(tmp_path, inventory):
    return UmmixService(inventory, Storage(tmp_path / "test.sqlite3"))


@pytest.fixture
def seed_factory(tmp_path):
    original = json.loads(files("ummix_mcp").joinpath("data/mock_inventory.json").read_text(encoding="utf-8"))

    def create(transform):
        payload = deepcopy(original)
        transform(payload)
        path = tmp_path / "inventory.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return MockInventoryRepository(path)
    return create
