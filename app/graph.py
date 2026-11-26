# The answer flow as a LangGraph StateGraph (Week 5 S3, ADR-016). Same steps and same functions as the plain flow
# in app/generate.py; the graph makes the branches explicit and records which steps ran (graph_trace in the audit).
#
#   mask -> [kill switch on?] -> search_only -> END
#        -> route -> retrieve -> generate -> validate -> [pass]              -> finish -> END
#                                    ^                -> [blocking, 1st try] -> generate (retry with the problems)
#                                    |________________-> [blocking, 2nd try] -> refuse -> finish -> END
#
# route records which products and policy versions apply (product filter ADR-009, version by date ADR-010); the
# search itself still applies them, so retrieval is identical to the plain flow. S4 adds a clarify branch after route.
# run: PIPELINE=graph python -m app.generate     |  diagram: python -m app.graph  (prints Mermaid)
import datetime, time
from typing import Any, TypedDict
from langgraph.graph import StateGraph, START, END
from app import generate as gen
from app import product as prod, policy_versions as pv
from app.killswitch import kill_switch_on
from app.pii import mask
from app.search import search
from app.validate import validate, blocking

KILL_MESSAGE = "Answer generation is switched off (kill switch). Showing the matching rules and clauses only."

class State(TypedDict, total=False):
    # inputs
    question: str; k: int; caller: str; layers: tuple; product: str | None; as_on: Any
    # working state
    ctx: dict; route: dict; attempt: int; msg: Any; text: str; cites: list; usage: list; issues: list
    check: dict; t_model: float; trace: list
    # outputs
    result: tuple

def _step(state: State, name: str) -> list:
    return state.get("trace", []) + [name]

def n_mask(state: State) -> State:
    # Only checks that masking runs first; _prepare masks again (same function, same result) so both flows share
    # one implementation. The masked question is what every later step sees.
    masked, found = mask(state["question"])
    return {"trace": _step(state, "mask"), "route": {"pii_masked": found, "masked_question": masked}}

def after_mask(state: State) -> str:
    return "search_only" if kill_switch_on() else "route"

def n_search_only(state: State) -> State:
    q = state["route"]["masked_question"]
    found = search(q, state["k"], layers=state["layers"], product=state["product"], as_on=state["as_on"])
    rec = {"pipeline": "graph", "mode": "search_only", "question": q, "pii_masked": state["route"]["pii_masked"],
           "as_on": found["as_on"].isoformat(), "products": list(found["products"]),
           "product_source": found["product_source"], "rows": found["rows"], "notices": [KILL_MESSAGE] + found["notices"],
           "refused": None, "cost_usd": 0.0, "graph_trace": _step(state, "search_only")}
    return {"trace": rec["graph_trace"], "result": (KILL_MESSAGE, [], rec)}

def n_route(state: State) -> State:
    q = state["route"]["masked_question"]
    products, source = prod.resolve(q, state["product"])
    as_on = pv.to_date(state["as_on"]) if state["as_on"] else datetime.date.today()   # as app/search.py
    live = [p for p in products if pv.in_force(p, as_on)]
    return {"trace": _step(state, "route"),
            "route": {**state["route"], "products": list(products), "product_source": source, "in_force": live}}

def n_retrieve(state: State) -> State:
    ctx = gen._prepare(state["question"], state["k"], state["layers"], state["product"], state["as_on"])
    return {"trace": _step(state, "retrieve"), "ctx": ctx, "attempt": 0, "usage": [], "t_model": time.perf_counter()}

def n_generate(state: State) -> State:
    ctx, attempt = state["ctx"], state["attempt"] + 1
    note = blocking(state["issues"]) if attempt > 1 else None
    msg, text, cites = gen._ask(ctx["model"], ctx["results"], ctx["q"], ctx["hits"], retry_note=note)
    out = {"trace": _step(state, "generate"), "attempt": attempt, "msg": msg, "text": text, "cites": cites,
           "usage": state["usage"] + [msg.usage]}
    if attempt > 1:
        out["check"] = {**state["check"], "draft_1": state["text"]}
    return out

def n_validate(state: State) -> State:
    ctx = state["ctx"]
    issues = validate(state["text"], state["cites"], ctx["hits"], ctx["products"], ctx["as_on"], ctx["q"])
    if state["attempt"] == 1:
        check = {"mode": gen.VALIDATOR, "first": issues, "action": "pass" if not blocking(issues) else "flagged"}
    else:
        check = {**state["check"], "second": issues}
        if not blocking(issues):
            check["action"] = "passed_after_retry"
    return {"trace": _step(state, "validate"), "issues": issues, "check": check}

def after_validate(state: State) -> str:
    if not blocking(state["issues"]) or gen.VALIDATOR != "enforce":
        return "finish"
    return "generate" if state["attempt"] < 2 else "refuse"

def n_refuse(state: State) -> State:
    check = {**state["check"], "action": "refused_after_retry", "draft_2": state["text"]}
    return {"trace": _step(state, "refuse"), "check": check, "text": gen.REFUSAL, "cites": []}

def n_finish(state: State) -> State:
    trace = _step(state, "finish")
    model_ms = int((time.perf_counter() - state["t_model"]) * 1000)
    result = gen._finish(state["ctx"], state["caller"], state["msg"], state["text"], state["cites"], state["usage"],
                         state["check"], model_ms,
                         extra={"pipeline": "graph", "graph_trace": trace, "graph_route": state["route"]})
    return {"trace": trace, "result": result}

def build():
    g = StateGraph(State)
    for name, fn in [("mask", n_mask), ("search_only", n_search_only), ("route", n_route), ("retrieve", n_retrieve),
                     ("generate", n_generate), ("validate", n_validate), ("refuse", n_refuse), ("finish", n_finish)]:
        g.add_node(name, fn)
    g.add_edge(START, "mask")
    g.add_conditional_edges("mask", after_mask, {"search_only": "search_only", "route": "route"})
    g.add_edge("search_only", END)
    g.add_edge("route", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "validate")
    g.add_conditional_edges("validate", after_validate, {"finish": "finish", "generate": "generate", "refuse": "refuse"})
    g.add_edge("refuse", "finish")
    g.add_edge("finish", END)
    return g.compile()

_GRAPH = None
def run(q: str, k: int = 5, caller: str = "cli", layers=("policy", "rbi"), product: str | None = None, as_on=None):
    """Same signature and return value as app.generate.answer: (text, citations, audit record)."""
    global _GRAPH
    _GRAPH = _GRAPH or build()
    out = _GRAPH.invoke({"question": q, "k": k, "caller": caller, "layers": tuple(layers), "product": product,
                         "as_on": as_on, "trace": [], "issues": []})
    return out["result"]

if __name__ == "__main__":
    print(build().get_graph().draw_mermaid())
