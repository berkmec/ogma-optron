"""Synthetic eval case factory.

Returns a list of (case_id, expected_image_type, expected_intent,
user_prompt, png_bytes) tuples. PIL-drawn screenshots are easier than real
ones; treat pass rates here as a smoke gate, not a benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    expected_image_type: str
    expected_intent: str
    user_prompt: str
    png: bytes


def _draw(width: int, height: int, bg: tuple[int, int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), color=bg)
    return img, ImageDraw.Draw(img)


def _to_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _error_connection_refused() -> bytes:
    img, d = _draw(760, 420, (20, 22, 30))
    d.text((30, 30), "ERROR: ConnectionRefusedError", fill=(255, 90, 90))
    d.text((30, 80), "Could not connect to host api.example.com:443", fill=(220, 220, 220))
    d.text((30, 140), "Traceback (most recent call last):", fill=(180, 180, 180))
    d.text((30, 180), '  File "main.py", line 42, in <module>', fill=(180, 180, 180))
    d.text((30, 220), "    response = client.get(url, timeout=5)", fill=(180, 180, 180))
    d.text((30, 280), "ConnectionError: [Errno 111] Connection refused", fill=(255, 120, 120))
    return _to_png(img)


def _error_null_pointer() -> bytes:
    img, d = _draw(700, 360, (20, 22, 30))
    d.text((30, 30), "FATAL: NullPointerException", fill=(255, 80, 80))
    d.text((30, 80), "Traceback (most recent call last):", fill=(220, 220, 220))
    d.text((30, 120), '  File "main.py", line 42', fill=(220, 220, 220))
    d.text((30, 160), "  AttributeError: NoneType has no attribute", fill=(255, 110, 110))
    d.text((30, 220), "Process exited with code 1", fill=(200, 200, 200))
    return _to_png(img)


def _github_ultraworkers() -> bytes:
    img, d = _draw(900, 480, (255, 255, 255))
    d.rectangle([(0, 0), (900, 56)], fill=(13, 17, 23))
    d.text((20, 18), "GitHub  /  ultraworkers / claw-code", fill=(240, 246, 252))
    d.text((780, 18), "Star  Fork  Watch", fill=(240, 246, 252))
    d.text((20, 90), "Branches:  main  *", fill=(36, 41, 47))
    d.text((20, 130), "Latest commit  d3f4a2c  by berkmm1  2 hours ago", fill=(110, 119, 129))
    d.text((20, 180), "src/", fill=(9, 105, 218))
    d.text((20, 210), "tests/", fill=(9, 105, 218))
    d.text((20, 240), "README.md", fill=(9, 105, 218))
    d.text((20, 270), "LICENSE", fill=(9, 105, 218))
    d.text((20, 320), "Issues 12   Pull requests 3   Actions   Projects", fill=(36, 41, 47))
    return _to_png(img)


def _github_python_repo() -> bytes:
    img, d = _draw(900, 460, (255, 255, 255))
    d.rectangle([(0, 0), (900, 56)], fill=(13, 17, 23))
    d.text((20, 18), "GitHub  /  pallets / flask", fill=(240, 246, 252))
    d.text((20, 90), "Python  85.3%  HTML  6.7%  CSS  4.1%", fill=(36, 41, 47))
    d.text((20, 140), "src/flask/", fill=(9, 105, 218))
    d.text((20, 170), "tests/", fill=(9, 105, 218))
    d.text((20, 200), "docs/", fill=(9, 105, 218))
    d.text((20, 230), "pyproject.toml", fill=(9, 105, 218))
    d.text((20, 260), "CHANGES.rst", fill=(9, 105, 218))
    d.text((20, 320), "65.2k stars  16.4k forks", fill=(36, 41, 47))
    return _to_png(img)


def _ui_login() -> bytes:
    img, d = _draw(820, 540, (245, 247, 250))
    d.rectangle([(280, 140), (540, 460)], fill=(255, 255, 255), outline=(220, 220, 220))
    d.text((360, 170), "Sign in", fill=(30, 30, 30))
    d.text((310, 220), "Email", fill=(110, 110, 110))
    d.rectangle([(310, 240), (510, 270)], outline=(220, 220, 220))
    d.text((310, 290), "Password", fill=(110, 110, 110))
    d.rectangle([(310, 310), (510, 340)], outline=(220, 220, 220))
    d.rectangle([(310, 370), (510, 400)], fill=(30, 80, 200))
    d.text((380, 378), "Sign in", fill=(255, 255, 255))
    d.text((320, 420), "Forgot password?  ·  Create account", fill=(60, 90, 200))
    return _to_png(img)


def _ui_dashboard() -> bytes:
    img, d = _draw(900, 540, (245, 247, 250))
    d.rectangle([(0, 0), (900, 60)], fill=(30, 80, 200))
    d.text((20, 20), "Analytics Dashboard", fill=(255, 255, 255))
    for i, (label, value) in enumerate(
        [("Users", "12,304"), ("Revenue", "$48.2K"), ("Sessions", "9,812")]
    ):
        x = 30 + i * 280
        d.rectangle([(x, 100), (x + 250, 220)], fill=(255, 255, 255), outline=(220, 220, 220))
        d.text((x + 16, 120), label, fill=(110, 110, 110))
        d.text((x + 16, 160), value, fill=(20, 20, 20))
    d.text((30, 270), "Recent activity:", fill=(20, 20, 20))
    for i, txt in enumerate(["+ new signup", "+ payment received", "- subscription canceled"]):
        d.text((30, 310 + i * 30), txt, fill=(60, 60, 60))
    return _to_png(img)


def _code_editor_python() -> bytes:
    img, d = _draw(820, 500, (30, 30, 36))
    for i in range(16):
        d.text((10, 20 + i * 22), f"{i + 1:>3}", fill=(110, 110, 130))
    lines = [
        "def fetch_user(user_id: int) -> User | None:",
        '    """Return a user by id, or None if absent."""',
        "    with sessionmaker() as session:",
        "        return (",
        "            session.query(User)",
        "            .filter(User.id == user_id)",
        "            .one_or_none()",
        "        )",
        "",
        "class UserService:",
        "    def __init__(self, repo: UserRepo) -> None:",
        "        self.repo = repo",
        "",
        "    def get(self, user_id: int) -> User:",
        "        user = self.repo.find(user_id)",
        "        if user is None:",
    ]
    for i, line in enumerate(lines):
        d.text((50, 20 + i * 22), line, fill=(220, 220, 220))
    return _to_png(img)


def _code_editor_typescript() -> bytes:
    img, d = _draw(820, 500, (30, 30, 36))
    for i in range(14):
        d.text((10, 20 + i * 22), f"{i + 1:>3}", fill=(110, 110, 130))
    lines = [
        "export async function loadUser(id: string): Promise<User> {",
        "  const res = await fetch(`/api/users/${id}`);",
        "  if (!res.ok) throw new Error(`HTTP ${res.status}`);",
        "  return (await res.json()) as User;",
        "}",
        "",
        "export function UserCard({ user }: { user: User }) {",
        "  return (",
        "    <div className=\"card\">",
        "      <h2>{user.name}</h2>",
        "      <p>{user.email}</p>",
        "    </div>",
        "  );",
        "}",
    ]
    for i, line in enumerate(lines):
        d.text((50, 20 + i * 22), line, fill=(220, 220, 220))
    return _to_png(img)


def _document_attention() -> bytes:
    img, d = _draw(800, 1000, (255, 255, 255))
    d.text((60, 60), "Chapter 3: Attention Is All You Need", fill=(0, 0, 0))
    d.text((60, 110), "Abstract", fill=(60, 60, 60))
    body = (
        "The dominant sequence transduction models are based on complex recurrent or"
        " convolutional neural networks that include an encoder and a decoder. The best"
        " performing models also connect the encoder and decoder through an attention"
        " mechanism. We propose a new simple network architecture, the Transformer,"
        " based solely on attention mechanisms, dispensing with recurrence and"
        " convolutions entirely."
    )
    words = body.split()
    line, y = "", 150
    for w in words:
        if len(line) + len(w) + 1 > 90:
            d.text((60, y), line, fill=(30, 30, 30))
            y += 22
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        d.text((60, y), line, fill=(30, 30, 30))
    return _to_png(img)


def _document_invoice() -> bytes:
    img, d = _draw(700, 900, (255, 255, 255))
    d.text((60, 60), "INVOICE", fill=(0, 0, 0))
    d.text((60, 110), "Invoice #2026-0517", fill=(60, 60, 60))
    d.text((60, 140), "Date: 2026-05-17", fill=(60, 60, 60))
    d.text((60, 190), "Billed to: Acme Corp", fill=(30, 30, 30))
    d.text((60, 220), "123 Main Street", fill=(30, 30, 30))
    d.text((60, 280), "Description           Qty   Unit   Total", fill=(30, 30, 30))
    d.line([(60, 305), (640, 305)], fill=(150, 150, 150))
    d.text((60, 320), "Consulting hours        20    100    2000", fill=(30, 30, 30))
    d.text((60, 350), "Hosting (Q2)             1    300     300", fill=(30, 30, 30))
    d.line([(60, 405), (640, 405)], fill=(150, 150, 150))
    d.text((60, 425), "Subtotal                              2300", fill=(30, 30, 30))
    d.text((60, 455), "Tax (10%)                              230", fill=(30, 30, 30))
    d.text((60, 485), "Total Due                             2530 USD", fill=(0, 0, 0))
    return _to_png(img)


CASES: list[EvalCase] = [
    EvalCase("err_conn_refused", "error_screen", "error_debug",
             "What does this error mean and how do I fix it?",
             _error_connection_refused()),
    EvalCase("err_null_pointer", "error_screen", "error_debug",
             "Help me debug this exception.",
             _error_null_pointer()),
    EvalCase("gh_claw_code", "github_repo", "repo_review",
             "Give me a quick review of this repository.",
             _github_ultraworkers()),
    EvalCase("gh_flask", "github_repo", "repo_review",
             "Review this repository.",
             _github_python_repo()),
    EvalCase("ui_login", "ui_dashboard", "ui_help",
             "What is this screen and what should I do?",
             _ui_login()),
    EvalCase("ui_dashboard", "ui_dashboard", "ui_help",
             "Explain this dashboard.",
             _ui_dashboard()),
    EvalCase("code_python", "code_editor", "ui_help",
             "What does this code do?",
             _code_editor_python()),
    EvalCase("code_typescript", "code_editor", "ui_help",
             "Walk me through this snippet.",
             _code_editor_typescript()),
    EvalCase("doc_paper", "document_page", "ui_help",
             "Summarize this page.",
             _document_attention()),
    EvalCase("doc_invoice", "document_page", "ui_help",
             "What is this document?",
             _document_invoice()),
]
