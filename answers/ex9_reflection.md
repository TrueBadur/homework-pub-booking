# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

During the Ex7 run (session sess_a382a2149fc1), the planner allocated subgoal sg_2 ("commit the booking under policy rules") to the structured half. This routing was triggered because the task text explicitly included the deterministic phrase "under policy rules." The framework's DefaultPlanner evaluates subgoals against a prompt detailing the role of each half; when it detects terms related to policies, rules, or constraints, it naturally routes the task to the structured half.

However, this planning decision is merely advisory rather than an enforced constraint. The orchestrator can only execute this handoff because both halves are actively implemented and connected. If the architecture only included a loop half, a subgoal routed to a structured half would simply disappear into a void, illustrating failure mode #4 from the course material.

The broader takeaway is that relying on prose interpretation for architectural routing introduces vulnerability. To remove this ambiguity entirely, policy rules should be hardcoded directly into the structured half's Python logic rather than relying on the LLM's interpretation of task text.

### Citation

- sessions/ex7-handoff-bridge/sess_7f81b6b4ec7a/logs/tickets/tk_*/raw_output.json
- sessions/ex7-handoff-bridge/sess_7f81b6b4ec7a/logs/trace.jsonl:23

---

## Q2 — Dataflow integrity catch

### Your answer

In the development phase of Ex5, the automated integrity check flagged a fabricated detail that easily evaded manual review. Inside session sess_de44a1b8eb12, the generated flyer stated "Total: £560" and "Deposit: £112." Because these figures closely aligned with the mathematical formulas found in catering.json, they appeared highly plausible upon a quick human glance.

However, verify_dataflow failed the run (ok=False) and isolated £560 and £112 as unverified facts. Cross-referencing the execution trace revealed that calculate_cost had actually returned a total_gbp of 540 and a deposit of 0, as the actual cost fell beneath the threshold requiring a deposit. The LLM had simply hallucinated realistic-looking numbers that a human reviewer would likely miss without manual cross-checking.

The integrity check succeeded because it validates outputs against factual records in _TOOL_CALL_LOG rather than analyzing contextual plausibility. This highlights a valuable testing principle: to verify an automated validator's effectiveness against human oversight, insert a blatantly incorrect value (like £9999) to ensure the system flags it.

### Citation

- sessions/ex5-edinburgh-research/sess_0251533c5660/workspace/flyer.md:12
- sessions/ex5-edinburgh-research/sess_0251533c5660/logs/trace.jsonl:15

---

## Q3 — Removing one framework primitive

### Your answer

If forced to strip down the framework, I would protect session directories (Decision 1) above all else and reconstruct the remaining components around them. While the forward-only state machine (Decision 2) is vital, it depends heavily on isolated directories to remain robust. Tickets (Decision 3) could be substituted with standard .jsonl files nested inside a session, and atomic-rename IPC (Decision 5) could be swapped for basic directory polling.

Isolated session directories provide an irreplaceable structural baseline. Removing them introduces severe risks like cross-tenant data leaks and forces developers to reconstruct system states by piecing together fragmented application logs. Debugging an active session state would devolve into database archaeology rather than reading local files. Much like Git commits serve as the foundational building blocks from which tools like merge and diff are built, session directories serve as the fundamental commits of this architecture.

### Citation

- sessions/sess_de44a1b8eb12/ — the directory itself
- sessions/sess_a382a2149fc1/logs/trace.jsonl
