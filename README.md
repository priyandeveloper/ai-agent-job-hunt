# Build an AI Agent That Hunts Jobs for You

3 hours. One working agent. Real jobs.

You pass a resume and a short line about what you want. A Strands agent calls two tools and stops. `scan_jobs` searches the web with Firecrawl and keeps recruiter links. `score_jobs` opens those pages, drops anything that is not a job description, and sends three of them to Jev. The chat model never sees the resume or the full job text.

Jev is the fast decision model. The session blurb calls it RLCD. Same model: `jev-latest`.

## The three hours

| Time | What you do | What you read |
|---|---|---|
| 0:00–0:20 | Setup. Run the tests. | `placement/gate.py` |
| 0:20–1:00 | Score one local posting. See apply, stretch, skip, and ask. | `placement/score.py` |
| 1:00–1:45 | Run `hunt` with `--want`. Watch `scan_jobs`, then `score_jobs`, then stop. | `placement/agent.py` |
| 1:45–2:25 | Tighten the URL filter or the JD check. Hunt again with your PDF. | `placement/filters.py` |
| 2:25–2:45 | Read the cost line. Compare it with `compare` on one saved JD. | `placement/spend.py` |
| 2:45–3:00 | Fork the repo. Do not commit `.env`. | this file |

## Layout

```
app.py                    hunt runs the Strands agent
placement/agent.py        two tools: scan_jobs, score_jobs
placement/filters.py      which URLs and pages count as a job
placement/query.py        search text from resume labels plus --want
placement/profile.py      one Jev call that picks role, level, language
placement/scrape.py       Firecrawl search, then one page
placement/hunt.py         the same steps written in order
placement/score.py        Jev fit, including pay type
placement/spend.py        time, Jev cost, chat tokens
placement/gate.py         apply / stretch / skip / ask
placement/resume_text.py  PDF or text in
resume.md                 sample student
samples/posting.md        one posting, no network
```

`placement/boards.py` is a Greenhouse fallback. The hunt does not call it.

## Setup

Python 3.10 or newer. A laptop, internet, and your resume.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with the FutureX key, the chat base URL (`/v1` included), the Jev base URL (no `/v1`), the chat model id, and a Firecrawl key. `hunt` needs `FIRECRAWL_API_KEY`.

Check the gate and the filters with no API calls:

```powershell
python -m unittest tests.test_decide tests.test_filters tests.test_boards
```

## Commands

The resume file and `--want` are the two inputs. Jev reads the resume once to pick a role, a level, and a language. Your words are appended to that search.

```powershell
python app.py hunt --resume resume.md --want "python intern Bengaluru"
```

Your own CV:

```powershell
python app.py hunt --resume C:\path\to\resume.pdf --want "data analyst intern remote"
```

The run ends with time, Jev cost, and the chat tokens spent on the tool loop. Each job card shows the description, pay type, match score, and the audit (bond, experience bar, Jev's bucket next to the code decision).

Score one known posting, with no search:

```powershell
python app.py score --jd samples/posting.md
```

Time Jev against a chat model on that same file, with no search and no agent loop.

```powershell
python app.py compare --jd samples/posting.md
```

## What Jev is asked

One call builds the search. Up to three more calls score jobs. Each score call also asks how the role is paid, so pay does not cost a second request.

| Question | Type | The gate uses it for |
|---|---|---|
| `skill_overlap` | score, 0–4 | apply, stretch, or skip |
| `requires_bond` | probability | skip when it is high, ask when it is close |
| `above_fresher` | probability | skip when the job wants a year or more of full-time work |
| `pay_type` | stipend / salaried / not posted | printed on the card |
| `verdict` | apply / stretch / skip | printed beside the code decision |

`decide()` wins when it disagrees with Jev's verdict. A cold email is a separate step: `python app.py score --url <apply-link> --draft`. The hunt itself does not write one.

The sample student is fictional. Replace `resume.md` before you send anything.
