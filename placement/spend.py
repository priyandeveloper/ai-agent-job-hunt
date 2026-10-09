"""Tokens and time for one hunt. Jev is billed on input tokens only."""

import time
from dataclasses import dataclass, field

# Published Jev price. Chat tokens are counted separately; their dollar rate depends on CHAT_MODEL.
JEV_USD_PER_MILLION = 0.042


@dataclass
class Spend:
    jev_calls: int = 0
    jev_input_tokens: int = 0
    firecrawl_scrapes: int = 0
    started: float = field(default_factory=time.perf_counter)

    def add_scrape(self) -> None:
        self.firecrawl_scrapes += 1

    def add_jev(self, tokens: int) -> None:
        self.jev_calls += 1
        self.jev_input_tokens += tokens

    def figures(self) -> tuple[float, float]:
        """Measured wall time in seconds, and Jev input-token dollars."""
        elapsed = time.perf_counter() - self.started
        usd = self.jev_input_tokens / 1_000_000 * JEV_USD_PER_MILLION
        return elapsed, usd

    def report(self, chat_in: int = 0, chat_out: int = 0) -> str:
        elapsed, usd = self.figures()
        return "\n".join(
            [
                "This hunt",
                f"  time: {elapsed:.1f}s",
                f"  Jev calls: {self.jev_calls}",
                f"  Jev input tokens: {self.jev_input_tokens}",
                f"  Jev cost: ${usd:.6f}",
                f"  Chat input tokens: {chat_in}",
                f"  Chat output tokens: {chat_out}",
            ]
        )
