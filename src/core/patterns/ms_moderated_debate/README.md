# Microsoft Agent Framework dynamic moderated 8-persona debate

## 1. Overview
This pattern implements a hub-and-spoke debate across 8 cultural perspectives using Microsoft Agent Framework `GroupChatBuilder`.

A centralized `Moderator` agent guides the discussion by selecting the next speaker based on prior arguments and produces a concluding synthesis at the end of the debate.

---

## 2. Architecture and topology

```mermaid
flowchart TD
    Start([User Topic]) --> Moderator["Moderator Agent"]
    Moderator --> SpeakerSelect{"Dynamic Speaker Selection"}
    SpeakerSelect --> Farmer["Farmer (SE Asia)"]
    SpeakerSelect --> Developer["Developer (USA)"]
    SpeakerSelect --> Teacher["Teacher (E Europe)"]
    SpeakerSelect --> Activist["Activist (S America)"]
    SpeakerSelect --> Spiritual["SpiritualLeader (Middle East)"]
    SpeakerSelect --> Artist["Artist (Africa)"]
    SpeakerSelect --> Immigrant["Immigrant (Asia/Canada)"]
    SpeakerSelect --> Doctor["Doctor (Scandinavia)"]
    Farmer --> Moderator
    Developer --> Moderator
    Teacher --> Moderator
    Activist --> Moderator
    Spiritual --> Moderator
    Artist --> Moderator
    Immigrant --> Moderator
    Doctor --> Moderator
    Moderator --> Synthesis["Final Synthesis"] --> Done([Completed])
```

---

## 3. Package structure

- **`personas.py`**: Defines the 8 cultural perspectives and the `create_moderator_agent` factory using Microsoft Agent Framework `Agent` instances.
- **`orchestration.py`**: Compiles `GroupChatBuilder` with dynamic `orchestrator_agent`.
- **`runner.py`**: Streaming adapter inheriting from `BaseAgentRunner`. Consumes `workflow.run(prompt, stream=True)` events and emits SSE stream updates.
