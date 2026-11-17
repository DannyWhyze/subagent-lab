from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain_ollama import ChatOllama
from weather_subagent import create_weather_subagent

model = ChatOllama(model="qwen3.5:latest")
backend = StateBackend()

agent = create_deep_agent(
    name="deep_supervisor",
    model=model,
    backend=backend,
    system_prompt=(
        "You are a supervisor agent. When asked about weather, "
        "use the task tool to delegate the query to the weather subagent."
    ),
    subagents=[
        create_weather_subagent(model),
    ],
)
