"""Tokens, traces, and consolidated cost for one hunt.

Tracks real response usage from both Jev and the Chat LLM (Strands Agent).
Model pricing is dynamically resolved based on model IDs and environment overrides,
rather than a single hardcoded constant.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any

# Default model pricing per 1 Million tokens (USD): (input_price, output_price)
DEFAULT_RATES: dict[str, tuple[float, float]] = {
    # Amazon Nova models
    "nova-micro": (0.035, 0.140),
    "nova-lite": (0.060, 0.240),
    "nova-pro": (0.800, 3.200),
    # OpenAI models
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.500, 10.000),
    "gpt-3.5-turbo": (0.500, 1.500),
    # Anthropic models
    "claude-3-haiku": (0.250, 1.250),
    "claude-3-5-sonnet": (3.000, 15.000),
    # TypeSafe / Jev models
    "jev-latest": (0.042, 0.042),
}


def resolve_model_rate(model_name: str, *, is_jev: bool = False) -> tuple[float, float]:
    """Resolve (input_price_per_1M, output_price_per_1M) in USD.

    Checks environment overrides first:
      - JEV: JEV_PRICE_PER_M or JEV_INPUT_PRICE_PER_M
      - Chat: CHAT_INPUT_PRICE_PER_M / CHAT_OUTPUT_PRICE_PER_M or CHAT_PRICE_PER_M
    Falls back to matching against DEFAULT_RATES.
    """
    if is_jev:
        env_rate = os.getenv("JEV_PRICE_PER_M") or os.getenv("JEV_INPUT_PRICE_PER_M")
        if env_rate:
            try:
                val = float(env_rate.strip())
                return val, val
            except ValueError:
                pass
    else:
        env_in = os.getenv("CHAT_INPUT_PRICE_PER_M") or os.getenv("CHAT_PRICE_PER_M")
        env_out = os.getenv("CHAT_OUTPUT_PRICE_PER_M") or os.getenv("CHAT_PRICE_PER_M")
        if env_in:
            try:
                in_val = float(env_in.strip())
                out_val = float(env_out.strip()) if env_out else in_val
                return in_val, out_val
            except ValueError:
                pass

    clean = (model_name or "").lower().strip()
    for key, (in_p, out_p) in DEFAULT_RATES.items():
        if key in clean:
            return in_p, out_p

    if is_jev:
        return 0.042, 0.042
    return 0.035, 0.140


@dataclass
class Spend:
    # Jev telemetry
    jev_calls: int = 0
    jev_input_tokens: int = 0
    jev_output_tokens: int = 0
    jev_model: str = "jev-latest"

    # Chat LLM telemetry (Strands Agent)
    chat_calls: int = 0
    chat_input_tokens: int = 0
    chat_output_tokens: int = 0
    chat_model: str = "nova-micro"
    agent_cycles: int = 0

    # Scrape / Cache stats
    firecrawl_scrapes: int = 0
    cache_hits: int = 0
    started: float = field(default_factory=time.perf_counter)

    # Detailed traces from agent execution
    agent_traces: list[dict[str, Any]] = field(default_factory=list)
    tool_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_scrape(self) -> None:
        self.firecrawl_scrapes += 1

    def add_cache_hit(self) -> None:
        self.cache_hits += 1

    def add_jev(self, input_tokens: int, output_tokens: int = 0) -> None:
        self.jev_calls += 1
        self.jev_input_tokens += int(input_tokens or 0)
        self.jev_output_tokens += int(output_tokens or 0)

    def add_chat(self, input_tokens: int, output_tokens: int = 0) -> None:
        self.chat_calls += 1
        self.chat_input_tokens += int(input_tokens or 0)
        self.chat_output_tokens += int(output_tokens or 0)

    def record_agent_metrics(self, metrics: object) -> None:
        """Trace the agent's actual execution metrics directly from the Strands event loop."""
        if not metrics:
            return

        # 1. Real token usage from accumulated event loop usage
        usage = getattr(metrics, "accumulated_usage", None) or {}
        if isinstance(usage, dict):
            in_tok = usage.get("inputTokens", usage.get("input_tokens", 0))
            out_tok = usage.get("outputTokens", usage.get("output_tokens", 0))
            self.chat_input_tokens = int(in_tok or 0)
            self.chat_output_tokens = int(out_tok or 0)

        # 2. Total event loop cycles
        self.agent_cycles = int(getattr(metrics, "cycle_count", 0) or 0)
        if self.agent_cycles:
            self.chat_calls = self.agent_cycles

        # 3. Traces
        traces = getattr(metrics, "traces", None) or []
        parsed_traces: list[dict[str, Any]] = []
        for trace in traces:
            if hasattr(trace, "to_dict"):
                try:
                    parsed_traces.append(trace.to_dict())
                except Exception:
                    pass
            elif isinstance(trace, dict):
                parsed_traces.append(trace)
        self.agent_traces = parsed_traces

        # 4. Tool metrics breakdown
        tool_metrics_obj = getattr(metrics, "tool_metrics", None) or {}
        parsed_tools: dict[str, dict[str, Any]] = {}
        if isinstance(tool_metrics_obj, dict):
            for name, tm in tool_metrics_obj.items():
                parsed_tools[name] = {
                    "call_count": getattr(tm, "call_count", 0),
                    "success_count": getattr(tm, "success_count", 0),
                    "total_time": getattr(tm, "total_time", 0.0),
                }
        self.tool_metrics = parsed_tools

    def calculate_jev_cost(self) -> float:
        in_rate, out_rate = resolve_model_rate(self.jev_model, is_jev=True)
        return (self.jev_input_tokens * in_rate + self.jev_output_tokens * out_rate) / 1_000_000

    def calculate_chat_cost(self) -> float:
        in_rate, out_rate = resolve_model_rate(self.chat_model, is_jev=False)
        return (self.chat_input_tokens * in_rate + self.chat_output_tokens * out_rate) / 1_000_000

    def consolidated_cost(self) -> dict[str, Any]:
        """Consolidated cost breakdown across Jev and Chat LLM."""
        jev_cost = self.calculate_jev_cost()
        chat_cost = self.calculate_chat_cost()
        total_cost = jev_cost + chat_cost
        in_j, out_j = resolve_model_rate(self.jev_model, is_jev=True)
        in_c, out_c = resolve_model_rate(self.chat_model, is_jev=False)
        return {
            "jev_cost_usd": jev_cost,
            "chat_cost_usd": chat_cost,
            "total_cost_usd": total_cost,
            "jev_model": self.jev_model,
            "chat_model": self.chat_model,
            "rates": {
                "jev_input_per_m": in_j,
                "jev_output_per_m": out_j,
                "chat_input_per_m": in_c,
                "chat_output_per_m": out_c,
            },
        }

    def figures(self) -> tuple[float, float]:
        """Measured wall time in seconds, and consolidated total USD."""
        elapsed = time.perf_counter() - self.started
        total_usd = self.calculate_jev_cost() + self.calculate_chat_cost()
        return elapsed, total_usd

    def report(self, chat_in: int = 0, chat_out: int = 0) -> str:
        """Formatted console summary with consolidated costs and execution traces."""
        if chat_in and not self.chat_input_tokens:
            self.chat_input_tokens = chat_in
        if chat_out and not self.chat_output_tokens:
            self.chat_output_tokens = chat_out

        elapsed = time.perf_counter() - self.started
        cost = self.consolidated_cost()

        lines = [
            "----------------------------------------------------------------",
            "Consolidated Cost & Telemetry Trace Report",
            "----------------------------------------------------------------",
            f"Time: {elapsed:.1f}s",
            f"Firecrawl: {self.firecrawl_scrapes} scrape(s) | {self.cache_hits} cache hit(s)",
            "",
            f"[1] Jev Model ({cost['jev_model']}):",
            f"    Calls: {self.jev_calls}",
            f"    Input tokens: {self.jev_input_tokens:,}",
            f"    Output tokens: {self.jev_output_tokens:,}",
            f"    Rate: ${cost['rates']['jev_input_per_m']:.4f} / 1M tokens",
            f"    Jev cost: ${cost['jev_cost_usd']:.6f}",
            "",
            f"[2] Chat LLM ({cost['chat_model']}):",
            f"    Agent cycles: {self.agent_cycles}",
            f"    Input tokens: {self.chat_input_tokens:,}",
            f"    Output tokens: {self.chat_output_tokens:,}",
            f"    Rates: ${cost['rates']['chat_input_per_m']:.4f}/1M in, ${cost['rates']['chat_output_per_m']:.4f}/1M out",
            f"    Chat cost: ${cost['chat_cost_usd']:.6f}",
            "",
            f"CONSOLIDATED TOTAL COST: ${cost['total_cost_usd']:.6f} USD",
        ]

        if self.tool_metrics:
            lines.append("")
            lines.append("Tool Execution Traces:")
            for tool_name, stats in self.tool_metrics.items():
                lines.append(
                    f"    - {tool_name}: {stats['call_count']} call(s), "
                    f"{stats['total_time']:.2f}s (success: {stats['success_count']})"
                )

        if self.agent_traces:
            lines.append(f"Agent Event Loop Traces: {len(self.agent_traces)} cycle(s) tracked")

        lines.append("----------------------------------------------------------------")
        return "\n".join(lines)
