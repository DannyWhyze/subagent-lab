from langchain.agents import create_agent
from deepagents.backends import StateBackend
from deepagents.middleware.subagents import SubAgentMiddleware
from langchain_ollama import ChatOllama
from weather_subagent import create_weather_subagent

model = ChatOllama(model="qwen3.5:latest")
backend = StateBackend()

agent = create_agent(
    model=model,
    system_prompt="You are a supervisor agent. When asked about weather, use the task tool to delegate the query to the weather subagent.",
    middleware=[
        SubAgentMiddleware(
            backend=backend,
            subagents=[
                # {
                #     "name": "weather",
                #     "description": "This subagent can get weather in cities.",
                #     "system_prompt": "Use the get_weather tool to get the weather in a city.",
                #     "tools": [get_weather],
                #     "model": model,
                #     "middleware": [],
                # }
                create_weather_subagent(model),
            ],
        )
    ],
)
