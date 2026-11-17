from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from file_tools import ls, read_file, write_file
from research_subagent import research_subagent_spec
from research_tools import think_tool, web_search
from state import DeepAgentState
from task_tool import create_task_tool

model = ChatOllama(model="qwen3.5:latest")

all_tools = [web_search, think_tool, ls, read_file, write_file]

task_tool = create_task_tool(
    tools=all_tools,
    subagents=[research_subagent_spec],
    model=model,
    state_schema=DeepAgentState,
)

supervisor_tools = [task_tool, ls, read_file, write_file, think_tool]

agent = create_agent(
    name="supervisor",
    model=model,
    tools=supervisor_tools,
    system_prompt=(
        "You are a supervisor coordinating research workflows.\n"
        "1. When asked to research a topic, delegate the task to the research-agent using the task tool.\n"
        "2. Instruct the subagent to save its findings to a file.\n"
        "3. You can verify and read saved files using ls and read_file.\n"
        "4. Always execute tool calls one at a time sequentially."
    ),
    state_schema=DeepAgentState,
)
