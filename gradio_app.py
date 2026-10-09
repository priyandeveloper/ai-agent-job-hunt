"""Gradio hunt. Resume plus what the student wants, then a Jev score table."""

import html
from pathlib import Path

import gradio as gr

from placement.agent import run_agent
from placement.filters import company_name
from placement import load_resume
from placement.scrape import Posting
from placement.settings import ROOT, load_settings
from placement.spend import Spend
from placement.write import draft_selected

DEFAULT_RESUME = ROOT / "resume.md"


def _resolve_resume(resume_file) -> str:
    path = Path(resume_file) if resume_file else DEFAULT_RESUME
    return load_resume(path)


def _cell(value: object) -> str:
    return html.escape(str(value))


def _match(job) -> str:
    score = max(0.0, min(float(job.fit.skill_score), 4.0))
    return f"{round(score / 4 * 100)}%"


def _labels(jobs: list) -> list[str]:
    return [f"{index}. {job.posting.title}" for index, job in enumerate(jobs, start=1)]


def _table(jobs: list) -> str:
    rows = []
    for index, job in enumerate(jobs, start=1):
        posting = job.posting
        url = html.escape(posting.url, quote=True)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{_cell(posting.title)}</td>"
            f"<td>{_cell(company_name(posting.url))}</td>"
            f'<td><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></td>'
            f"<td>{_match(job)}</td>"
            f"<td>{_cell(job.fit.note)}</td>"
            "</tr>"
        )
    return f"""
<table>
<thead>
<tr>
<th>#</th><th>Role</th><th>Company</th><th>Job portal</th><th>Match</th><th>Against the resume</th>
</tr>
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
"""


def _bill(spend: Spend, jobs: list, chat_in: int, chat_out: int) -> str:
    seconds, total_usd = spend.figures()
    per_job = f"{seconds / len(jobs):.1f} s per scored job" if jobs else "no scored job"
    cost = spend.consolidated_cost()

    rows = [
        "### Consolidated Cost & Telemetry Report",
        "",
        "| Operation / Overview | Metric |",
        "|---|---|",
        f"| Jobs scored | **{len(jobs)}** |",
        f"| Firecrawl scrapes | **{spend.firecrawl_scrapes} of 10** |",
        f"| Cache hits | **{spend.cache_hits}** |",
        f"| Wall time | **{seconds:.1f} s** ({per_job}) |",
        "",
        "#### Model Consumption & Cost Breakdown",
        "",
        "| Model | Operations / Tokens | Rates (USD / 1M) | Cost (USD) |",
        "|---|---|---|---|",
        f"| **Jev** (`{cost['jev_model']}`) | {spend.jev_calls} calls - {spend.jev_input_tokens:,} in / {spend.jev_output_tokens:,} out | ${cost['rates']['jev_input_per_m']:.4f} in | **${cost['jev_cost_usd']:.6f}** |",
        f"| **Chat LLM** (`{cost['chat_model']}`) | {spend.agent_cycles} cycles - {spend.chat_input_tokens:,} in / {spend.chat_output_tokens:,} out | ${cost['rates']['chat_input_per_m']:.4f} in / ${cost['rates']['chat_output_per_m']:.4f} out | **${cost['chat_cost_usd']:.6f}** |",
        f"| **CONSOLIDATED TOTAL** | **Total Tokens: {spend.jev_input_tokens + spend.jev_output_tokens + spend.chat_input_tokens + spend.chat_output_tokens:,}** | | **${cost['total_cost_usd']:.6f}** |",
    ]

    if spend.tool_metrics:
        rows.extend([
            "",
            "#### Tool Execution Traces",
            "",
            "| Tool | Calls | Total Time | Success Rate |",
            "|---|---|---|---|",
        ])
        for tool_name, stats in spend.tool_metrics.items():
            total_time = stats.get("total_time", 0.0)
            calls = stats.get("call_count", 0)
            succ = stats.get("success_count", 0)
            rows.append(f"| `{tool_name}` | {calls} | {total_time:.2f} s | {succ} / {calls} |")

    return "\n".join(rows)


def run_hunt(resume_file, want, limit=20):
    try:
        resume = _resolve_resume(resume_file)
        settings = load_settings(need_firecrawl=True)
        target_count = int(limit) if limit else 20
        jobs, spend, chat_in, chat_out = run_agent(resume, settings, want=want or "", limit=target_count)
    except SystemExit as exc:
        return "", f"⚠️ {exc}", gr.Dropdown(choices=[], value=None), {"jobs": []}
    except Exception as exc:
        return "", f"⚠️ {type(exc).__name__}: {exc}", gr.Dropdown(choices=[], value=None), {"jobs": []}

    if not jobs:
        return "", "No job descriptions survived. Try a more specific line, for example `python intern Bengaluru`.", gr.Dropdown(choices=[], value=None), {"jobs": []}
    labels = _labels(jobs)
    held = {
        "resume": resume,
        "jobs": [
            {
                "title": job.posting.title,
                "url": job.posting.url,
                "text": job.posting.text,
                "match": _match(job),
            }
            for job in jobs
        ],
    }
    return _table(jobs), _bill(spend, jobs, chat_in, chat_out), gr.Dropdown(choices=labels, value=labels[0]), held


def write_email(choice, held, want):
    jobs = (held or {}).get("jobs") or []
    if not choice or not jobs:
        return "Hunt first, then pick a job number."
    try:
        number = int(str(choice).split(".", 1)[0])
    except ValueError:
        return "Pick a job number from the list."
    if number < 1 or number > len(jobs):
        return "That job number is not in this hunt."
    job = jobs[number - 1]
    posting = Posting(source=job["url"], title=job["title"], text=job["text"])
    try:
        return draft_selected(
            (held or {}).get("resume", ""),
            posting,
            want or "",
            load_settings(),
            job["match"],
        )
    except SystemExit as exc:
        return f"⚠️ {exc}"
    except Exception as exc:
        return f"⚠️ {type(exc).__name__}: {exc}"


with gr.Blocks(title="AI Agent Hot Hunt") as demo:
    gr.Markdown(
        "# AI Agent Hot Hunt\n"
        "Upload a resume and say what you want. A Strands agent calls scan_jobs, then score_jobs. Jev scores the jobs."
    )
    resume = gr.File(
        label="Resume (PDF / MD / TXT — empty uses the sample resume)",
        file_types=[".pdf", ".md", ".txt"],
        type="filepath",
    )
    with gr.Row():
        want = gr.Textbox(
            label="What do you want?",
            placeholder="python intern Bengaluru",
            scale=3,
        )
        limit_slider = gr.Slider(
            minimum=10,
            maximum=30,
            value=20,
            step=5,
            label="Jobs to hunt (10–30)",
            scale=1,
        )
    hunt_btn = gr.Button("Hunt", variant="primary")
    table = gr.HTML()
    bill = gr.Markdown()
    held = gr.State({"jobs": []})
    pick = gr.Dropdown(label="Job number", choices=[], value=None)
    email_btn = gr.Button("Write email")
    email_out = gr.Textbox(label="Email", lines=14)
    hunt_btn.click(run_hunt, inputs=[resume, want, limit_slider], outputs=[table, bill, pick, held])
    email_btn.click(write_email, inputs=[pick, held, want], outputs=email_out)


if __name__ == "__main__":
    demo.launch(share=True)
