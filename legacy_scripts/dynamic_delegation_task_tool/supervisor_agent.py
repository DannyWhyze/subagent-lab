from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from state import DeepAgentState
from task_tool import create_task_tool
from weather_subagent import weather_subagent_spec
from weather_tool import get_weather

model = ChatOllama(model="qwen3.5:latest")

task_tool = create_task_tool(
    tools=[get_weather],
    subagents=[weather_subagent_spec],
    model=model,
    state_schema=DeepAgentState,
)

agent = create_agent(
    name="supervisor",
    model=model,
    tools=[task_tool],
    system_prompt=(
        "You are a supervisor agent. When asked about weather, "
        "use the task tool to delegate the query to the weather subagent."
    ),
    state_schema=DeepAgentState,
)
