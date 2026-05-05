from typing import TypedDict, List, Any
from langgraph.graph import StateGraph, START, END

from app.agents.planner_agent import planner_agent
from app.agents.researcher_agent import researcher_agent
from app.agents.coder_agent import coder_agent
from app.agents.answer_agent import answer_agent
from app.agents.reviewer_agent import reviewer_agent


class AgentState(TypedDict):
    repo_id: str
    user_task: str
    review_enabled: bool
    plan: List[str]
    research_results: List[Any]
    code_suggestion: dict
    final_answer: dict
    review: dict


def should_review(state: AgentState):
    if state.get("review_enabled"):
        return "reviewer"
    return "end"


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)
    graph.add_node("researcher", researcher_agent)
    graph.add_node("coder", coder_agent)
    graph.add_node("answer", answer_agent)
    graph.add_node("reviewer", reviewer_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "coder")
    graph.add_edge("coder", "answer")

    graph.add_conditional_edges(
        "answer",
        should_review,
        {
            "reviewer": "reviewer",
            "end": END,
        },
    )

    graph.add_edge("reviewer", END)

    return graph.compile()