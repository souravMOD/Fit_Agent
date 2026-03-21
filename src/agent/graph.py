from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from src.config import OLLAMA_BASE_URL, LLM_MODEL, LLM_TEMPERATURE
from src.tools.agent_tools import (
    analyze_and_log_meal,
    get_daily_summary,
    get_weekly_history,
    check_goals,
)

tools = [analyze_and_log_meal, get_daily_summary, get_weekly_history, check_goals]

# The LLM that powers the agent
llm = ChatOpenAI(
    base_url=OLLAMA_BASE_URL,
    model=LLM_MODEL,
    temperature=LLM_TEMPERATURE,
    api_key="not-needed",
).bind_tools(tools)


SYSTEM_PROMPT = """You are FitAgent, a personal fitness and nutrition assistant.

Your capabilities:
1. Analyze meal photos to estimate calories and macros
2. Log meals to track daily nutrition
3. Show daily summaries and weekly trends
4. Check progress against personal goals
5. Give helpful nutrition advice

Rules:
- When a user sends a meal image, ALWAYS analyze it first, then log it
- After logging, check their daily goals and give brief feedback
- Be encouraging but honest about nutrition
- Keep responses concise and friendly
- Use metric units (grams, kcal)

The current user's ID is provided in each message."""


def agent_node(state: MessagesState):
    """The agent: reads messages, decides what to do."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_graph():
    """
    Build the LangGraph agent.

    The graph has 2 nodes:
    - agent: LLM thinks and picks tools (or responds)
    - tools: executes whatever tool the agent chose

    And 1 conditional edge:
    - After agent: if it picked a tool → go to tools node
    - After agent: if it has the answer → go to END
    - After tools: always go back to agent (to think about the result)
    """
    graph = StateGraph(MessagesState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))

    # Add edges
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


# Build once, reuse
agent = build_graph()