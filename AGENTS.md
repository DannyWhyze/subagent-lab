# AGENTS.md — Leitfaden für KI-Agenten in `subagent_lab`

Diese Datei dient als primäre Einstiegs- und Orientierungsdokumentation für jeden KI-Agenten, der in diesem Repository arbeitet.

---

## 1. Verbindliche Richtlinien & Speicher

Jeder Agent **muss** vor Beginn der Arbeit folgende Dokumente laden und deren Regeln strikt befolgen:

* **[`docs_dw/memories.md`](file:///docs_dw/memories.md):** Kontextuelle Erinnerungen, historische Vorfälle, Sicherheitsgrenzen und die vollständigen Betriebsgrundsätze.
* **[`docs_dw/rules.md`](file:///docs_dw/rules.md):** Die 47 mandatorischen Arbeitsregeln (u. a. Rücksprache vor Aktionen, keine eigenmächtigen Git-Commits, Anti-Nudging, Englisch nach außen / Deutsch nach innen).
* **[`docs_dw/ABOUT_DANNY.md`](file:///docs_dw/ABOUT_DANNY.md):** Arbeitsweise, Präferenzen und technischer Hintergrund von Danny.
* **[`docs_dw/JOURNAL_1.md`](file:///docs_dw/JOURNAL_1.md):** Das aktuelle Arbeitsjournal. Vor Beginn lesen und nach signifikanten Änderungen lückenlos nachführen.

---

## 2. Projektüberblick & Scope

* **Ziel:** Systematischer Vergleich, Benchmarking und Prototyping verschiedener Subagenten-Architekturen im LangChain/LangGraph- und Microsoft-Agent-Ökosystem:
  1. *Subagent-as-Tool* (gekapselt in `@tool`, optional mit Human-in-the-Loop)
  2. *Prebuilt SubAgentMiddleware* (`deepagents.middleware.subagents`)
  3. *Dynamic Delegation / Task Meta-Tool* (kontext-isolierte Agenten)
  4. *Autonomous DeepAgent* (virtuelles Dateisystem, Sandboxing)
  5. *Microsoft Agent Framework* (`agent.as_tool()` für Caller-Callee-Isolation, `HandoffBuilder` für Peer-Mesh, `GroupChatBuilder` für Diskurse)
* **Kapselungs-Prinzip (Mesh vs. Hierarchie):**
  - *Mesh / Handoff:* Permanenter Kontrollwechsel (Staffellauf) mit vollständiger Übergabe des Verlaufs an den nächsten Agenten.
  - *Hierarchie / Subagent:* Echte Caller-Callee-Kapselung (`as_tool()` mit `propagate_session=False` oder isoliertes Task-Tool). Der Subagent arbeitet in einer privaten Sandbox und liefert nur das Endergebnis an den Aufrufer zurück.
* **Status:** Aktuelle Experimente liegen in `legacy_scripts/`. Der produktive Aufbau erfolgt schrittweise in `src/`.
* **Code-Lifecycle:** Explorative Prototypen und isolierte Machbarkeitsnachweise werden in `legacy_scripts/` entwickelt und verifiziert. Erst nach erfolgreicher empirischer Validierung erfolgt die modulare, testbare Überführung in das Produktiv-Framework unter `src/`.

---

## 3. Technische Systemumgebung & Konventionen

* **Betriebssystem & Loop:** Windows 10/11. Für asynchrone Skripte ist der `WindowsProactorEventLoopPolicy` zwingend erforderlich.
* **Windows Console Encoding:** Bei Skripten mit Modell-Streaming auf Windows-Konsolen ist `sys.stdout.reconfigure(encoding="utf-8")` zwingend einzubinden, um `UnicodeEncodeError` (`cp1252`) bei Sonderzeichen und Emojis zu verhindern.
* **Paket- & Umgebungsmanager:** Ausschließlich `uv` in der lokalen virtuellen Umgebung (`.venv`).
* **LLM-Inferenz & Framework-Entkopplung:** Lokale Ollama-Instanz (Standard: `qwen3.5:latest`).
  * *Wichtig:* Bei lokalen Modellen stets sequentielle Tool-Ausführung in den Prompts erzwingen, da parallele Tool-Calls zu JSON-Verkettungsfehlern führen können.
  * *Fremd-Frameworks & Endpoints:* Bei Integration von Drittanbieter-Frameworks (z. B. Microsoft Agent Framework) nicht provider-spezifische Wrapper mit strengen Versions-Pins nutzen (wie `agent-framework-ollama`), sondern den standardisierten OpenAI-kompatiblen Port (`http://localhost:11434/v1` via `OpenAIChatClient`). Dies schützt vor `pip`/`uv`-Abhängigkeitskollisionen mit `langchain-ollama`.
* **Multi-Agent-Orchestrierung auf lokalen Modellen:** Bei Multi-Agent-Diskussionen oder sequentiellen Abläufen (z. B. `GroupChatBuilder`) sind deterministische Selektionsfunktionen (`GroupChatState` mit Modulo Round-Robin) separaten LLM-Moderatoren vorzuziehen. Dies eliminiert Token-Overhead, Latenz und Ausführungsfehler (wie leere Message-Caches bei Sprecher-Wiederholungen).
* **ChatML- & Multi-Agent Dialog-Turn Konvention:** Lokale Chat-Modelle (Ollama mit Qwen/Llama ChatML-Templates) brechen bei Multi-Agent-Diskussionen sofort mit leeren Strings (`text=""`, EOS-Token) ab, wenn die übergebene Nachrichten-Historie mit `role="assistant"` endet. In Multi-Agenten-Gruppenchats müssen vorangegangene Beiträge fremder Assistenten daher als eingehende Nutzer-Dialogbeiträge (`role="user"` mit Autoren-Präfix `"[Author]: "`) serialisiert werden (Nutzung von `OllamaCompatibleOpenAIChatClient` aus `src/core/patterns/common/ms_client.py`).
* **Deterministische State-Guardrails für Subagenten:** Bei formalen Regeln und Zustandsautomaten (z. B. Schachspiel, Buchungs-Workflows) darf das LLM niemals den Zustand oder erlaubte Aktionen aus dem internen Gedächtnis halluzinieren. Der aktuelle Zustand (z. B. FEN) und die Liste aller legalen Optionen müssen stets deterministisch aus einer Python-Engine (z. B. `python-chess`) injiziert werden. Jede Modellauswahl muss vor der Zustandsänderung validiert und bei Fehlschlägen mit Feedback-Retries und sicherem Fallback abgefangen werden.
* **Deterministische Tool-Fallbacks:** Externe Werkzeuge (wie Web-Suche) müssen immer einen lokalen Mock-Fallback besitzen und Umgebungsvariablen (`.env`) dynamisch laden, damit Testläufe und Benchmarks auch ohne externe API-Keys (z. B. `TAVILY_API_KEY`) offline und fehlerfrei funktionieren.
* **Dateistruktur- & Speicherort-Disziplin:** Neue Experimente, Spikes und Portierungen gehören ausnahmslos in entsprechende dedizierte Unterordner von `legacy_scripts/` (z. B. `legacy_scripts/langgraph_round_robin_debate/`) und dürfen niemals direkt im Projekt-Root oder in künstlich nummerierten Sammelordnern (`01_`, `02_`) abgelegt werden. Jedes Paradigma besitzt sein eigenes Verzeichnis.
* **Explizite LangGraph Graph-Topologie & Builder-Transparenz:** In LangGraph-Workflows dürfen Kanten und Routing-Entscheidungen nicht in Node-Closures oder undurchsichtigen Hilfsfunktionen versteckt werden. Die Topologie muss im Graph Builder (`StateGraph`) vollständig und transparent deklariert sein (`START`, `builder.add_node`, `builder.add_edge`, `builder.add_conditional_edges`).
* **Moderne Content-Block & Multi-Modal Text-Normalisierung:** Moderne Chat-Modelle und Wrapper (`langchain_ollama`, Anthropic, OpenAI) liefern Antworten standardmäßig als strukturierte Content-Block-Listen (`response.content = [{'type': 'text', 'text': ...}, ...]`). Vor der Weitergabe an String-Formatierer (wie ChatML Dialog-Turn Sanitizing `[Author]: Content`), Log-Ausgaben oder Transkripte müssen Nachrichteninhalte zwingend über eine Normalisierungsfunktion (`_extract_text`) in reinen Text überführt werden, um zu verhindern, dass rohe Python-Dictionary-Syntax (`[{'type': 'text', ...}]`) als Prompt-Kontext injiziert wird.
* **Single-GPU Inferenz-Sequenzierung (VRAM-Disziplin):** Auf lokalen Single-GPU-Systemen (RTX 5070 Ti) darf niemals mehr als ein Inferenz-Prozess gleichzeitig gestartet werden. Vor jedem Lauf ist sicherzustellen, dass keine Hintergrund-Tasks oder parallelen Python-Instanzen laufen, um VRAM-Paging in den System-RAM und Ausführungs-Timeouts zu verhindern.
* **Streaming-Protokoll & Reasoning-Entkopplung:** LangGraph `v3` Streaming (`stream_events(..., version="v3")`).
  * *Hinweis zu Tool-Calls:* `ToolCallStream`-Objekte werden bei `tool-started` ausgeliefert. Um das finale `output` zu lesen, muss der Channel vorab konsumiert werden (`for delta in item: pass`).
  * *LangGraph v3 Reasoning:* Liefert Denk-Tokens über den dedizierten Generator `item.reasoning` und die finale Antwort über `item.text`. Gedanken dürfen niemals manuell per RegEx aus Antwortblöcken geparst werden.
  * *Microsoft Agent Framework Streaming:* Trennt Denkprozesse strikt auf Typsystem-Ebene: `update.text` liefert ausschließlich sichtbaren Antworttext (`Content.type == "text"`). Reasoning-Tokens müssen aus `update.contents` anhand von `content.type == "text_reasoning"` ausgelesen werden.
* **Ollama `reasoning_effort` Translation Layer:** Ollamas OpenAI-kompatibler Port (`http://localhost:11434/v1`) unterstützt den Parameter `reasoning_effort` (`"none"`, `"low"`, `"medium"`, `"high"`) und übersetzt diesen intern in das Token-Budget für Reasoning-fähige lokale Modelle (wie `qwen3.5:latest` oder `deepseek-r1`). Um den Denkprozess bei lokalen Modellen vollständig abzuschalten, muss explizit `reasoning_effort="none"` (Microsoft/OpenAI) bzw. `reasoning=False` / `think=False` (LangChain/Native) übergeben werden; Auslassung führt zum Standard-Thinking.
* **Namensraum-Disziplin:** Alle Agenten müssen bei `create_agent` explizite Namen (`name="supervisor"`, `name="subagent_name"`) erhalten, um Token-Leaks über `lc_agent_name` in Streaming-Pipelines zu verhindern.
* **Sandboxing-Grenzziehung (Lokal vs. Server):** In-Process AST-Sandboxes (`LocalPythonExecutor`, `ASTSandbox`) sind ausschließlich für lokale Prototypen, CLI-Tools und Single-User-Umgebungen zugelassen (< 1 ms Latenz). Auf Produktions- und Multi-Tenant-Servern ist für fremden oder generierten Modell-Code zwingend echte Kernel- und Prozess-Isolation (Podman / Docker / E2B) vorgeschrieben, um DoS-, OOM-Kills und Shared-Memory-Lecks auszuschließen.
* **`smolagents` Integration für lokale Modelle:** Bei Nutzung von `smolagents` gegen lokale Endpoints ist `OpenAIServerModel(model_id="qwen3.5:latest", api_base="http://localhost:11434/v1", api_key="ollama")` einzusetzen. Um unkontrolliertes Thinking bei Modellen wie Qwen 3.5 zu unterbinden, muss `extra_body={"reasoning_effort": "none"}` übergeben werden.
* **LangGraph v3 Synchronous Stream Yield-Disziplin:** LangGraph v3 `.interleave("messages", "tool_calls")` ist ein synchroner Iterator (`GraphRunStream`). Wird er innerhalb eines asynchronen FastAPI-Tasks in eine `asyncio.Queue` gespeist, muss nach jedem `await queue.put(event)` zwingend ein kooperativer Yield (`await asyncio.sleep(0)`) erfolgen. Andernfalls hungert der synchrone Generator den asyncio-Event-Loop aus, wodurch FastAPI alle SSE-Tokens gepuffert in einem einzigen Block (statt Token-für-Token) ausliefert.
* **Microsoft Agent GroupChat Sprecher-Extraktion:** In GroupChat-Workflows (`GroupChatBuilder`) liefert der Stream `WorkflowEvent`-Objekte, die kein `author_name` besitzen. Der aktive Sprecher darf niemals über `event.author_name` oder `data.response_id` (bei Ollama stets `None`) abgefragt werden, sondern muss zwingend aus `event.data.author_name` (bei `intermediate`) bzw. `event.data.participant_name` (bei `group_chat`) extrahiert werden, um Sprecher-Zusammenlegungen im Frontend zu verhindern.
* **Microsoft Agent Streaming Text-Duplikations-Schutz:** Microsoft Agent Framework sendet nach den Inkrement-Deltas (`merge_mode="append"`) am Ende jedes Turns einen Abschluss-Chunk (`ResponseTextDoneEvent`) mit dem vollen Text und `merge_mode="replace"`. Um Text-Verdopplungen im Stream zu verhindern, dürfen Text-Tokens nur emittiert werden, wenn `merge_mode != "replace"` ist.
* **Globale UI-Control Parität & Pattern-Gating:** Wenn ein Pattern bestimmte globale UI-Features nicht unterstützt (z. B. `ms_chess` nutzt schnelle Prompt-Gedanken `<thought>` statt Reasoning-Tokens), muss das entsprechende UI-Element (`thinkingSelect`) im Frontend deterministisch deaktiviert (`disabled = true` mit Tooltip) und beim Wechsel zu unterstützten Mustern reaktiviert werden, um Verwirrung über wirkungslose Schalter auszuschließen.
* **Idempotente REST-Initialisierung für UI-Widgets:** GET-Endpunkte für zustandsbehaftete Frontend-Komponenten (wie `/api/chess/state`) dürfen für neue oder uninitialisierte `session_id`s niemals `404 Not Found` werfen, sondern müssen den gültigen Anfangszustand (z. B. Initial-Board mit 200 OK und legalen Zügen) selbsterklärend erzeugen.
* **Thought-Konsolidierung & Tool-Container-Begrenzung:** Wenn ein Agent vor und nach Tool-Aufrufen denkt, müssen die Fragmente im Frontend in einer einzigen, konsolidierten Thinking-Box weitergeführt werden (`commitActiveThought`). Tool- und Subagenten-Events sind im CSS zwingend auf maximale Höhen (`max-height: 180px` mit `overflow-y: auto`) zu begrenzen, um Layout-Sprünge bei massiven Payloads zu verhindern.

---

## 4. Arbeitsweise für Agenten (Kernregeln)

1. **Rücksprache & Gitvorschlag (Regel 1 & 32):** Keine Git-Commits, Staging, Package-Installationen (`uv add`) oder Datei-Löschungen ohne explizites Ja. Auf „Gitvorschlag“ ausschließlich Commit-Message und betroffene Dateien ausgeben; niemals fragen „Soll ich committen?“.
2. **Sprachgrenze (Regel 4):** Code, Docstrings, Kommentare, Spezifikationen und `README.md` strictly auf Englisch. Gespräche mit Danny, Journale und Notizen (`docs_dw/`) auf Deutsch.
3. **Punktgenauigkeit & Anti-Overdelivering (Regel 7):** Exakt den Auftrag ausführen. Nach Architekturentscheidungen keine Alternativ-Buffets anbieten, sondern direkt und fokussiert umsetzen.
4. **Empirischer Beweiszwang & Zero Unproven Code (Regel 44 & 46):** Kein Code gilt als fertig ohne lokalen Laufzeittest (`uv run python ...` mit Exit-Code 0). Ein Exit-Code 0 ist bei Multi-Agent- und Streaming-Pipelines jedoch kein hinreichender Beweis: Es muss immer explizit verifiziert werden, dass alle erwarteten Akteure tatsächlich Tokens/Inhalte erzeugt haben (`assert len(speakers_seen) == expected_count`), um stumme Template-Abbrüche oder übersprungene Runden auszuschließen. Nach jedem Teil-Task sofort testen und Fehler isolieren.
5. **Ursachenbehebung (Regel 3 & 16):** Keine stummen Exceptions (`try/except: pass`). Fehlerursachen (wie leere Kontext-Caches oder parallele Tool-Call-Fehler) an der Wurzel lösen.
6. **Async-Disziplin im Event-Loop (Regel 24):** Niemals synchrone Blocker in asynchronen Multi-Agent-Pipelines nutzen (`asyncio.sleep` statt `time.sleep`, asynchrone HTTP-Clients für Netzwerk-I/O).
7. **Signatur-Parität für Benchmarks (Regel 37):** Standard-Werkzeuge (wie `get_weather`) müssen framework-übergreifend exakt identische Signaturen und deterministische Rückgaben aufweisen.
8. **UI-Entwickler-Labels ohne Emojis (Regel 22 - wichtig für kommendes Frontend):** Deko-Emojis in Buttons, Badges, Tabs und Aktions-Labels (`[Delete]`, `[Clear Parsed]`) sind strikt verboten. Rein sachliche Entwickler-Beschriftung.
9. **Ende-zu-Ende Asynchronitäts- & UI-Verifikation (Regel 47):** Bei Frontend- und Streaming-Features reicht kein oberflächlicher Unit-Test. Die gesamte Kette (`[Trigger]` -> `[API]` -> `[Background-Task]` -> `[Stream/SSE]` -> `[DOM-Update]`) muss gedanklich und empirisch verifiziert werden (keine verlorenen F5-States, saubere Client-Persistenz).
10. **Quellcode vor Doku & Namensraum-Disziplin:** Bei Unstimmigkeiten stets die installierte Signatur in `Lib/site-packages` prüfen.
11. **Dokumentations-Disziplin (Regel 11, 27 & 39):** `legacy_scripts/README.md` und `docs_dw/JOURNAL_1.md` nach signifikanten Fortschritten proaktiv nachführen; `AGENTS.md` nur auf explizite Rückfrage. Keine Erwähnung von `docs_dw/` in Commit-Messages!
