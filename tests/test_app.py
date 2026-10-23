import json
import os
import re
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-please-32b")
os.environ.setdefault("ALLOW_INDEXING", "0")
os.environ.pop("SITE_URL", None)

from app import app


class ExamStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "results.json")
        os.environ["EXAM_DATA_FILE"] = self.path
        self.client = app.test_client()

    def token_from(self, response):
        match = re.search(br'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match, response.data[:400])
        return match.group(1).decode()

    def add(self, question, obtained, total, token=None):
        if token is None:
            token = self.token_from(self.client.get("/"))
        return self.client.post(
            "/api/add_question",
            data={
                "csrf_token": token,
                "question_text": question,
                "marks_obtained": obtained,
                "total_marks": total,
            },
        )

    def saved(self):
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_home_is_private_and_has_the_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertIn(b"Exam Strategy Studio", body)
        self.assertIn(b'name="question_text"', body)
        self.assertIn(b'name="marks_obtained"', body)
        self.assertIn(b'name="total_marks"', body)
        self.assertIn(b"Save question", body)
        self.assertIn(b"noindex, nofollow", body)
        self.assertIn(b"application/ld+json", body)
        self.assertIn(b"og:title", body)
        self.assertFalse(os.path.exists(self.path))

    def test_save_keeps_the_original_schema_and_order(self):
        first = self.add("Explain speed and velocity.", "4", "6")
        self.assertEqual(first.status_code, 302)
        self.assertTrue(first.headers["Location"].endswith("/"))
        second = self.add("Find the average speed.", "5", "5")
        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            self.saved()["exams"],
            [
                {
                    "question_text": "Explain speed and velocity.",
                    "marks_obtained": "4",
                    "total_marks": "6",
                },
                {
                    "question_text": "Find the average speed.",
                    "marks_obtained": "5",
                    "total_marks": "5",
                },
            ],
        )
        page = self.client.get("/")
        self.assertIn(b"Saved on this computer.", page.data)
        self.assertIn(b"67%", page.data)
        self.assertIn(b"100%", page.data)
        mode = os.stat(self.path).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_marks_are_canonicalised(self):
        response = self.add("Half marks.", "7.50", "10")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.saved()["exams"][0]["marks_obtained"], "7.5")

    def test_user_text_is_escaped_and_not_executed(self):
        payload = '</textarea><script>alert(1)</script>{{7*7}}'
        rejected = self.add(payload, "nope", "4")
        self.assertEqual(rejected.status_code, 400)
        self.assertNotIn(b"<script>", rejected.data)
        self.assertIn(b"&lt;/textarea&gt;", rejected.data)
        self.assertIn(b"&lt;script&gt;", rejected.data)
        saved = self.add(payload, "1", "4")
        self.assertEqual(saved.status_code, 302)
        page = self.client.get("/")
        self.assertNotIn(b"<script>", page.data)
        self.assertIn(b"{{7*7}}", page.data)
        self.assertNotIn(b"What is 49", page.data)
        self.assertEqual(self.saved()["exams"][0]["question_text"], payload)

    def test_missing_csrf_does_not_save(self):
        response = self.client.post(
            "/api/add_question",
            data={"question_text": "Sneaky", "marks_obtained": "1", "total_marks": "1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(os.path.exists(self.path))
        self.assertIn(b"form expired", response.data.lower())

    def test_bad_marks_and_blank_questions_are_rejected(self):
        blank = self.add("   ", "1", "2")
        self.assertEqual(blank.status_code, 400)
        self.assertFalse(os.path.exists(self.path))
        cases = [
            ("Question", "1", "0"),
            ("Question", "-1", "5"),
            ("Question", "3", "2"),
            ("Question", "abc", "5"),
            ("Question", "1001", "1001"),
            ("Question\x00", "1", "2"),
        ]
        for question, obtained, total in cases:
            with self.subTest(question=question, obtained=obtained, total=total):
                response = self.add(question, obtained, total)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(os.path.exists(self.path))

    def test_corrupt_file_is_not_overwritten(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{")
        with open(self.path, encoding="utf-8") as handle:
            before = handle.read()
        response = self.add("Keep me", "1", "2")
        self.assertEqual(response.status_code, 400)
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"could not be read", page.data)

    def test_extra_keys_are_preserved(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"owner": "kept", "exams": []}, handle)
        self.assertEqual(self.add("Extra", "1", "1").status_code, 302)
        data = self.saved()
        self.assertEqual(data["owner"], "kept")
        self.assertEqual(data["exams"][0]["question_text"], "Extra")

    def test_entry_cap(self):
        payload = {
            "exams": [
                {"question_text": "q", "marks_obtained": "1", "total_marks": "1"}
                for _ in range(1000)
            ]
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        response = self.add("one more", "1", "1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.saved()["exams"]), 1000)

    def test_large_body_is_rejected(self):
        response = self.client.post(
            "/api/add_question",
            data={"question_text": "a" * 40000, "marks_obtained": "1", "total_marks": "1"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertNotIn(b"<script>", response.data)
        self.assertFalse(os.path.exists(self.path))

    def test_security_headers_cookie_and_host(self):
        response = self.client.get("/")
        self.assertFalse(app.debug)
        self.assertLessEqual(app.config["MAX_CONTENT_LENGTH"], 32 * 1024)
        csp = response.headers["Content-Security-Policy"]
        self.assertNotIn("unsafe-inline", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        nonce = re.search(r"script-src 'nonce-([^']+)'", csp)
        self.assertIsNotNone(nonce)
        self.assertIn(f'nonce="{nonce.group(1)}"'.encode(), response.data)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Server", response.headers)
        parts = [part.strip() for part in response.headers["Set-Cookie"].split(";")]
        self.assertIn("HttpOnly", parts)
        self.assertIn("SameSite=Lax", parts)
        self.assertNotIn("Secure", parts)
        blocked = self.client.get("/", headers={"Host": "evil.example"})
        self.assertEqual(blocked.status_code, 400)

    def test_get_cannot_save(self):
        self.assertEqual(self.client.get("/api/add_question").status_code, 405)

    def test_page_has_no_third_party_assets(self):
        html = self.client.get("/").data.decode()
        for host in (
            "googleapis",
            "gstatic",
            "cloudflare",
            "jsdelivr",
            "unpkg",
            "googletagmanager",
        ):
            self.assertNotIn(host, html)
        self.assertIn('href="/static/studio.css"', html)
        for path in ("/static/studio.css", "/static/favicon.svg", "/static/fonts/fraunces-latin.woff2"):
            asset = self.client.get(path)
            self.addCleanup(asset.close)
            self.assertEqual(asset.status_code, 200)

    def test_indexing_can_be_turned_on(self):
        os.environ["ALLOW_INDEXING"] = "1"
        try:
            self.assertIn(b"index, follow", self.client.get("/").data)
        finally:
            os.environ["ALLOW_INDEXING"] = "0"

    def fetch(self, path, **kwargs):
        response = self.client.get(path, **kwargs)
        self.addCleanup(response.close)
        return response

    def test_seo_routes_and_site_url_injection(self):
        robots = self.fetch("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b"Allow: /", robots.data)
        sitemap = self.fetch("/sitemap.xml")
        self.assertIn(b"https://github.com/ryaneditraj/Exam", sitemap.data)
        llms = self.fetch("/llms.txt")
        self.assertIn(b"Exam Strategy Studio", llms.data)
        self.assertIn(b"local", llms.data.lower())
        security = self.fetch("/.well-known/security.txt")
        self.assertIn(b"security/advisories/new", security.data)
        missing = self.client.get("/<script>alert(1)</script>")
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn(b"<script>alert", missing.data)

        os.environ["SITE_URL"] = "javascript:alert(1)"
        try:
            poisoned_response = self.fetch("/sitemap.xml")
            poisoned = poisoned_response.data
            self.assertNotIn(b"javascript", poisoned)
            self.assertIn(b"https://github.com/ryaneditraj/Exam", poisoned)
        finally:
            os.environ.pop("SITE_URL", None)

        os.environ["SITE_URL"] = "https://exam.example"
        os.environ["ALLOW_INDEXING"] = "1"
        try:
            live = self.fetch("/sitemap.xml").data.decode()
            self.assertIn("https://exam.example/", live)
            self.assertIn(
                "Sitemap: https://exam.example/sitemap.xml",
                self.fetch("/robots.txt").data.decode(),
            )
        finally:
            os.environ.pop("SITE_URL", None)
            os.environ["ALLOW_INDEXING"] = "0"

    def test_example_file_documents_the_schema(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "results.example.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIsInstance(data["exams"], list)
        entry = data["exams"][0]
        self.assertEqual(
            set(entry),
            {"question_text", "marks_obtained", "total_marks"},
        )

    def test_cover_image_is_a_png(self):
        response = self.client.get("/og-cover.png")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertTrue(response.data.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
