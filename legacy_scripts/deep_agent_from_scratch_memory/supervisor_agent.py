"""Supervisor agent with LangGraph InMemorySaver checkpointer and virtual filesystem."""

from file_tools import ls, read_file, write_file
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from research_subagent import research_subagent_spec
from research_tools import think_tool, web_search
from state import DeepAgentState
from task_tool import create_task_tool

# Ollama local model with reasoning off for deterministic and fast execution
model = ChatOllama(model="qwen3.5:latest", reasoning=False)

all_tools = [web_search, think_tool, ls, read_file, write_file]

task_tool = create_task_tool(
    tools=all_tools,
    subagents=[research_subagent_spec],
    model=model,
    state_schema=DeepAgentState,
)

supervisor_tools = [task_tool, ls, read_file, write_file, think_tool]

# LangGraph Checkpointer for multi-turn conversational memory & virtual state persistence
checkpointer = InMemorySaver()

agent = create_agent(
    name="supervisor",
    model=model,
    tools=supervisor_tools,
    system_prompt=(
        "You are an autonomous DeepAgent supervisor coordinating research workflows.\n"
        "Rules:\n"
        "1. Delegate research tasks to `research-agent` using `task` immediately.\n"
        "2. Do not emit conversational preamble, status updates, or intermediate commentary before or between tool calls. Call tools first without speaking.\n"
        "3. You have a virtual filesystem in your state. Inspect and manage it using `ls`, `read_file`, and `write_file`.\n"
        "4. Always execute tools sequentially one at a time.\n"
        "5. Synthesize the final answer clearly for the user only after all tool operations are complete."
    ),
    state_schema=DeepAgentState,
    checkpointer=checkpointer,
)
