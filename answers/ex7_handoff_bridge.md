# Ex7 — Handoff bridge

## Your answer

The HandoffBridge orchestrates the execution loop between the loop half and the structured half. In each round, the loop half runs, and if the next action requires a handoff to the structured half, the bridge creates a forward handoff file and invokes structured execution. Depending on the outcome, the bridge either marks the session as complete if the structured half confirms the booking, or it builds a reverse task to loop back if the structured half escalates.

The escalation path is particularly notable. Upon escalation, the bridge modifies the initial task into a dictionary containing the prior result, the rejection reason, and a retry flag. In a production environment with an LLM, this new executor invocation would prompt the model to generate a different subgoal. However, for the scripted offline demo, the retry choice is hardcoded to a specific venue and seat count to ensure the test remains deterministic.

System state and audit logging are managed at key transition points. Every half transition emits a state change event via the session trace. To ensure the process did actual work before reporting success, an integrity check verifies that the trace contains at least one round start, one state change, and one tool call. Additionally, rather than deleting old inter-process communication files during cleanup, the system moves stale handoff files into a dedicated log directory to preserve the audit trail.

## Citations

- starter/handoff_bridge/bridge.py — HandoffBridge.run + helpers
- starter/handoff_bridge/integrity.py — verify_dataflow
