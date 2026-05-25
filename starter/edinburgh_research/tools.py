"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from sovereign_agent import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from .integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by area, party size, and budget.

    If results are found, choose one and proceed to get_weather.
    If no results are found, try a different 'near' area.

    IMPORTANT: If you have already found a suitable venue in previous calls,
    STOP searching and proceed to calculate_cost. Do NOT spiral.
    """
    try:
        with open(_SAMPLE_DATA / "venues.json") as f:
            venues = json.load(f)
    except FileNotFoundError:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "venues.json fixture is missing") from None

    previous_calls = [r for r in _TOOL_CALL_LOG if r.tool_name == "venue_search"]
    search_count = len(previous_calls)
    if search_count >= 3:
        # Build a useful message listing venues already found to prevent spiralling
        found_venues = []
        for call in previous_calls:
            if call.output.get("results"):
                found_venues.extend([v.get("id") for v in call.output["results"]])

        useful_message = f"Venues already identified: {list(set(found_venues))}" if found_venues else "No venues found in previous areas."

        return ToolResult(
            success=False,
            output={"error": "too_many_searches", "count": search_count, "previous_results": found_venues},
            summary=f"STOP calling venue_search. Use the results you already have. {useful_message}.",
        )

    results = []
    near_lower = near.lower()
    for v in venues:
        if not v.get("open_now"):
            continue
        if near_lower not in v.get("area", "").lower():
            continue
        if v.get("seats_available_evening", 0) < party_size:
            continue

        cost_floor = v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0)
        if cost_floor > budget_max_gbp:
            continue

        results.append(v)

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }
    record_tool_call("venue_search", {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"venue_search({near}, party={party_size}): {len(results)} result(s)"
    )


def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for `city` on `date` (YYYY-MM-DD).

    This function reads the fixture file ``sample_data/weather.json`` and
    returns a ToolResult describing the weather for the requested city and
    date. City matching is case-insensitive.

    Args:
        city: City name to look up (e.g. "Edinburgh"). Matching is
            case-insensitive.
        date: Date string in ISO format (YYYY-MM-DD) to look up.

    Returns:
        ToolResult: On success (found city and date) returns success=True and
        output containing the keys ``city`` (lowercased), ``date``,
        ``condition`` and ``temperature_c``. If the city or date is not found
        returns success=False with a helpful summary and empty output.

    Raises:
        ToolError: If the weather fixture file is missing (SA_TOOL_DEPENDENCY_MISSING).

    Example:
        >>> get_weather("Edinburgh", "2026-04-25")
    """
    try:
        with open(_SAMPLE_DATA / "weather.json") as f:
            weather_data = json.load(f)
    except FileNotFoundError:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "weather.json fixture is missing") from None

    city_key = city.lower()
    city_weather = weather_data.get(city_key)
    if not city_weather:
        return ToolResult(success=False, summary=f"City '{city}' not found in weather data", output={})

    day_weather = city_weather.get(date)
    if not day_weather:
        return ToolResult(success=False, summary=f"Date '{date}' not found for city '{city}'", output={})

    output = {
        "city": city_key,
        "date": date,
        "condition": day_weather.get("condition"),
        "temperature_c": day_weather.get("temperature_c"),
    }
    record_tool_call("get_weather", {"city": city_key, "date": date}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"get_weather({city_key}, {date}): {output['condition']}, {output['temperature_c']}C."
    )

