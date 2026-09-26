"""Named things in a title: the model, tool, plugin or product an item is about, so that mentions
from different sources can be counted together ("Qwen 3.8", "Qwen3.8-27B", "unsloth/Qwen3.8-GGUF"
are one entity, `qwen38`).

No model and no training data: a span of name-like words (a digit, an inner capital, a dot or
plus between letters, or a capital that is not the title's first letter), cut at three words,
with generic words dropped. A title in Title Case capitalises every word, so there only the
strongly name-like words count. Addresses name things exactly and win over the title:
`github.com/<owner>/<repo>` is the repo, `huggingface.co/<org>/<model>` the model family.

`key()` is the join key everywhere: casefolded, size and quantisation suffixes dropped, every
character that is not a letter or digit removed.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#'’_-]*")
_VERSION_ONLY = re.compile(r"^[vb]?\d+(\.\d+)*[a-z]?$", re.I)
# Size, quantisation and packaging suffixes: one model family, many files.
_SUFFIX = re.compile(
    r"[-_ ](?:\d+(?:\.\d+)?[bm]|a\d+(?:\.\d+)?b|e\d+b|\d+x\d+b|gguf|awq|gptq|mlx|exl[23]|fp8|fp16|nvfp4|bf16|int[48]"
    r"|style|compatible|like|based|level|q\d(?:_k)?(?:_[a-z]+)?|iq\d\w*|ud|\d+bit|instruct|chat|it|base|thinking|preview|hf|\d{4}(?:-?\d{2}){0,2})$", re.I)

# Platforms and the field itself: part of a name ("Claude Code", "Google Gemini 4"), never a
# trend on their own.
BRANDS = set("""
ai llm llms gpt gpu gpus cpu api apis cli sdk mcp ui ux os ide ml rl rag nlp tts stt asr vlm vlms moe agi asi
sota oss foss usa eu uk us io claude anthropic openai google meta microsoft apple nvidia amd intel github
reddit youtube twitter hn huggingface hf arxiv linux windows macos ios android mac iphone pc chatgpt copilot
gemini vst vst3 au aax daw synth python rust audio image video speech voice vision music code coder
beginners awesome java
""".split())
# The words headlines are built from: cut from either end of a span.
FILLER = set("""
new update updated release released releases introducing announcing announced show ask tell launch launches
today yesterday week weekly daily part the a an i my we our you your this that it its here there what why how
made one two first last best just now finally official free open pull request requests psa wtf tps tl dr faq
qa eli5 imo fyi diy vs version edition max pro mini beta alpha preview guide tutorial review benchmark
benchmarks evaluation study survey agent agents model models plugin plugins next agentic decision system systems
flash omni local open-source opensource
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december
""".split())
GENERIC = BRANDS | FILLER
_CLAUSE = re.compile(r"\s*(?:[:|·!?]|\s[-–—]\s|\.\s)\s*")

_PREFIXES = {"show", "launch", "ask", "tell"}
_OWNER = re.compile(r"(?<![\w.])[\w.-]+/(?=[\w.-])")
_UNIT = re.compile(r"^\d+(?:[kmgt]b|gbps|k|x|hz|khz|fps|ms|w|tok|tps|gb|tb|mb|mm|nm|p|th|st|nd|rd)?$")
_STRONG_NAME = re.compile(r"(?:\d.*[A-Za-z]|[A-Za-z].*\d|[a-z][A-Z]|[A-Za-z][.+][A-Za-z])")
_GITHUB_SKIP = {"orgs", "topics", "features", "settings", "marketplace", "sponsors", "collections", "trending"}
_HF_SKIP = {"datasets", "spaces", "papers", "blog", "docs", "models", "collections", "posts"}


def key(name: str) -> str:
    """The join key: 'Qwen3.8-27B-Instruct' and 'qwen 3.8' both give 'qwen38'."""
    s = name.casefold().strip()
    for _ in range(4):
        t = _SUFFIX.sub("", s).strip(" -_.")
        if t == s or not t:
            break
        s = t
    return re.sub(r"[^a-z0-9]", "", s)


def _clean(word: str) -> str:
    return re.sub(r"['’]s$", "", word).strip(".-_'’#")


def _name_like(word: str, first: bool) -> bool:
    if "'" in word or "’" in word:
        return False  # I've, don't
    if _STRONG_NAME.search(word):
        return True
    return not first and word[:1].isupper() and len(word) > 1 and word.casefold() not in FILLER


def _usable(words: list[str]) -> str | None:
    """A span as an entity name, or None when nothing specific is left."""
    while words and words[0].casefold() in FILLER:
        words = words[1:]
    while words and words[-1].casefold() in FILLER:
        words = words[:-1]
    if not words or (len(words) == 1 and words[0].casefold() in GENERIC):
        return None
    name = " ".join(words)
    k = key(name)
    if len(k) < 3 or k in GENERIC or _VERSION_ONLY.match(name) or k.isdigit() or _UNIT.match(k):
        return None
    if len(words) == 1 and words[0].isupper() and len(words[0]) <= 3:
        return None  # a bare short acronym (RAG, TTS, PSA) is vocabulary, not a thing
    return name


def _spans(clause: list[str], title_case: bool) -> list[list[str]]:
    spans: list[list[str]] = []
    cur: list[str] = []
    for i, w in enumerate(clause):
        ok = bool(_STRONG_NAME.search(w)) if title_case else _name_like(w, first=(i == 0))
        # a version right after a name belongs to it: "Qwen 3.8", "Mica v0.1"
        if not ok and cur and _VERSION_ONLY.match(w):
            ok = True
        # a capitalised first word counts when a version or a name follows: "Qwen 3.8", "Claude Code"
        if not ok and i == 0 and len(clause) > 1 and w[:1].isupper() and w.casefold() not in FILLER:
            nxt = clause[1]
            ok = bool(_VERSION_ONLY.match(nxt) or _STRONG_NAME.search(nxt) or (nxt[:1].isupper() and not title_case))
        if ok and len(cur) < 3:
            cur.append(w)
        else:
            if cur:
                spans.append(cur)
            cur = [w] if ok else []
    if cur:
        spans.append(cur)
    return spans


def from_title(title: str) -> list[str]:
    """Entity names in a title, longest spans first, at most five. A title's head before a colon
    or dash names its subject ("Show HN: Foo – …", "BuildBench: …") when it is one to three
    capitalised words."""
    title = _OWNER.sub("", title or "")  # "owner/repo": the repo is the thing
    clauses = [[w for w in (_clean(x) for x in _WORD.findall(c)) if w] for c in _CLAUSE.split(title)]
    clauses = [c for c in clauses if c]
    words = [w for c in clauses for w in c]
    if not words:
        return []
    prose = [w for c in clauses if c[0].casefold() not in _PREFIXES for w in c]  # "Show HN" says nothing of the case
    caps = sum(1 for w in prose if w[:1].isupper())
    title_case = len(prose) >= 4 and caps / len(prose) > 0.6
    spans: list[list[str]] = []
    heads = [c for c in clauses[:2] if c[0].casefold() not in _PREFIXES] if len(clauses) > 1 else []
    if heads and len(heads[0]) <= 3 and all(w[:1].isupper() or w[:1].isdigit() for w in heads[0]):
        spans.append(heads[0])
    for c in clauses:
        spans += _spans(c, title_case)
    out: list[str] = []
    for span in sorted(spans, key=len, reverse=True):
        name = _usable(span)
        if name and key(name) not in {key(o) for o in out}:
            out.append(name)
    return out[:5]


def family_key(k: str) -> str:
    """'qwen38' -> 'qwen', 'opus55' -> 'opus': the name without its version; '' when nothing that
    is not generic is left."""
    stem = re.sub(r"v?\d.*$", "", k)
    return stem if len(stem) >= 3 and stem != k and stem not in GENERIC else ""


def from_url(url: str) -> list[str]:
    """The exact name an address carries: a GitHub repo or a Hugging Face model family."""
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return []
    host = (parts.hostname or "").removeprefix("www.")
    path = [p for p in parts.path.split("/") if p]
    if host == "github.com" and len(path) >= 2 and path[0] not in _GITHUB_SKIP:
        return [n for n in (_usable([path[1].removesuffix(".git")]),) if n]
    if host == "huggingface.co" and len(path) >= 2 and path[0] not in _HF_SKIP:
        return [hf_family(f"{path[0]}/{path[1]}")]
    return []


def hf_family(model_id: str) -> str:
    """'unsloth/Qwen3.8-27B-Instruct-GGUF' -> 'Qwen3.8'; 'x/Mica-v0.1-4B' -> 'Mica-v0.1'."""
    name = model_id.split("/")[-1]
    parts = re.split(r"[-_]", name)
    while len(parts) > 1 and _SUFFIX.fullmatch("-" + parts[-1]):
        parts.pop()
    return "-".join(parts)


def lowercase_vocabulary(titles) -> Counter:
    """How often each word appears written in lower case, over a set of titles."""
    c: Counter = Counter()
    for t in titles:
        c.update(w for w in _WORD.findall(t or "") if w.islower())
    return c


def is_word(name: str, vocab: Counter) -> bool:
    """A single plain word that the same titles also write in lower case, or one in capitals for
    emphasis ("SAVE", "Skills", "Search"): vocabulary, not a name. A digit, an inner capital or a
    dot keeps it ("GPT-6", "KoboldCpp", "llama.cpp")."""
    if " " in name or _STRONG_NAME.search(name):
        return False
    if name.isupper():
        return True
    return vocab.get(name.casefold(), 0) >= 1


def of(title: str, url: str = "", hints: list[str] | None = None, vocab: Counter | None = None) -> list[str]:
    """Every entity of one mention: hints and the address first (they are exact), then the title."""
    out: list[str] = []
    seen: set[str] = set()
    names = [*(hints or []), *from_url(url), *from_title(title)]
    for name in (n for n in names if not (vocab is not None and is_word(n, vocab))):
        k = key(name)
        if k and k not in seen and k not in GENERIC and len(k) >= 3:
            seen.add(k)
            out.append(name)
    return out
