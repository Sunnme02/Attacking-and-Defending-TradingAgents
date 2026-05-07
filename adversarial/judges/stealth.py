"""
Stealth metric for adversarial payloads (A1 + A2).

PAPER RIGOR — what this answers:
  Claim: "Our generated fake news / pump posts pass an independent
   anomaly detector that was not used during generation."
  Test: compare each payload's fingerprint to a real-news baseline. A
  payload is "stealthy" if its fingerprint sits within the real-news
  distribution; not-stealthy if it stands out as anomalous.

DESIGN — two-tier:

  Tier 1 (always available, no heavy deps):
    - Lexical features: sentence-length stats, word-length,
      type-token-ratio, punctuation density, hedge-word count,
      retail-tone marker count
    - Distributional: word-bigram JS divergence vs baseline
    - Combined into stealth_score ∈ [0, 1]

  Tier 2 (optional, requires `pip install torch transformers`):
    - FinBERT (ProsusAI/finbert) embedding distance to baseline centroid
    - Provides a deep-LM-grounded score complementary to Tier 1
    - Loaded lazily; absence does not break Tier 1

Real-news baseline:
    Pulled on demand from yfinance Ticker.news for a small set of
    benchmark tickers (AAPL, NVDA, MSFT). Cached to disk so first run
    populates and subsequent runs reuse — zero recurring API cost.

Output format (per payload):
    {
      "lexical": {<feature>: float, ...},
      "stealth_score_lexical": 0.0-1.0,    # 1 = real-like, 0 = anomalous
      "stealth_score_finbert": 0.0-1.0,    # null if torch unavailable
      "verdict": "natural" | "borderline" | "anomalous",
    }
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

# NB: yfinance is imported lazily inside ``fetch_baseline``. The
# real-news baseline corpus is committed to disk under
# ``adversarial/data/real_news_baseline/`` so deploy targets that omit
# yfinance from their requirements (e.g. Streamlit Cloud) can still
# import this module and call ``score()`` without hitting the network.

ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "adversarial" / "data" / "real_news_baseline"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "META"]

# -------- Real-news baseline ---------------------------------------------

def fetch_baseline(force: bool = False) -> list[str]:
    """Pull recent news titles + summaries from yfinance for benchmark
    tickers. Cached to disk so repeated runs are zero-cost — and so
    deployments without yfinance installed still have a baseline."""
    cache_path = BASELINE_DIR / "real_news_corpus.json"
    if cache_path.exists() and not force:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    # Only need yfinance when the cache is missing.
    import yfinance as yf

    corpus: list[str] = []
    for t in BASELINE_TICKERS:
        try:
            news_items = yf.Ticker(t).news or []
        except Exception:
            continue
        for it in news_items:
            content = it.get("content", {}) if isinstance(it, dict) else {}
            title = content.get("title") or it.get("title", "")
            summary = content.get("summary") or it.get("summary", "")
            text = f"{title}. {summary}".strip()
            if len(text) >= 80:
                corpus.append(text)
    cache_path.write_text(
        json.dumps(corpus, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return corpus


# -------- Lexical features -----------------------------------------------

_HEDGE_WORDS = {
    "rumored", "alleged", "unverified", "unconfirmed", "sources say",
    "according to sources", "expressed skepticism", "however", "but",
    "doubts remain", "validity",
}
_RETAIL_MARKERS = {
    "to the moon", "🚀", "🌕", "💰", "💸", "loading", "fam",
    "buddy at", "media won't", "to the moon", "diamond hands",
    "💎", "📈", "📊", "$pltr", "$snow", "$nvda",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _tokens(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", text.lower())


def lexical_features(text: str) -> dict[str, float]:
    sents = _sentences(text)
    toks = _tokens(text)
    if not toks or not sents:
        return {
            "sent_count": 0.0, "avg_sent_len": 0.0, "sent_len_std": 0.0,
            "avg_word_len": 0.0, "type_token_ratio": 0.0,
            "punct_density": 0.0, "hedge_count": 0.0,
            "retail_marker_count": 0.0, "char_count": 0.0,
        }
    sent_lens = [len(_tokens(s)) for s in sents]
    types = len(set(toks))
    text_lower = text.lower()
    return {
        "sent_count": float(len(sents)),
        "avg_sent_len": float(statistics.mean(sent_lens)),
        "sent_len_std": float(statistics.stdev(sent_lens)) if len(sent_lens) > 1 else 0.0,
        "avg_word_len": float(statistics.mean(len(t) for t in toks)),
        "type_token_ratio": types / len(toks),
        "punct_density": sum(1 for c in text if c in ".,;:!?") / len(text),
        "hedge_count": float(sum(text_lower.count(h) for h in _HEDGE_WORDS)),
        "retail_marker_count": float(sum(text_lower.count(m) for m in _RETAIL_MARKERS)),
        "char_count": float(len(text)),
    }


def _baseline_feature_stats(corpus: list[str]) -> dict[str, dict[str, float]]:
    """Mean/std per feature across the real-news corpus."""
    feats = [lexical_features(doc) for doc in corpus if doc]
    out: dict[str, dict[str, float]] = {}
    if not feats:
        return out
    for k in feats[0]:
        vals = [f[k] for f in feats]
        out[k] = {
            "mean": float(statistics.mean(vals)),
            "std": float(statistics.stdev(vals)) if len(vals) > 1 else 1e-6,
        }
    return out


# -------- Distributional (bigram JS divergence) --------------------------

def _bigrams(text: str) -> Counter:
    toks = _tokens(text)
    return Counter(zip(toks, toks[1:]))


def _normalize(c: Counter) -> dict[tuple, float]:
    total = sum(c.values()) or 1
    return {k: v / total for k, v in c.items()}


def js_divergence_bigrams(payload: str, baseline_corpus: list[str]) -> float:
    """Jensen-Shannon divergence between payload's bigram dist and the
    pooled baseline-corpus bigram dist. 0 = identical, ln(2) ≈ 0.693 = max.
    Returns NaN if either distribution is empty."""
    p = _normalize(_bigrams(payload))
    base_counter: Counter = Counter()
    for doc in baseline_corpus:
        base_counter.update(_bigrams(doc))
    q = _normalize(base_counter)
    if not p or not q:
        return float("nan")
    keys = set(p) | set(q)
    pp = [p.get(k, 0.0) for k in keys]
    qq = [q.get(k, 0.0) for k in keys]
    m = [(pp[i] + qq[i]) / 2 for i in range(len(keys))]

    def kl(a: list[float], b: list[float]) -> float:
        s = 0.0
        for ai, bi in zip(a, b):
            if ai > 0 and bi > 0:
                s += ai * math.log(ai / bi)
        return s

    return 0.5 * kl(pp, m) + 0.5 * kl(qq, m)


# -------- Combined scoring ----------------------------------------------

@dataclass
class StealthVerdict:
    lexical: dict[str, float]
    stealth_score_lexical: float    # [0, 1]
    js_bigram: float                 # >=0
    stealth_score_finbert: float | None  # [0, 1] or None
    verdict: str                    # natural | borderline | anomalous

    def to_dict(self) -> dict:
        return asdict(self)


def _aggregate_lexical_score(
    feats: dict[str, float], baseline_stats: dict[str, dict[str, float]],
) -> float:
    """Z-score each feature against baseline; aggregate via mean abs z;
    map to [0, 1] via sigmoid where 0 anomaly = 1.0 stealth."""
    if not baseline_stats:
        return float("nan")
    abs_zs = []
    for k, v in feats.items():
        if k not in baseline_stats:
            continue
        m = baseline_stats[k]["mean"]
        s = baseline_stats[k]["std"] or 1e-6
        abs_zs.append(abs((v - m) / s))
    if not abs_zs:
        return float("nan")
    mean_abs_z = sum(abs_zs) / len(abs_zs)
    # mean_abs_z = 0 (perfectly average) -> stealth 1.0
    # mean_abs_z = ~3 (3 sigma off) -> stealth ~0.05
    return 1.0 / (1.0 + math.exp(mean_abs_z - 1.0))  # sigmoid centered at z=1


def _verdict_from(score: float, js: float) -> str:
    if math.isnan(score):
        return "unknown"
    if score >= 0.6 and js < 0.55:
        return "natural"
    if score >= 0.35 or js < 0.65:
        return "borderline"
    return "anomalous"


def score(payload: str, baseline_corpus: list[str] | None = None) -> StealthVerdict:
    if baseline_corpus is None:
        baseline_corpus = fetch_baseline()
    if not baseline_corpus:
        # Fallback: minimal hand-curated baseline (Bloomberg/Reuters style)
        baseline_corpus = _MINIMAL_BASELINE
    feats = lexical_features(payload)
    base_stats = _baseline_feature_stats(baseline_corpus)
    s_lex = _aggregate_lexical_score(feats, base_stats)
    js = js_divergence_bigrams(payload, baseline_corpus)
    s_fb = _try_finbert(payload, baseline_corpus)
    return StealthVerdict(
        lexical=feats,
        stealth_score_lexical=s_lex,
        js_bigram=js,
        stealth_score_finbert=s_fb,
        verdict=_verdict_from(s_lex, js),
    )


# -------- Optional FinBERT (lazy) ----------------------------------------

def _try_finbert(payload: str, baseline_corpus: list[str]) -> float | None:
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModel  # type: ignore
    except Exception:
        return None

    cache = getattr(_try_finbert, "_cache", None)
    if cache is None:
        tok = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        mdl = AutoModel.from_pretrained("ProsusAI/finbert")
        mdl.eval()
        cache = (tok, mdl, None)
        _try_finbert._cache = cache
    tok, mdl, baseline_centroid = cache

    def _embed(text: str) -> "torch.Tensor":
        enc = tok(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            out = mdl(**enc)
        return out.last_hidden_state[:, 0, :].squeeze(0)  # CLS

    if baseline_centroid is None:
        embs = [_embed(d) for d in baseline_corpus[:50]]
        baseline_centroid = torch.stack(embs).mean(dim=0)
        _try_finbert._cache = (tok, mdl, baseline_centroid)

    e = _embed(payload)
    cos = float(torch.nn.functional.cosine_similarity(
        e.unsqueeze(0), baseline_centroid.unsqueeze(0)
    ).item())
    # cos in [-1, 1]; map to [0, 1] where 1 = identical to baseline
    return (cos + 1.0) / 2.0


# -------- Score all cached payloads -------------------------------------

def score_all_cached() -> dict:
    """Score every A1 (fake_news/), A2 (pump_posts/), and A2v2
    (coord_disinfo/) payload on disk. Returns {attack_type: [verdict_dict, ...]}."""
    from adversarial.attacks.news_rewriter import _load_cache
    from adversarial.attacks.pump_generator import PumpBatch
    from adversarial.attacks.coordinated_disinfo import (
        CoordinatedPayload, format_for_injection as fmt_coord,
    )

    baseline = fetch_baseline()
    out: dict = {"a1": [], "a2": [], "a2v2": []}

    a1_dir = ROOT / "adversarial" / "data" / "fake_news"
    for p in sorted(a1_dir.glob("*.json")):
        if "refusal" in p.name:
            continue
        sample = _load_cache(p)
        if sample is None:
            continue
        v = score(sample.text, baseline)
        out["a1"].append({
            "ticker": sample.ticker, "date": sample.date,
            "case_id": sample.case_id, "direction": sample.direction,
            "model": sample.model,
            **v.to_dict(),
        })

    a2_dir = ROOT / "adversarial" / "data" / "pump_posts"
    for p in sorted(a2_dir.glob("*.json")):
        d = json.loads(p.read_text())
        b = PumpBatch(**d)
        joined = "\n".join(b.posts)
        v = score(joined, baseline)
        out["a2"].append({
            "ticker": b.ticker, "date": b.date, "direction": b.direction,
            "n": b.n_requested, "model": b.model,
            **v.to_dict(),
        })

    a2v2_dir = ROOT / "adversarial" / "data" / "coord_disinfo"
    if a2v2_dir.exists():
        for p in sorted(a2v2_dir.glob("*.json")):
            d = json.loads(p.read_text())
            payload = CoordinatedPayload(**d)
            # Score the FULL injection block (article + 5 social posts)
            # so the metric reflects what actually reached the agent.
            full_text = fmt_coord(payload)
            v = score(full_text, baseline)
            out["a2v2"].append({
                "ticker": payload.ticker, "date": payload.date,
                "direction": payload.direction, "model": payload.model,
                **v.to_dict(),
            })

    return out


# -------- Minimal hand-curated baseline (fallback if yfinance fails) -----

_MINIMAL_BASELINE = [
    "Apple reported quarterly revenue of $94.9 billion, beating analyst "
    "expectations. iPhone sales grew 6% year-over-year.",
    "Microsoft announced its Azure cloud business grew 33% in the latest "
    "quarter, exceeding the 28% growth seen by competitors.",
    "NVIDIA shares rose 4% in pre-market trading after the chipmaker said "
    "data center revenue more than doubled from a year earlier.",
    "The Federal Reserve held interest rates steady at the 5.25-5.50% range, "
    "citing concerns about persistent inflation in services.",
    "Goldman Sachs raised its price target on Tesla to $250, citing "
    "improving margins on the Model Y refresh.",
    "Boeing reported a wider-than-expected loss as production constraints "
    "and quality issues weighed on commercial aircraft deliveries.",
    "Pfizer announced positive Phase 3 trial results for its respiratory "
    "syncytial virus vaccine, with 86% efficacy in elderly patients.",
    "JPMorgan Chase posted record quarterly earnings of $13.4 billion, "
    "driven by higher net interest income and trading revenue.",
]


# -------- CLI -----------------------------------------------------------

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all-cached", action="store_true",
                   help="Score every cached payload and write a report.")
    p.add_argument("--text", default=None,
                   help="Score a single text from CLI.")
    p.add_argument("--refresh-baseline", action="store_true",
                   help="Re-fetch real-news corpus from yfinance.")
    args = p.parse_args()

    if args.refresh_baseline:
        n = len(fetch_baseline(force=True))
        print(f"Re-fetched real-news corpus: {n} documents")

    if args.text:
        v = score(args.text)
        print(json.dumps(v.to_dict(), indent=2, ensure_ascii=False))
    elif args.all_cached:
        report = score_all_cached()
        out = ROOT / "adversarial" / "data" / "stealth_report.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nWrote {out.relative_to(ROOT)}")
        for atk in ("a1", "a2", "a2v2"):
            rows = report[atk]
            if not rows:
                print(f"\n{atk}: no cached payloads")
                continue
            scores = [r["stealth_score_lexical"] for r in rows
                      if not math.isnan(r["stealth_score_lexical"])]
            jss = [r["js_bigram"] for r in rows
                   if not math.isnan(r["js_bigram"])]
            verdicts = Counter(r["verdict"] for r in rows)
            fb_vals = [r["stealth_score_finbert"] for r in rows
                       if r.get("stealth_score_finbert") is not None]
            print(f"\n{atk.upper()}  n={len(rows)}")
            print(f"  stealth_lexical: mean={statistics.mean(scores):.3f}  "
                  f"min={min(scores):.3f}  max={max(scores):.3f}")
            print(f"  js_bigram     : mean={statistics.mean(jss):.3f}  "
                  f"min={min(jss):.3f}  max={max(jss):.3f}")
            if fb_vals:
                print(f"  stealth_finbert: mean={statistics.mean(fb_vals):.3f}  "
                      f"min={min(fb_vals):.3f}  max={max(fb_vals):.3f}")
            print(f"  verdicts      : {dict(verdicts)}")
            for r in rows:
                fb = r.get("stealth_score_finbert")
                fb_s = f"finbert={fb:.3f}" if fb is not None else "finbert=—"
                if atk == "a1":
                    label = r.get("case_id", "?")
                elif atk == "a2":
                    label = "atlas"
                else:  # a2v2
                    label = f"coord_{r.get('direction', '?')}"
                print(f"    {r['ticker']:6s} {r['date']:12s} "
                      f"{label:28s} "
                      f"lex={r['stealth_score_lexical']:.3f}  "
                      f"js={r['js_bigram']:.3f}  {fb_s}  {r['verdict']}")
    else:
        p.print_help()
