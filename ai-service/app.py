import json
import os
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from fastapi import FastAPI
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DIR = BASE_DIR / ".chroma"


class HashEmbeddings(Embeddings):
    """Small deterministic embeddings for offline hackathon demos."""

    def __init__(self, size: int = 64):
        self.size = size

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.size
        for token in text.lower().replace("-", " ").replace("_", " ").split():
            vector[hash(token) % self.size] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class AnalyzeRequest(BaseModel):
    incident_id: str = "INC-1001"
    query: str = "Why are checkout payments failing?"


class IncidentSummary(BaseModel):
    incident_id: str
    severity: str
    root_cause: str
    confidence: float = Field(ge=0, le=1)
    impacted_services: List[str]
    evidence: List[str]
    recommended_actions: List[str]
    agent_trace: List[str]
    human_approval_required: bool


class RcaState(TypedDict, total=False):
    incident_id: str
    query: str
    alerts: List[Dict[str, Any]]
    logs: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]
    runbook_context: List[str]
    root_cause: str
    confidence: float
    evidence: List[str]
    actions: List[str]
    summary: Dict[str, Any]
    trace: List[str]


def load_logs() -> List[Dict[str, Any]]:
    return [json.loads(line) for line in (DATA_DIR / "logs.jsonl").read_text().splitlines()]


def load_json(name: str) -> List[Dict[str, Any]]:
    return json.loads((DATA_DIR / name).read_text())


def build_vector_store() -> Chroma:
    documents: List[Document] = []
    for row in load_logs():
        content = f"{row['timestamp']} {row['service']} {row['level']} {row['message']}"
        documents.append(Document(page_content=content, metadata={"source": "logs", "service": row["service"]}))
    documents.append(Document(page_content=(DATA_DIR / "runbooks.md").read_text(), metadata={"source": "runbook"}))
    return Chroma.from_documents(
        documents=documents,
        embedding=HashEmbeddings(),
        persist_directory=str(VECTOR_DIR),
        collection_name="incident_docs",
    )


vector_store = build_vector_store()
retriever = vector_store.as_retriever(search_kwargs={"k": 4})


@tool
def search_logs(query: str) -> List[Dict[str, Any]]:
    """Search production logs for services, errors, timeouts, or trace ids."""
    terms = query.lower().split()
    results = []
    for row in load_logs():
        haystack = json.dumps(row).lower()
        if any(term in haystack for term in terms):
            results.append(row)
    return results[:6]


@tool
def query_metrics(service: str) -> List[Dict[str, Any]]:
    """Return metrics for one service or all services."""
    metrics = load_json("metrics.json")
    if service.lower() == "all":
        return metrics
    return [row for row in metrics if row["service"] == service]


@tool
def lookup_alerts(incident_id: str) -> List[Dict[str, Any]]:
    """Look up alert payloads for an incident id."""
    return [row for row in load_json("alerts.json") if row["incident_id"] == incident_id]


@tool
def retrieve_runbook_context(query: str) -> List[str]:
    """Retrieve relevant runbook and log context using vector search."""
    return [doc.page_content for doc in retriever.invoke(query)]


def add_trace(state: RcaState, message: str) -> List[str]:
    return [*state.get("trace", []), message]


def alert_agent(state: RcaState) -> RcaState:
    alerts = lookup_alerts.invoke({"incident_id": state["incident_id"]})
    return {**state, "alerts": alerts, "trace": add_trace(state, "alert_agent used lookup_alerts")}


def log_agent(state: RcaState) -> RcaState:
    query = f"{state['query']} payment timeout 503 database pool exhausted"
    logs = search_logs.invoke({"query": query})
    return {**state, "logs": logs, "trace": add_trace(state, "log_agent used search_logs")}


def metric_agent(state: RcaState) -> RcaState:
    metrics = query_metrics.invoke({"service": "all"})
    return {**state, "metrics": metrics, "trace": add_trace(state, "metric_agent used query_metrics")}


def runbook_agent(state: RcaState) -> RcaState:
    context = retrieve_runbook_context.invoke({"query": "payment-service database pool exhausted checkout 503"})
    return {**state, "runbook_context": context, "trace": add_trace(state, "runbook_agent used retrieve_runbook_context")}


