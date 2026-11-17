from langchain.agents import create_agent
from subagent_as_tool import schedule_event, manage_email
from langchain_ollama import ChatOllama

model = ChatOllama(model="qwen3.5:latest")

SUPERVISOR_PROMPT = (
    "You are a helpful personal assistant. "
    "You can schedule calendar events and send emails. "
    "Break down user requests into appropriate tool calls and coordinate the results. "
    "When a request involves multiple actions, use multiple tools in sequence or in parallel as appropriate."
)

supervisor_agent = create_agent(
    model,
    tools=[schedule_event, manage_email],
    system_prompt=SUPERVISOR_PROMPT,
)