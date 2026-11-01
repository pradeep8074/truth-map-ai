import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db, get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    """Initializes a fresh isolated SQLite database for each test run."""
    test_db = tmp_path / "test_truthmap_contracts.db"
    init_db(test_db)
    monkeypatch.setattr("backend.database.DB_PATH", test_db)
    monkeypatch.setattr("backend.routers.investigations.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.sources.get_db", lambda: get_db(test_db))
    monkeypatch.setattr("backend.routers.contracts.get_db", lambda: get_db(test_db))


def test_compile_get_update_recompile_contract():
    # 1. Create an investigation
    q = "Does this government scholarship programme improve access to higher education for rural students?"
    create_res = client.post("/api/investigations", json={"research_question": q})
    assert create_res.status_code == 201
    inv_id = create_res.json()["investigation_id"]

    # 2. Query contract before compile -> Expect 404
    get_before = client.get(f"/api/investigations/{inv_id}/contract")
    assert get_before.status_code == 404

    # 3. Compile decision contract
    compile_res = client.post(f"/api/investigations/{inv_id}/contract/compile")
    assert compile_res.status_code == 201
    contract = compile_res.json()

    assert contract["investigation_id"] == inv_id
    assert len(contract["decision_objective"]) > 10
    assert len(contract["requirements"]) >= 4
    assert len(contract["constraints"]) >= 1
    assert len(contract["assumptions"]) >= 1
    assert len(contract["unresolved_questions"]) >= 1
    contract_id = contract["contract_id"]

    # 4. GET compiled contract
    get_res = client.get(f"/api/investigations/{inv_id}/contract")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["contract_id"] == contract_id
    assert retrieved["decision_objective"] == contract["decision_objective"]
    assert len(retrieved["requirements"]) == len(contract["requirements"])

    # 5. PATCH contract: edit decision objective & add custom constraint
    patch_payload = {
        "decision_objective": "Customized Objective: Quantify rural enrollment impact in State X.",
        "scope": "Restricted to 2023-2025 cohorts in District Y",
    }
    patch_res = client.patch(f"/api/investigations/{inv_id}/contract", json=patch_payload)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["decision_objective"] == "Customized Objective: Quantify rural enrollment impact in State X."
    assert updated["scope"] == "Restricted to 2023-2025 cohorts in District Y"

    # 6. Recompile contract
    recompile_res = client.post(f"/api/investigations/{inv_id}/contract/recompile")
    assert recompile_res.status_code == 200
    recompiled = recompile_res.json()
    assert recompiled["investigation_id"] == inv_id
    assert len(recompiled["requirements"]) >= 4

    # 7. Check investigation details includes has_contract=True
    inv_res = client.get(f"/api/investigations/{inv_id}")
    assert inv_res.status_code == 200
    assert inv_res.json()["has_contract"] is True


def test_contract_invalid_investigation_id():
    bad_id = "non-existent-uuid"
    res = client.post(f"/api/investigations/{bad_id}/contract/compile")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    get_res = client.get(f"/api/investigations/{bad_id}/contract")
    assert get_res.status_code == 404
