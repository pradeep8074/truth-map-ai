import json
import uuid
import datetime
from fastapi import APIRouter, HTTPException
from backend.database import get_db
from backend.models import (
    DecisionContractModel,
    RequirementModel,
    EvidenceRequirementModel,
    ConstraintModel,
    AssumptionModel,
    UnresolvedQuestionModel,
    ContractUpdateRequest,
)
from backend.services.contract_compiler import compile_decision_contract

router = APIRouter(prefix="/api/investigations/{investigation_id}/contract", tags=["contracts"])


def load_contract_from_db(conn, contract_id: str) -> DecisionContractModel:
    """Helper to assemble a full DecisionContractModel from relational tables."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM decision_contracts WHERE id = ?", (contract_id,))
    c_row = cursor.fetchone()
    if not c_row:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    # 1. Load Requirements
    cursor.execute("""
        SELECT * FROM contract_requirements
        WHERE contract_id = ?
        ORDER BY sort_order ASC
    """, (contract_id,))
    req_rows = cursor.fetchall()

    requirements: list[RequirementModel] = []
    all_evidence_reqs: list[EvidenceRequirementModel] = []

    for r in req_rows:
        req_id = r["id"]
        # Load evidence requirements for this requirement
        cursor.execute("SELECT * FROM contract_evidence_requirements WHERE requirement_id = ?", (req_id,))
        ev_rows = cursor.fetchall()
        
        evidence_list = []
        for ev in ev_rows:
            pref_sources = json.loads(ev["preferred_source_types"]) if ev["preferred_source_types"] else []
            ev_model = EvidenceRequirementModel(
                evidence_requirement_id=ev["id"],
                requirement_id=ev["requirement_id"],
                evidence_type=ev["evidence_type"],
                rationale=ev["rationale"],
                preferred_source_types=pref_sources,
                temporal_scope=ev["temporal_scope"],
                geographic_scope=ev["geographic_scope"],
            )
            evidence_list.append(ev_model)
            all_evidence_reqs.append(ev_model)

        requirements.append(
            RequirementModel(
                requirement_id=r["id"],
                title=r["title"],
                description=r["description"],
                requirement_type=r["requirement_type"],
                priority=r["priority"],
                verification_criteria=r["verification_criteria"],
                status=r["status"],
                evidence_needed=evidence_list,
            )
        )

    # 2. Load Constraints
    cursor.execute("SELECT * FROM contract_constraints WHERE contract_id = ?", (contract_id,))
    const_rows = cursor.fetchall()
    constraints = [
        ConstraintModel(
            constraint_id=c["id"],
            description=c["description"],
            constraint_type=c["constraint_type"],
        )
        for c in const_rows
    ]

    # 3. Load Assumptions
    cursor.execute("SELECT * FROM contract_assumptions WHERE contract_id = ?", (contract_id,))
    assump_rows = cursor.fetchall()
    assumptions = [
        AssumptionModel(
            assumption_id=a["id"],
            description=a["description"],
            confidence=a["confidence"],
            source=a["source"] if "source" in a.keys() and a["source"] else "ai_inferred",
            validation_status=a["validation_status"],
        )
        for a in assump_rows
    ]

    # 4. Load Unresolved Questions
    cursor.execute("SELECT * FROM contract_unresolved_questions WHERE contract_id = ?", (contract_id,))
    unres_rows = cursor.fetchall()
    unresolved = [
        UnresolvedQuestionModel(
            question_id=u["id"],
            question=u["question"],
            clarification_type=u["clarification_type"],
            dimension=u["dimension"],
        )
        for u in unres_rows
    ]

    comp_method = c_row["compilation_method"] or ""
    processing_mode = "gemini" if "gemini" in comp_method.lower() else "fallback"

    return DecisionContractModel(
        contract_id=c_row["id"],
        investigation_id=c_row["investigation_id"],
        original_question=c_row["original_question"],
        normalized_question=c_row["normalized_question"],
        decision_objective=c_row["decision_objective"],
        scope=c_row["scope"],
        compilation_method=comp_method,
        processing_mode=processing_mode,
        created_at=c_row["created_at"],
        updated_at=c_row["updated_at"],
        requirements=requirements,
        evidence_requirements=all_evidence_reqs,
        constraints=constraints,
        assumptions=assumptions,
        unresolved_questions=unresolved,
    )


def save_compiled_contract(conn, compiled: dict) -> DecisionContractModel:
    """Saves a compiled contract into SQLite, deleting any prior contract for this investigation."""
    cursor = conn.cursor()
    inv_id = compiled["investigation_id"]

    # Delete existing contract if present (foreign keys cascade will clear sub-tables)
    cursor.execute("DELETE FROM decision_contracts WHERE investigation_id = ?", (inv_id,))

    # Insert root contract
    cursor.execute("""
        INSERT INTO decision_contracts (
            id, investigation_id, original_question, normalized_question,
            decision_objective, scope, compilation_method, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        compiled["contract_id"],
        compiled["investigation_id"],
        compiled["original_question"],
        compiled["normalized_question"],
        compiled["decision_objective"],
        compiled.get("scope"),
        compiled["compilation_method"],
        compiled["created_at"],
        compiled["updated_at"],
    ))

    # Insert Requirements and nested Evidence Requirements
    for sort_idx, r in enumerate(compiled.get("requirements", [])):
        cursor.execute("""
            INSERT INTO contract_requirements (
                id, contract_id, title, description, requirement_type,
                priority, verification_criteria, status, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["requirement_id"],
            compiled["contract_id"],
            r["title"],
            r["description"],
            r["requirement_type"],
            r["priority"],
            r["verification_criteria"],
            r.get("status", "unverified"),
            sort_idx,
        ))

        for ev in r.get("evidence_needed", []):
            pref_sources_json = json.dumps(ev.get("preferred_source_types", []))
            cursor.execute("""
                INSERT INTO contract_evidence_requirements (
                    id, requirement_id, contract_id, evidence_type,
                    rationale, preferred_source_types, temporal_scope, geographic_scope
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ev["evidence_requirement_id"],
                r["requirement_id"],
                compiled["contract_id"],
                ev["evidence_type"],
                ev["rationale"],
                pref_sources_json,
                ev.get("temporal_scope"),
                ev.get("geographic_scope"),
            ))

    # Insert Constraints
    for c in compiled.get("constraints", []):
        cursor.execute("""
            INSERT INTO contract_constraints (id, contract_id, description, constraint_type)
            VALUES (?, ?, ?, ?)
        """, (
            c["constraint_id"],
            compiled["contract_id"],
            c["description"],
            c["constraint_type"],
        ))

    # Insert Assumptions
    for a in compiled.get("assumptions", []):
        cursor.execute("""
            INSERT INTO contract_assumptions (id, contract_id, description, confidence, source, validation_status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            a["assumption_id"],
            compiled["contract_id"],
            a["description"],
            a.get("confidence", 0.8),
            a.get("source", "ai_inferred"),
            a.get("validation_status", "pending"),
        ))

    # Insert Unresolved Questions
    for u in compiled.get("unresolved_questions", []):
        cursor.execute("""
            INSERT INTO contract_unresolved_questions (id, contract_id, question, clarification_type, dimension)
            VALUES (?, ?, ?, ?, ?)
        """, (
            u["question_id"],
            compiled["contract_id"],
            u["question"],
            u["clarification_type"],
            u["dimension"],
        ))

    conn.commit()
    return load_contract_from_db(conn, compiled["contract_id"])


@router.post("/compile", response_model=DecisionContractModel, status_code=201)
async def compile_contract_endpoint(investigation_id: str):
    """
    Compiles a structured Decision Contract from the investigation's research question.
    Saves to SQLite and returns the complete contract model.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT research_question FROM investigations WHERE id = ?", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
        research_question = row["research_question"]

        compiled_dict = await compile_decision_contract(investigation_id, research_question)
        contract = save_compiled_contract(conn, compiled_dict)
        return contract


@router.get("", response_model=DecisionContractModel)
async def get_contract_endpoint(investigation_id: str):
    """Retrieves the current Decision Contract for the investigation."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM decision_contracts WHERE investigation_id = ?", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Decision contract has not yet been compiled for investigation '{investigation_id}'."
            )
        return load_contract_from_db(conn, row["id"])


@router.patch("", response_model=DecisionContractModel)
async def update_contract_endpoint(investigation_id: str, payload: ContractUpdateRequest):
    """Updates user-edited fields of an existing decision contract."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM decision_contracts WHERE investigation_id = ?", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No decision contract exists to update for investigation '{investigation_id}'."
            )
        contract_id = row["id"]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Update root fields
        if payload.decision_objective is not None or payload.scope is not None:
            cursor.execute("""
                UPDATE decision_contracts
                SET decision_objective = COALESCE(?, decision_objective),
                    scope = COALESCE(?, scope),
                    updated_at = ?
                WHERE id = ?
            """, (payload.decision_objective, payload.scope, now, contract_id))

        # Update Requirements if provided
        if payload.requirements is not None:
            # Delete old requirements
            cursor.execute("DELETE FROM contract_requirements WHERE contract_id = ?", (contract_id,))
            for sort_idx, r in enumerate(payload.requirements):
                cursor.execute("""
                    INSERT INTO contract_requirements (
                        id, contract_id, title, description, requirement_type,
                        priority, verification_criteria, status, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.requirement_id or str(uuid.uuid4()),
                    contract_id,
                    r.title,
                    r.description,
                    r.requirement_type,
                    r.priority,
                    r.verification_criteria,
                    r.status,
                    sort_idx,
                ))

                for ev in r.evidence_needed:
                    cursor.execute("""
                        INSERT INTO contract_evidence_requirements (
                            id, requirement_id, contract_id, evidence_type,
                            rationale, preferred_source_types, temporal_scope, geographic_scope
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ev.evidence_requirement_id or str(uuid.uuid4()),
                        r.requirement_id,
                        contract_id,
                        ev.evidence_type,
                        ev.rationale,
                        json.dumps(ev.preferred_source_types),
                        ev.temporal_scope,
                        ev.geographic_scope,
                    ))

        # Update Constraints if provided
        if payload.constraints is not None:
            cursor.execute("DELETE FROM contract_constraints WHERE contract_id = ?", (contract_id,))
            for c in payload.constraints:
                cursor.execute("""
                    INSERT INTO contract_constraints (id, contract_id, description, constraint_type)
                    VALUES (?, ?, ?, ?)
                """, (
                    c.constraint_id or str(uuid.uuid4()),
                    contract_id,
                    c.description,
                    c.constraint_type,
                ))

        # Update Assumptions if provided
        if payload.assumptions is not None:
            cursor.execute("DELETE FROM contract_assumptions WHERE contract_id = ?", (contract_id,))
            for a in payload.assumptions:
                cursor.execute("""
                    INSERT INTO contract_assumptions (id, contract_id, description, confidence, source, validation_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    a.assumption_id or str(uuid.uuid4()),
                    contract_id,
                    a.description,
                    a.confidence,
                    a.source if hasattr(a, "source") and a.source else "user_provided",
                    a.validation_status,
                ))

        # Update Unresolved Questions if provided
        if payload.unresolved_questions is not None:
            cursor.execute("DELETE FROM contract_unresolved_questions WHERE contract_id = ?", (contract_id,))
            for u in payload.unresolved_questions:
                cursor.execute("""
                    INSERT INTO contract_unresolved_questions (id, contract_id, question, clarification_type, dimension)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    u.question_id or str(uuid.uuid4()),
                    contract_id,
                    u.question,
                    u.clarification_type,
                    u.dimension,
                ))

        conn.commit()
        return load_contract_from_db(conn, contract_id)


@router.post("/recompile", response_model=DecisionContractModel)
async def recompile_contract_endpoint(investigation_id: str):
    """
    Recompiles the decision contract using the investigation's current research question,
    updating the contract in place.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT research_question FROM investigations WHERE id = ?", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
        research_question = row["research_question"]

        compiled_dict = await compile_decision_contract(investigation_id, research_question)
        contract = save_compiled_contract(conn, compiled_dict)
        return contract
