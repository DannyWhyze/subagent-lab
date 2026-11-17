# Microsoft Agent Framework round-robin 8-persona debate

## 1. Overview
This pattern implements a cyclic discussion across 8 cultural perspectives using Microsoft Agent Framework (`agent-framework-orchestrations`). It runs locally against Ollama via `OllamaCompatibleOpenAIChatClient`.

A modulo selection function determines speaker progression without requiring a coordinator LLM, keeping latency low and execution predictable.

---

## 2. Architecture and topology

```mermaid
flowchart LR
    Start([User Topic]) --> Farmer["Farmer (SE Asia)"]
    Farmer --> Developer["Developer (USA)"]
    Developer --> Teacher["Teacher (E Europe)"]
    Teacher --> Activist["Activist (S America)"]
    Activist --> Spiritual["SpiritualLeader (Middle East)"]
    Spiritual --> Artist["Artist (Africa)"]
    Artist --> Immigrant["Immigrant (Asia/Canada)"]
    Immigrant --> Doctor["Doctor (Scandinavia)"]
    Doctor --> Termination{"max_rounds reached"}
    Termination -- Yes --> Done([Completed])
```

---

## 3. Package structure

- **`personas.py`**: Defines the 8 cultural perspectives using Microsoft Agent Framework `Agent` instances.
- **`orchestration.py`**: Compiles `GroupChatBuilder` with `round_robin_selection`.
- **`runner.py`**: Streaming adapter inheriting from `BaseAgentRunner`. Consumes `workflow.run(prompt, stream=True)` events and emits SSE stream updates.