def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking and return a ToolResult.

    The function reads two fixtures from ``sample_data/``:
      - ``catering.json`` — contains base rates per catering tier, venue
        modifiers and service charge percent.
      - ``venues.json`` — contains venue metadata (hire fee, min spend).

    Calculation summary:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers.get(venue_id, 1.0)
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * (service_charge_percent / 100)
      total         = subtotal + service + (hire_fee_gbp + min_spend_gbp)

    Deposit rules (applied to `total`):
      - total < 300          -> deposit 0
      - 300 < total < 1000   -> deposit 10% of total
      - total >= 1000        -> deposit 20% of total

    Args:
        venue_id: The venue identifier (must match an entry in venues.json).
        party_size: Number of guests.
        duration_hours: Number of hours the booking lasts (treated as at least 1).
        catering_tier: One of the tiers defined in the catering fixture
            (default: "bar_snacks").

    Returns:
        ToolResult with success=True and output containing:
          - venue_id, party_size, duration_hours, catering_tier
          - subtotal_gbp (int), service_gbp (int), total_gbp (int)
          - deposit_required_gbp (int)

        If the venue_id is unknown or catering_tier invalid, returns
        success=False and an explanatory summary with empty output.

    Raises:
        ToolError: If either fixture file is missing (SA_TOOL_DEPENDENCY_MISSING).

    Notes:
        This function MUST call ``record_tool_call(...)`` before returning so
        the grader can verify tool usage and outputs.

    Example:
        >>> calculate_cost("haymarket_tap", 6, 3)
    """
    try:
        with open(_SAMPLE_DATA / "catering.json") as f:
            cat = json.load(f)
        with open(_SAMPLE_DATA / "venues.json") as f:
            venues = json.load(f)
    except FileNotFoundError as e:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"Missing fixture: {e.filename}") from e

    venue = next((v for v in venues if v["id"] == venue_id), None)
    if not venue:
        return ToolResult(success=False, summary=f"Unknown venue_id: {venue_id}", output={})

    if catering_tier not in cat["base_rates_gbp_per_head"]:
        return ToolResult(success=False, summary=f"Invalid catering_tier: {catering_tier}", output={})

    base_per_head = cat["base_rates_gbp_per_head"][catering_tier]
    venue_mult = cat["venue_modifiers"].get(venue_id, 1.0)

    subtotal = base_per_head * venue_mult * party_size * max(1, duration_hours)
    service = subtotal * (cat["service_charge_percent"] / 100)

    venue_floor = venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)
    total = subtotal + service + venue_floor

    if total < 300:
        deposit = 0
    elif 300 < total < 1000:
        deposit = total * 0.1
    else:
        deposit = total * 0.2

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": int(subtotal),
        "service_gbp": int(service),
        "total_gbp": int(total),
        "deposit_required_gbp": int(deposit),
    }
    record_tool_call("calculate_cost", {"venue_id": venue_id, "party_size": party_size, "duration_hours": duration_hours, "catering_tier": catering_tier}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"calculate_cost({venue_id}, {party_size}): total £{output['total_gbp']}, deposit £{output['deposit_required_gbp']}. Now call generate_flyer with these details."
    )


def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ccc; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; }}
            dl {{ display: grid; grid-template-columns: 1fr 2fr; }}
            dt {{ font-weight: bold; }}
            .cost {{ font-size: 1.2em; font-weight: bold; color: #e67e22; }}
        </style>
    </head>
    <body>
        <article>
            <h1>Event Flyer: <span data-testid="venue_name">{venue_name}</span></h1>
            <p><strong>Location:</strong> <span data-testid="venue_address">{venue_address}</span></p>

            <section>
                <h2>Event Details</h2>
                <dl>
                    <dt>Date:</dt><dd data-testid="date">{date}</dd>
                    <dt>Time:</dt><dd data-testid="time">{time}</dd>
                    <dt>Party Size:</dt><dd data-testid="party_size">{party_size}</dd>
                </dl>
            </section>

            <section>
                <h2>Weather Forecast</h2>
                <p>Expect <span data-testid="condition">{condition}</span> conditions with a temperature of <span data-testid="temperature_c">{temperature_c}</span>&deg;C.</p>
            </section>

            <section>
                <h2>Cost Breakdown</h2>
                <p class="cost">Total: &pound;<span data-testid="total_gbp">{total_gbp}</span></p>
                <p>Deposit Required: &pound;<span data-testid="deposit_required_gbp">{deposit_required_gbp}</span></p>
            </section>
        </article>
    </body>
    </html>
    """

    # Ensure all required fields exist for the template to avoid KeyError
    defaults = {
        "venue_name": "N/A",
        "venue_address": "N/A",
        "date": "N/A",
        "time": "N/A",
        "party_size": "N/A",
        "condition": "N/A",
        "temperature_c": "N/A",
        "total_gbp": "0",
        "deposit_required_gbp": "0",
    }
    merged_details = {**defaults, **event_details}
    content = html_template.format(**merged_details)
    path = session.workspace_dir / "flyer.html"
    path.write_text(content)

    output = {"path": "workspace/flyer.html", "bytes_written": len(content)}
    record_tool_call("generate_flyer", {"event_details": event_details}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote {output['path']} ({len(content)} chars). Task nearly complete; now call complete_task."
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description=inspect.getdoc(venue_search),
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description=inspect.getdoc(get_weather),
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description=inspect.getdoc(calculate_cost),
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description=inspect.getdoc(generate_flyer),
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
