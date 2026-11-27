"""Tools for the support agent (Module 5B).
Each tool = a DECLARATION (name, description, JSON schema -> what the model sees)
          + a FUNCTION (what actually runs, with the real business rules)."""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import math
from functools import lru_cache

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore, storage
from google.genai import types

from shoppilot.agent.orders import ORDERS
from shoppilot.config import get_settings
from shoppilot.llm import embed

REFUND_WINDOW_DAYS = 30
APPROVAL_THRESHOLD_INR = 10_000


@lru_cache
def _db() -> firestore.Client:
    return firestore.Client(project=get_settings().project_id)


@lru_cache
def _gcs() -> storage.Client:
    return storage.Client(project=get_settings().project_id)


def _clean_id(order_id: str) -> str:
    return str(order_id).strip().lstrip("#")


# ---------------- tool functions ----------------
def get_order(order_id: str) -> dict:
    order = ORDERS.get(_clean_id(order_id))
    return order if order else {"error": f"order {order_id} not found"}


def get_ticket(ticket_id: str) -> dict:
    snap = _db().collection("tickets").document(ticket_id.strip()).get()
    if not snap.exists:
        return {"error": f"ticket {ticket_id} not found (it may still be processing)"}
    d = snap.to_dict()
    return {k: d.get(k) for k in ("ticket_id", "subject", "body", "category", "priority", "status", "summary")}


@lru_cache  # built once per process; Module 6 replaces this with a real vector database
def _policy_index() -> list[tuple[str, str, list[float]]]:
    bucket = _gcs().bucket(f"{get_settings().project_id}-policies")
    docs: list[tuple[str, str]] = []

    # 1. hand-written policies (Module 1)
    for blob in bucket.list_blobs(prefix="policies/"):
        if blob.name.endswith(".md"):
            docs.append((blob.name, blob.download_as_text()))

    # 2. ingested chunks (Module 4): only real policies, only the NEWEST version of each source
    latest: dict[str, tuple] = {}
    blobs = list(bucket.list_blobs(prefix="chunks/"))
    with ThreadPoolExecutor(max_workers=16) as pool:  # network-bound work, so threads help: 51 s -> ~5 s
        contents = list(pool.map(lambda b: b.download_as_text(), blobs))
    for blob, content in zip(blobs, contents):
        rows = [json.loads(line) for line in content.splitlines() if line.strip()]
        if not rows or "/policies/" not in rows[0]["source"]:
            continue  # skip bulk/ test data and manual/ copies
        src = rows[0]["source"]
        if src not in latest or blob.updated > latest[src][0]:
            latest[src] = (blob.updated, rows)
    for _, rows in latest.values():
        docs += [(r["source"], r["text"]) for r in rows]

    vectors = embed([text for _, text in docs], task_type="RETRIEVAL_DOCUMENT")
    return [(src, text, vec) for (src, text), vec in zip(docs, vectors)]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def search_policies(query: str, top_k: int = 3) -> dict:
    q = embed([query], task_type="RETRIEVAL_QUERY")[0]  # queries and documents are embedded differently
    scored = sorted(((_cosine(q, v), src, text) for src, text, v in _policy_index()), reverse=True)
    return {"results": [{"score": round(s, 3), "source": src, "text": text}
                        for s, src, text in scored[: max(1, min(int(top_k), 5))]]}


def create_refund_request(order_id: str, reason: str) -> dict:
    """ALL business rules are enforced HERE, in code. The model cannot bypass them."""
    order = ORDERS.get(_clean_id(order_id))
    if not order:
        return {"error": f"order {order_id} not found"}
    if order["status"] != "delivered":
        return {"refund_allowed": False, "reason": f"order is '{order['status']}'; refunds are possible only after delivery"}

    days = (dt.date.today() - dt.date.fromisoformat(order["delivered_on"])).days
    if days > REFUND_WINDOW_DAYS:
        return {"refund_allowed": False,
                "reason": f"delivered {days} days ago; refund window is {REFUND_WINDOW_DAYS} days"}

    amount = order["total_inr"]  # from the system of record - NEVER an amount suggested by the model
    status = "pending_manager_approval" if amount > APPROVAL_THRESHOLD_INR else "approved"

    ref = _db().collection("refund_requests").document(order["order_id"])  # one per order = idempotent
    try:
        ref.create({"order_id": order["order_id"], "amount_inr": amount, "reason": reason,
                    "status": status, "created_at": dt.datetime.now(dt.UTC)})
    except AlreadyExists:
        existing = ref.get().to_dict()
        return {"already_requested": True, "status": existing["status"], "amount_inr": existing["amount_inr"]}

    return {"refund_request_created": True, "status": status, "amount_inr": amount,
            "note": "a manager must approve refunds above ₹10,000" if status != "approved"
                    else "refund will reach the original payment method in 5-7 business days"}


# ---------------- declarations (what the model sees) ----------------
DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_order",
        description="Look up an order by its order number. Returns items, total amount (INR), status and delivery date.",
        parameters_json_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order number, digits only, e.g. 48213"}},
            "required": ["order_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_ticket",
        description="Look up an existing support ticket by its id (format T-xxxxxxxx).",
        parameters_json_schema={
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    ),
    types.FunctionDeclaration(
        name="search_policies",
        description="Semantic search over ShopPilot's official policies (refunds, returns, shipping). "
                    "Use for ANY question about rules, windows, fees or timelines.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, in natural language"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Results to return (default 3)"},
            },
            "required": ["query"],
        },
    ),
    types.FunctionDeclaration(
        name="create_refund_request",
        description="Create a refund request for a delivered order. Enforces the refund window and approval rules. "
                    "Only call after confirming the order and the customer's reason.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string", "description": "Customer's reason, in a short sentence"},
            },
            "required": ["order_id", "reason"],
        },
    ),
]
TOOLS = types.Tool(function_declarations=DECLARATIONS)

REGISTRY = {
    "get_order": get_order,
    "get_ticket": get_ticket,
    "search_policies": search_policies,
    "create_refund_request": create_refund_request,
}


def execute(name: str, args: dict) -> dict:
    """Run a tool safely. Errors are RETURNED to the model (so it can recover), never raised."""
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"unknown tool '{name}'"}
    try:
        return fn(**args)
    except TypeError as e:  # wrong/missing arguments
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # tool crashed
        return {"error": f"{name} failed: {e}"}
