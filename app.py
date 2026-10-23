"""Exam Strategy Studio: a local exam review log."""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import tempfile
import urllib.parse
from typing import Any

from flask import (
    Flask,
    Response,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_REPO_URL = "https://github.com/ryaneditraj/Exam"
AUTHOR_URL = "https://github.com/ryaneditraj"
INSTAGRAM_URL = "https://instagram.com/ryaneditraj"
MAX_QUESTION_LENGTH = 2000
MAX_EXAMS = 1000
MAX_DATA_BYTES = 2_000_000
MAX_MARK = 1000
MARK_RE = re.compile(r"\d{1,4}(\.\d{1,2})?")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{20,128}")
HOST_RE = re.compile(r"[A-Za-z0-9.-]{1,253}")

ON = {"1", "true", "yes", "on"}


class DataError(Exception):
    """The score sheet exists but cannot be trusted for a rewrite."""


def load_dotenv(path: str) -> None:
    """Read KEY=VALUE lines into the environment without overriding or executing."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            os.environ[key] = value


def flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ON


def exam_data_path() -> str:
    raw = os.environ.get("EXAM_DATA_FILE", "data/results.json").strip() or "data/results.json"
    if not os.path.isabs(raw):
        raw = os.path.join(BASE_DIR, raw)
    return os.path.abspath(raw)


def example_path() -> str:
    return os.path.abspath(os.path.join(BASE_DIR, "data", "results.example.json"))


def site_url() -> str:
    raw = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    if any(char in raw for char in '<>"\'` \t\r\n&'):
        return ""
    return raw


def allow_indexing() -> bool:
    return flag("ALLOW_INDEXING")


def trusted_hosts() -> list[str]:
    hosts = ["127.0.0.1", "localhost", "::1"]
    for item in os.environ.get("TRUSTED_HOSTS", "").split(","):
        host = item.strip()
        if host and host not in hosts and HOST_RE.fullmatch(host):
            hosts.append(host)
    return hosts


def og_image() -> str:
    site = site_url()
    if site:
        return f"{site}/og-cover.png"
    return f"{PUBLIC_REPO_URL}/raw/main/docs/screenshots/score-sheet.png"


def structured_data() -> dict[str, Any]:
    url = site_url() or PUBLIC_REPO_URL
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Exam Strategy Studio",
        "applicationCategory": "EducationalApplication",
        "operatingSystem": "Windows, macOS, Linux",
        "description": (
            "Local-first exam review log for practice questions, marks obtained, "
            "and total marks. The score sheet stays on your computer."
        ),
        "url": url,
        "codeRepository": PUBLIC_REPO_URL,
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "license": "https://opensource.org/licenses/MIT",
        "author": {
            "@type": "Person",
            "name": "Ryan Editraj",
            "url": AUTHOR_URL,
            "sameAs": [AUTHOR_URL, INSTAGRAM_URL],
        },
    }


load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
_secret = os.environ.get("SECRET_KEY", "").strip()
app.config.update(
    SECRET_KEY=_secret or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=flag("SESSION_COOKIE_SECURE"),
    MAX_CONTENT_LENGTH=32 * 1024,
    MAX_FORM_MEMORY_SIZE=32 * 1024,
    MAX_FORM_PARTS=8,
    TRUSTED_HOSTS=trusted_hosts(),
    TEMPLATES_AUTO_RELOAD=False,
)


@app.before_request
def set_csp_nonce() -> None:
    g.csp_nonce = secrets.token_urlsafe(16)


@app.after_request
def security_headers(response: Response) -> Response:
    nonce = getattr(g, "csp_nonce", "")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'nonce-{nonce}'; "
        "style-src 'self'; "
        "img-src 'self'; "
        "font-src 'self'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers.pop("Server", None)
    if request.path.startswith("/static/") or request.path == "/og-cover.png":
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.context_processor
def inject_meta() -> dict[str, Any]:
    return {
        "csp_nonce": getattr(g, "csp_nonce", ""),
        "site_url": site_url(),
        "public_url": site_url() or PUBLIC_REPO_URL,
        "og_image": og_image(),
        "allow_indexing": allow_indexing(),
        "structured_data": structured_data(),
        "repo_url": PUBLIC_REPO_URL,
        "author_url": AUTHOR_URL,
    }


def ensure_csrf() -> str:
    token = session.get("csrf_token")
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
        session.permanent = False
    return token


def csrf_ok() -> bool:
    sent = request.form.get("csrf_token", "")
    stored = session.get("csrf_token", "")
    if not isinstance(sent, str) or not isinstance(stored, str):
        return False
    if not TOKEN_RE.fullmatch(sent) or not TOKEN_RE.fullmatch(stored):
        return False
    return hmac.compare_digest(sent, stored)


def as_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value


def clip_form(form: Any) -> dict[str, str]:
    values = {}
    for name in ("question_text", "marks_obtained", "total_marks"):
        text = as_text(form.get(name, ""))
        text = "".join(char for char in text if char in "\n\t" or ord(char) >= 32)
        values[name] = text[:4000]
    return values


def clean_question(raw: Any) -> str:
    text = as_text(raw).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("Enter the question you want to review.")
    if len(text) > MAX_QUESTION_LENGTH:
        raise ValueError("That question is too long. Keep it under 2,000 characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise ValueError("The question contains a character this log does not accept.")
    return text


def parse_mark(raw: Any) -> float | None:
    text = as_text(raw).strip()
    if not MARK_RE.fullmatch(text):
        return None
    value = float(text)
    if value > MAX_MARK:
        return None
    return value


def to_cents(value: float) -> int:
    return int(round(value * 100))


def format_mark(value: float) -> str:
    cents = to_cents(value)
    whole, frac = divmod(cents, 100)
    if frac == 0:
        return str(whole)
    if frac % 10 == 0:
        return f"{whole}.{frac // 10}"
    return f"{whole}.{frac:02d}"


def clean_entry(form: Any) -> dict[str, str]:
    question = clean_question(form.get("question_text", ""))
    obtained = parse_mark(form.get("marks_obtained", ""))
    total = parse_mark(form.get("total_marks", ""))
    if obtained is None:
        raise ValueError("Enter marks obtained as a number from 0 to 1,000.")
    if total is None or total <= 0:
        raise ValueError("Enter total marks as a number greater than 0, up to 1,000.")
    if to_cents(obtained) > to_cents(total):
        raise ValueError("Marks obtained cannot be higher than the total.")
    return {
        "question_text": question,
        "marks_obtained": format_mark(obtained),
        "total_marks": format_mark(total),
    }


def stored_mark(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return None
    return parse_mark(value.strip())


def tone_for(percent: int) -> str:
    if percent >= 80:
        return "high"
    if percent >= 50:
        return "mid"
    return "low"


def present(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    rows = []
    got = 0.0
    total = 0.0
    countable = 0
    for item in data.get("exams", []):
        if not isinstance(item, dict):
            question = "This entry could not be read."
            obtained = None
            full = None
        else:
            question = item.get("question_text", "")
            if not isinstance(question, str) or not question.strip():
                question = "This entry has no question text."
            obtained = stored_mark(item.get("marks_obtained"))
            full = stored_mark(item.get("total_marks"))
        percent = None
        if obtained is not None and full is not None and full > 0 and to_cents(obtained) <= to_cents(full):
            percent = round((obtained / full) * 100)
            got += obtained
            total += full
            countable += 1
        rows.append(
            {
                "question": question,
                "obtained_label": format_mark(obtained) if obtained is not None else "—",
                "total_label": format_mark(full) if full is not None else "—",
                "percent": percent,
                "tone": tone_for(percent) if percent is not None else "",
            }
        )
    if countable == 0 or total <= 0:
        return rows, None
    summary = {
        "questions": len(rows),
        "obtained_label": format_mark(got),
        "total_label": format_mark(total),
        "percent": round((got / total) * 100),
        "tone": tone_for(round((got / total) * 100)),
    }
    return rows, summary


def load_data() -> dict[str, Any]:
    path = exam_data_path()
    if path == example_path() or os.path.islink(path):
        raise DataError(path)
    if not os.path.exists(path):
        return {"exams": []}
    if not os.path.isfile(path) or os.path.getsize(path) > MAX_DATA_BYTES:
        raise DataError(path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataError(path) from exc
    if not isinstance(data, dict) or not isinstance(data.get("exams"), list):
        raise DataError(path)
    return data


def save_data(data: dict[str, Any]) -> None:
    path = exam_data_path()
    if path == example_path() or os.path.islink(path):
        raise OSError("refusing to write this score sheet path")
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    descriptor, tmp = tempfile.mkstemp(dir=directory, prefix=".results-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        tmp = ""
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def render_home(status: int = 200, errors: list[str] | None = None, form: dict[str, str] | None = None):
    load_error = None
    try:
        data = load_data()
    except DataError:
        data = {"exams": []}
        load_error = (
            "The score sheet file could not be read. Nothing new will be saved until it is valid JSON again."
        )
    rows, summary = present(data)
    body = render_template(
        "index.html",
        errors=errors or [],
        form=form or {"question_text": "", "marks_obtained": "", "total_marks": ""},
        rows=rows,
        summary=summary,
        load_error=load_error,
        csrf_token=ensure_csrf(),
    )
    return body, status


@app.route("/", methods=["GET"])
def home():
    return render_home()


@app.route("/api/add_question", methods=["POST"])
def add_question():
    form = clip_form(request.form)
    if not csrf_ok():
        return render_home(
            400,
            errors=["The form expired. Refresh the page and try again."],
            form=form,
        )
    try:
        entry = clean_entry(request.form)
    except ValueError as exc:
        return render_home(400, errors=[str(exc)], form=form)
    try:
        data = load_data()
    except DataError:
        return render_home(
            400,
            errors=["The score sheet could not be read, so the question was not saved."],
            form=form,
        )
    if len(data["exams"]) >= MAX_EXAMS:
        return render_home(
            400,
            errors=["The score sheet already has 1,000 questions. Nothing new was saved."],
            form=form,
        )
    data["exams"].append(entry)
    try:
        save_data(data)
    except OSError:
        app.logger.exception("Could not save the score sheet")
        return render_home(500, errors=["The question could not be saved to disk."], form=form)
    session.pop("csrf_token", None)
    flash("Saved on this computer.")
    return redirect(url_for("home"))


@app.route("/robots.txt")
def robots():
    site = site_url()
    if not site:
        return send_from_directory(BASE_DIR, "robots.txt", mimetype="text/plain")
    body = f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    site = site_url()
    if not site:
        return send_from_directory(BASE_DIR, "sitemap.xml", mimetype="application/xml")
    if not allow_indexing():
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "</urlset>\n"
        )
        return Response(body, mimetype="application/xml")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{site}/</loc>\n"
        "    <changefreq>weekly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")


@app.route("/llms.txt")
def llms():
    return send_from_directory(BASE_DIR, "llms.txt", mimetype="text/plain")


@app.route("/.well-known/security.txt")
def security_txt():
    return send_from_directory(
        os.path.join(BASE_DIR, ".well-known"),
        "security.txt",
        mimetype="text/plain",
    )


@app.route("/og-cover.png")
def og_cover():
    return send_from_directory(
        os.path.join(BASE_DIR, "docs", "screenshots"),
        "score-sheet.png",
        mimetype="image/png",
    )


@app.errorhandler(404)
def not_found(_error):
    return (
        render_template(
            "error.html",
            heading="Page not found",
            message="That page is not part of Exam Strategy Studio.",
        ),
        404,
    )


@app.errorhandler(413)
def too_large(_error):
    return (
        render_template(
            "error.html",
            heading="That submission is too large",
            message="Keep the question under 2,000 characters and try again.",
        ),
        413,
    )


@app.errorhandler(500)
def server_error(_error):
    return (
        render_template(
            "error.html",
            heading="Something went wrong",
            message="Reload the page and try again.",
        ),
        500,
    )


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("PORT", "5001"))
    except ValueError:
        raise SystemExit("PORT must be a number from 1 to 65535.") from None
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be a number from 1 to 65535.")
    debug = flag("FLASK_DEBUG")
    if debug:
        app.logger.warning(
            "FLASK_DEBUG is on. Do not expose this process to a network you do not trust."
        )
    if not os.environ.get("SECRET_KEY", "").strip():
        app.logger.warning("SECRET_KEY is not set. The form session resets when the process restarts.")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
