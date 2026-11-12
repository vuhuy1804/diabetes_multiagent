"""Static agent catalog from the course architecture PDF.

Phase 8 implements the seven required agents; RL remains optional.
"""

AGENT_CATALOG = (
    {"agent": "patient_data", "purpose": "Validate and normalize input features", "optional": False},
    {"agent": "dl_prediction", "purpose": "Run the actual trained DL model", "optional": False},
    {"agent": "rule_based", "purpose": "Apply explicit auditable rules", "optional": False},
    {"agent": "kg_rag", "purpose": "Retrieve grounded evidence from Neo4j / RAG", "optional": False},
    {"agent": "coordinator", "purpose": "Orchestrate and aggregate agent outputs", "optional": False},
    {"agent": "explanation", "purpose": "Prepare evidence-grounded report", "optional": False},
    {"agent": "monitoring", "purpose": "Record execution metadata and failures", "optional": False},
    {"agent": "rl", "purpose": "Optional policy experiments in synthetic simulation", "optional": True},
)