def root_cause_agent(state: RcaState) -> RcaState:
    logs = state.get("logs", [])
    metrics = state.get("metrics", [])
    pool_exhausted = any("pool exhausted" in row["message"].lower() for row in logs)
    high_db_pool = any(row["metric"] == "db_pool_usage_pct" and row["value"] > 95 for row in metrics)
    payment_timeouts = any("timeout" in row["message"].lower() for row in logs)

    if pool_exhausted and high_db_pool:
        root = "payment-service database connection pool exhaustion caused payment authorization timeouts, which made checkout-api return 503 errors."
        confidence = 0.91
    elif payment_timeouts:
        root = "payment-service upstream/provider timeouts are the strongest correlated signal behind checkout failures."
        confidence = 0.72
    else:
        root = "Insufficient evidence for a single root cause; payment-service remains the primary suspect."
        confidence = 0.55

    evidence = []
    for alert in state.get("alerts", []):
        evidence.append(f"Alert {alert['incident_id']} reported {alert['title']} on {alert['service']}.")
    for row in logs[:4]:
        evidence.append(f"{row['service']} {row['level']}: {row['message']}")
    for row in metrics:
        if row["value"] > 90 or row["metric"] in {"error_rate_pct", "provider_timeout_rate_pct"}:
            evidence.append(f"{row['service']} {row['metric']}={row['value']}")

    actions = [
        "Reduce payment retry concurrency to relieve pressure on the payment ledger database.",
        "Restart or scale payment-service instances one at a time after checking database capacity.",
        "Inspect recent payment-service deployment and slow ledger queries.",
        "Notify payments on-call and customer support about checkout failures.",
    ]

    return {
        **state,
        "root_cause": root,
        "confidence": confidence,
        "evidence": evidence[:8],
        "actions": actions,
        "trace": add_trace(state, "root_cause_agent correlated logs, alerts, metrics, and RAG context"),
    }


def summary_agent(state: RcaState) -> RcaState:
    alert = state.get("alerts", [{}])[0]
    impacted = sorted({row["service"] for row in state.get("logs", []) if row.get("level") in {"WARN", "ERROR"}})
    summary = IncidentSummary(
        incident_id=state["incident_id"],
        severity=alert.get("severity", "UNKNOWN"),
        root_cause=state["root_cause"],
        confidence=state["confidence"],
        impacted_services=impacted,
        evidence=state["evidence"],
        recommended_actions=state["actions"],
        agent_trace=add_trace(state, "summary_agent produced structured output"),
        human_approval_required=state["confidence"] < 0.7,
    )

    if os.getenv("OPENAI_API_KEY") and ChatOpenAI:
        parser = JsonOutputParser(pydantic_object=IncidentSummary)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Rewrite this RCA as concise JSON that matches the schema.\n{format_instructions}"),
                ("human", "{draft}"),
            ]
        )
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        chain = prompt | llm | parser
        refined = chain.invoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "draft": summary.model_dump_json(),
            }
        )
        return {**state, "summary": refined, "trace": summary.agent_trace}

    return {**state, "summary": summary.model_dump(), "trace": summary.agent_trace}


def build_graph():
    graph = StateGraph(RcaState)
    graph.add_node("alert_agent", alert_agent)
    graph.add_node("log_agent", log_agent)
    graph.add_node("metric_agent", metric_agent)
    graph.add_node("runbook_agent", runbook_agent)
    graph.add_node("root_cause_agent", root_cause_agent)
    graph.add_node("summary_agent", summary_agent)

    graph.set_entry_point("alert_agent")
    graph.add_edge("alert_agent", "log_agent")
    graph.add_edge("log_agent", "metric_agent")
    graph.add_edge("metric_agent", "runbook_agent")
    graph.add_edge("runbook_agent", "root_cause_agent")
    graph.add_edge("root_cause_agent", "summary_agent")
    graph.add_edge("summary_agent", END)
    return graph.compile()


app = FastAPI(title="Incident AI RCA Service")
rca_graph = build_graph()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "UP", "service": "incident-ai-service"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> Dict[str, Any]:
    state = rca_graph.invoke({"incident_id": request.incident_id, "query": request.query, "trace": []})
    return state["summary"]

