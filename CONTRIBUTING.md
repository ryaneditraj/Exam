# Contributing to Exam Strategy Studio

Thanks for wanting to improve the log. The useful changes are small and specific: a bug in saving marks, a clearer empty state, a test for a case that broke.

## Ground rules

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Be decent to people in issues, pull requests, and reviews.

Security bugs go through [SECURITY.md](SECURITY.md), not a public issue.

## Set up

```bash
git clone https://github.com/ryaneditraj/Exam.git
cd Exam
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5001. On Windows, create the virtual environment with `py -m venv .venv` and activate it with `.venv\Scripts\activate`.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use a temporary score sheet. They do not read or write your `data/results.json`.

## Pull requests

- Describe what changed and how you tested it.
- Keep the save behavior stable: `POST /api/add_question` still accepts `question_text`, `marks_obtained`, and `total_marks`, then redirects home. Stored entries keep those three string fields.
- Do not render question text as HTML or as a Jinja template. Pass it to the template as a variable and let autoescape do its job.
- Do not enable the debugger by default, bind `0.0.0.0` by default, or add a third-party script, font, or analytics host.
- Do not commit `.env`, `data/results.json`, or real questions from a paper. `data/results.example.json` is the committed sample.
- Pin new Python dependencies to a version you have checked for known vulnerabilities.

## What to work on

The [roadmap in the README](README.md#roadmap) is the current list. Editing or deleting a logged question, without opening the JSON file, is the gap people will hit first.
