# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through [GitHub security advisories](https://github.com/ryaneditraj/Exam/security/advisories/new).

Do not open a public issue, and do not paste exploit details into a pull request. Include what you found, which version or commit you tested, and the impact as you understand it.

Private vulnerability reporting has to be enabled by the repository owner under Settings, Code security. Until that switch is on, contact [Ryan Editraj](https://github.com/ryaneditraj) directly instead of filing a public issue.

This project is maintained as time allows. There is no bug-bounty program and no guaranteed response window. Please give the maintainer time to fix a confirmed issue before writing about it in public.

The running app also serves this policy at `/.well-known/security.txt`.

## Supported versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Older commits | No |

There are no numbered releases yet. Use the latest commit on `main`.

## What this app is

Exam Strategy Studio is a local, single-user exam review log. It is not an account system, not a multi-tenant website, and not a place to store secrets. The sensitive data it does hold is the text of your questions and your marks, in `data/results.json` on the computer where the app runs.

## Secrets audit

The full git history of this repository was reviewed on 23 October 2026 (both commits, `5a4afae` and `24ac35d`, plus the tree they produced). The review looked for API keys, tokens, passwords, private keys, and cloud credentials.

No secret was found. There is nothing in the committed history to rotate.

`data/results.json` was committed, but it contained only `{"exams": []}` — an empty score sheet, not personal questions and not a credential. That live file is no longer tracked. `data/results.example.json` is the sample shape.

## Protections in the app

- The Flask debugger is off unless `FLASK_DEBUG` is set. The debugger can execute code on the machine if the port is reachable. Leave it off.
- The development server binds to `127.0.0.1` unless `HOST` is set.
- Question text is stored as data and rendered as escaped text. It is not concatenated into a template.
- The save form uses a per-session token. A foreign site cannot submit a question with the victim's browser alone.
- Mark fields accept only numbers from 0 to 1,000, and marks obtained cannot exceed the total.
- Requests larger than 32 KB are rejected. The sheet stops accepting new questions at 1,000 entries. Files over 2 MB are treated as unreadable and are not overwritten.
- Corrupt JSON is not replaced with a fresh file on the next save.
- The score sheet is written atomically and is created with mode `0600`.
- The app refuses to write through a symlink or to overwrite `data/results.example.json`.
- Pages send `noindex` unless `ALLOW_INDEXING=1`, so a deployed copy does not publish private questions by default.
- Open Graph text is static. Logged questions are never placed in the page title, the description, or the social card.
- Responses set a content security policy with no inline scripts except the JSON-LD block, which carries a per-request nonce. Styles, fonts, and images are same-origin. There is no third-party asset host.
- `Host` headers other than localhost, `127.0.0.1`, `::1`, and names listed in `TRUSTED_HOSTS` are rejected.
- HTML responses are `Cache-Control: no-store`.

## Dependencies

Direct dependencies are pinned in `requirements.txt` to the current patched releases as of 23 October 2026:

| Package | Pin | Why this floor |
| --- | --- | --- |
| Flask | 3.1.3 | Fixes [GHSA-68rp-wp8r-4726](https://github.com/pallets/flask/security/advisories) (session access and `Vary: Cookie`). |
| Werkzeug | 3.1.9 | Includes the 2026 `safe_join` fixes, most recently [GHSA-g6x2-hccm-hh4m](https://github.com/pallets/werkzeug/security/advisories/GHSA-g6x2-hccm-hh4m). This app does not build filesystem paths from question text. The pin still keeps the stack patched. |
| Jinja2 | 3.1.6 | Fixes [GHSA-cpwx-vrp4-4pq7](https://github.com/advisories/GHSA-cpwx-vrp4-4pq7). User text is a template variable, not a template. |
| MarkupSafe, ItsDangerous, Click, Blinker | pinned | Transitive runtime, locked so installs do not float. |

`requests` was listed in the original `requirements.txt` and was never imported. It has been removed so a fresh install does not pull an unused package.

The original requirements were not pinned. A fresh install today would have received current releases, but nothing stopped an older or yanked release from being installed later. Pins plus Dependabot are the fix.

The interactive debugger issue [GHSA-2g68-c3qc-8985](https://github.com/pallets/werkzeug/security/advisories) is not something a version pin removes. The debugger is a feature. This project leaves it off unless you opt in.

## If you run it somewhere other than your laptop

- Set `SECRET_KEY` to a long random value so form sessions survive a restart.
- Serve it over HTTPS and set `SESSION_COOKIE_SECURE=1`.
- Leave `FLASK_DEBUG` unset.
- Set `TRUSTED_HOSTS` to the hostname you actually use.
- Set `SITE_URL` to that origin.
- Turn on `ALLOW_INDEXING` only when the sheet contains no private questions.
- The file on disk is not encrypted. Full-disk encryption, or the permissions on the machine, is what protects it at rest.

## Residual risk

Anyone who can use the operating-system account can read and edit `data/results.json`. That is the trust boundary. The app does not add accounts, password hashing, or encryption on top of it.

A browser extension, or malware on the same machine, can read the page. CSRF protection does not defend against that.

There is no rate limit. The app is meant to be reached from the same computer, not from the open internet.
