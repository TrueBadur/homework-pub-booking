# Ex5 — Edinburgh research loop scenario

## Your answer

The planner generated two subgoals for the loop executor session: sg_1 (find a Haymarket venue for 6 people) and sg_2 (create a flyer with the venue, weather, and cost details).

The execution proceeded in three turns:

Turn 1: Executed venue_search, get_weather, and calculate_cost concurrently. These read-only operations are marked parallel_safe.

Turn 2: Ran generate_flyer, which is not parallel_safe because it writes a file.

Turn 3: Finalized the process via complete_task.

During development, a dataflow integrity check flagged an issue in the flyer text. The template originally used a hardcoded rule threshold ("total under £300 threshold"), which inserted "£300" into the prose despite it not being returned by any data tool. Because £300 appeared contextually plausible, it likely would have bypassed manual review. To fix this and maintain data integrity, the text was simplified to: "No deposit required for this booking."

## Citations

- sessions/ex5-edinburgh-research/sess_*/logs/trace.jsonl — tool call sequence
- sessions/ex5-edinburgh-research/sess_*/workspace/flyer.md — the produced flyer
