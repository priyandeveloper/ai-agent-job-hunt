# Placement Fit

A 3-hour workshop project. Paste a resume, point at a job posting, and get a decision you can defend: **apply**, **stretch**, or **skip**. A draft is written only when the decision is apply or stretch.

The posting is scraped with Firecrawl. Fit is scored by Jev through the TypeSafe SDK. The draft is one chat call on the FutureX key. A Strands agent can call the same scrape and score functions as tools.

## Layout

```
app.py                 run this
placement/settings.py  keys and base URLs
placement/scrape.py    Firecrawl → posting text
placement/gate.py      apply / stretch / skip, plain Python
placement/score.py     Jev questions, then the gate
placement/write.py     one chat call for the draft
placement/agent.py     Strands tools around scrape and score
resume.md              sample student, replace with yours
samples/posting.md     local posting, no Firecrawl needed
```

`app.py` is the whole pipeline. Read it first. Each file under `placement/` is one step.

## Setup

Python 3.10 or newer.

```powershell
cd placement-fit
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with the campus FutureX key, the chat base URL, the Jev base URL, the chat model id, and a Firecrawl key.

`FUTUREX_BASE_URL` includes `/v1` because the OpenAI client calls `/chat/completions`.
`JEV_BASE_URL` does not. The TypeSafe SDK adds `/v1/systemone` itself.

## Run

Score the sample posting. This path does not call Firecrawl.

```powershell
python app.py --jd samples/posting.md
```

Score a live posting:

```powershell
python app.py --url "https://company.example/careers/intern"
```

Use your own resume:

```powershell
python app.py --jd samples/posting.md --resume my-resume.md
```

Hand the same steps to a Strands agent. This needs a URL.

```powershell
python app.py --url "https://company.example/careers/intern" --agent
```

Check the gate without calling any API:

```powershell
python -m unittest tests.test_decide
```

## What the gate does

Jev answers four questions about the resume and the posting:

| Question | Type | Meaning |
|---|---|---|
| `skill_overlap` | score, 0–4 | How much of the required stack is already in the resume |
| `requires_bond` | probability | A service bond or a repay-if-you-leave clause |
| `above_fresher` | probability | More than a year of full-time work, or a degree the resume lacks |
| `verdict` | apply / stretch / skip | Jev's own bucket |

`decide()` in `placement/gate.py` is the policy. A likely bond or an experience bar above a fresher becomes **skip**, even if the skill score is high. Jev's verdict is printed beside the code decision so you can see when they disagree.

**skip** stops. **apply** and **stretch** go to `placement/write.py`. The writer may only use facts from the resume.

## In the room

1. Run the sample posting. Read `gate.py` until `decide()` is obvious.
2. Change `BOND_SKIP` or `SKILL_APPLY` in `gate.py`, rerun `python -m unittest tests.test_decide`, then rerun the sample.
3. Add the commented question in `score.py`, and use it inside `decide()`.
4. Swap `resume.md` for your own and score a real URL.
5. Run `--agent` and compare it with the linear run. The tools are the same functions.

The sample student is fictional. Replace `resume.md` before you apply to anything real.
