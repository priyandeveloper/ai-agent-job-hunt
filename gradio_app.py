"""Gradio hunt. Resume plus what the student wants, then a Jev score table."""

import html
from pathlib import Path

import gradio as gr

from placement.agent import run_agent
from placement.filters import company_name
from placement.resume_text import load_resume
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
    seconds, usd = spend.figures()
    per_job = f"{seconds / len(jobs):.1f} s per scored job" if jobs else "no scored job"
    return "\n".join(
        [
            "### This hunt",
            "",
            "| | |",
            "|---|---|",
            f"| Jobs scored | {len(jobs)} |",
            f"| Firecrawl scrapes | {spend.firecrawl_scrapes} of 10 |",
            f"| Time | {seconds:.1f} s |",
            f"| Speed | {per_job} |",
            f"| Jev calls | {spend.jev_calls} |",
            f"| Jev input tokens | {spend.jev_input_tokens} |",
            f"| Jev cost | ${usd:.6f} |",
            f"| Chat input tokens | {chat_in} |",
            f"| Chat output tokens | {chat_out} |",
        ]
    )


def run_hunt(resume_file, want):
    try:
        resume = _resolve_resume(resume_file)
        settings = load_settings(need_firecrawl=True)
        jobs, spend, chat_in, chat_out = run_agent(resume, settings, want=want or "")
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


with gr.Blocks(title="placement-fit") as demo:
    gr.Markdown(
        "# placement-fit\n"
        "Upload a resume and say what you want. A Strands agent calls scan_jobs, then score_jobs. Jev scores the jobs."
    )
    resume = gr.File(
        label="Resume (PDF / MD / TXT — empty uses the sample resume)",
        file_types=[".pdf", ".md", ".txt"],
        type="filepath",
    )
    want = gr.Textbox(
        label="What do you want?",
        placeholder="python intern Bengaluru",
    )
    hunt_btn = gr.Button("Hunt", variant="primary")
    table = gr.HTML()
    bill = gr.Markdown()
    held = gr.State({"jobs": []})
    pick = gr.Dropdown(label="Job number", choices=[], value=None)
    email_btn = gr.Button("Write email")
    email_out = gr.Textbox(label="Email", lines=14)
    hunt_btn.click(run_hunt, inputs=[resume, want], outputs=[table, bill, pick, held])
    email_btn.click(write_email, inputs=[pick, held, want], outputs=email_out)


if __name__ == "__main__":
    demo.launch()
