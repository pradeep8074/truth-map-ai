import time
import sqlite3
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

sys.stdout.reconfigure(encoding='utf-8')
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db
import backend.database as db_module

client = TestClient(app)

def run_performance_benchmarks():
    test_db = "backend/data/perf_test.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    init_db(test_db)
    db_module.DB_PATH = test_db

    print("=== TRUTHMAP AI PERFORMANCE & LATENCY BENCHMARK ===")

    # 1. Database Query Latency
    t0 = time.perf_counter()
    with sqlite3.connect(test_db) as conn:
        for _ in range(100):
            conn.execute("SELECT 1;").fetchone()
    db_lat_ms = (time.perf_counter() - t0) * 10  # average over 100 queries in ms
    print(f"1. Database Raw SQLite Latency (avg of 100 queries): {db_lat_ms:.3f} ms")

    # 2. Investigation Creation Latency
    t0 = time.perf_counter()
    res_inv = client.post("/api/investigations", json={"research_question": "Does regional high-speed rail reduce carbon emissions in interstate transit corridors?"})
    inv_lat_ms = (time.perf_counter() - t0) * 1000
    inv_id = res_inv.json()["investigation_id"]
    print(f"2. Investigation Creation API Latency: {inv_lat_ms:.2f} ms")

    # Seed source and passages
    t0 = time.perf_counter()
    with sqlite3.connect(test_db) as conn:
        conn.execute(
            "INSERT INTO sources (id, investigation_id, source_type, title, publisher, content_hash, extraction_status, retrieved_at) "
            "VALUES ('src-perf-1', ?, 'document', 'Interstate Transit Carbon Baseline', 'DOT', 'hash-p1', 'completed', '2026-10-31T03:00:00Z');",
            (inv_id,)
        )
        conn.execute(
            "INSERT INTO passages (id, source_id, passage_text, sha256_hash) "
            "VALUES ('pas-p1', 'src-perf-1', 'Electric high speed rail reduces net passenger-mile emissions by 68 percent compared to regional air travel.', 'hash-pas-1'), "
            "       ('pas-p2', 'src-perf-1', 'Grid electricity source mix during peak evening hours increases effective rail emissions by 14 percent.', 'hash-pas-2');"
        )
        conn.execute(
            "INSERT INTO claims (id, investigation_id, source_id, passage_id, claim_text, category, extraction_method, extraction_confidence, created_at) "
            "VALUES ('clm-p1', ?, 'src-perf-1', 'pas-p1', 'Electric high speed rail reduces net passenger-mile emissions by 68 percent.', 'statistical', 'deterministic', 0.95, '2026-10-31T03:05:00Z'), "
            "       ('clm-p2', ?, 'src-perf-1', 'pas-p2', 'Grid electricity source mix during peak evening hours increases effective rail emissions by 14 percent.', 'statistical', 'deterministic', 0.90, '2026-10-31T03:06:00Z');",
            (inv_id, inv_id)
        )
        conn.commit()
    seed_ms = (time.perf_counter() - t0) * 1000
    print(f"3. Evidence Seed & Provenance Insert Duration: {seed_ms:.2f} ms")

    # 4. Decision Contract Compilation Duration
    t0 = time.perf_counter()
    res_comp = client.post(f"/api/investigations/{inv_id}/contract/compile")
    comp_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"4. Decision Contract Compilation Duration: {comp_lat_ms:.2f} ms (Status: {res_comp.status_code})")

    # 5. Graph Construction Duration
    t0 = time.perf_counter()
    res_graph = client.post(f"/api/investigations/{inv_id}/evidence-graph/analyze")
    graph_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"5. Evidence Dependency Graph Construction Duration: {graph_lat_ms:.2f} ms (Status: {res_graph.status_code})")

    # 6. Conflict Detection Duration
    t0 = time.perf_counter()
    res_conf = client.post(f"/api/investigations/{inv_id}/conflicts/analyze")
    conf_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"6. Evidence Conflict Analysis Duration: {conf_lat_ms:.2f} ms (Status: {res_conf.status_code})")

    # 7. Sufficiency & Gap Analysis Duration
    t0 = time.perf_counter()
    res_suff = client.post(f"/api/investigations/{inv_id}/sufficiency/analyze")
    suff_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"7. Evidence Sufficiency & Gap Analysis Duration: {suff_lat_ms:.2f} ms (Status: {res_suff.status_code})")

    # 8. Stress Testing Duration
    t0 = time.perf_counter()
    res_stress = client.post(f"/api/investigations/{inv_id}/stress-tests/generate")
    stress_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"8. Decision Stress Scenario Generation Duration: {stress_lat_ms:.2f} ms (Status: {res_stress.status_code})")

    # 9. Report Synthesis Duration (Deterministic / Fallback)
    t0 = time.perf_counter()
    res_rep = client.post(f"/api/investigations/{inv_id}/reports/generate")
    rep_lat_ms = (time.perf_counter() - t0) * 1000
    print(f"9. Decision Intelligence Report Synthesis Duration: {rep_lat_ms:.2f} ms (Status: {res_rep.status_code})")

    # Clean up perf test db
    try:
        if os.path.exists(test_db):
            os.remove(test_db)
    except Exception:
        pass
    print("=== BENCHMARK COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_performance_benchmarks()
