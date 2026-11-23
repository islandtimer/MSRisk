"""Match supplier names against entity-level lists. Possible matches are proposed, never applied silently.

Lists:
  - US CBP Withhold Release Orders & Findings (entity names)        -> enforcement indicator
  - DHS UFLPA Entity List (names and aliases)                         -> enforcement indicator
  - UK Modern Slavery Statement Registry (organisation/parent names)  -> governance information (not a risk indicator)

Matching rule (deliberately conservative, then human-confirmed):
  - names are normalised (case, accents, punctuation, legal suffixes such as Co./Ltd/Group removed);
  - a candidate is proposed when rapidfuzz token_set_ratio >= MIN_SCORE and the shared words cover at least 60% of
    the longer name (or token_sort_ratio >= MIN_SCORE); one-word normalised names only match exactly
    (short aliases like "Meike" would otherwise match far too much);
  - the reviewer records decisions in config/entity_match_decisions.csv (confirmed / rejected).
    Confirmed enforcement matches become a "government or regulatory indicator"; unconfirmed ones still select
    the supplier for review, labelled "possible enforcement-list match - requires confirmation"; rejected ones are dropped.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

HERE = Path(__file__).resolve().parent
ENT_DB = HERE.parent / "entities" / "data" / "entities.sqlite"
DECISIONS = HERE / "config" / "entity_match_decisions.csv"
MIN_SCORE = 90        # enforcement lists: favour recall, a person confirms
MIN_SCORE_UK = 95     # statement lookup is informational: favour precision
DECISION_COLS = ["vendor_name", "list", "record_id", "matched_name", "decision", "reviewer", "date", "note"]

LEGAL = r"\b(co|company|corp|corporation|ltd|limited|llc|inc|plc|pvt|private|pty|p l|gmbh|s\.?a|s\.?r\.?l|d\.?o\.?o|de c\.?v|l\.?l\.?c|group|holdings?|industr(y|ies)|the|sdn bhd|jsc)\b"


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).replace("�", " "))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(LEGAL, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_lists() -> dict | None:
    if not ENT_DB.exists():
        return None
    con = sqlite3.connect(ENT_DB)
    try:
        names = pd.read_sql("SELECT * FROM entity_names", con)
        uk = pd.read_sql("SELECT statement_year, organisation_name, parent_name, company_number, statement_summary_url, "
                         "statement_includes_due_diligence, policies FROM uk_msr_statements", con)
    finally:
        con.close()
    names["name_norm"] = names["name"].map(norm_name)  # re-normalise with this module's rule
    uk = uk.sort_values("statement_year").drop_duplicates(["organisation_name"], keep="last")
    uk_names = pd.concat([
        uk.assign(match_on=uk["organisation_name"], via="organisation"),
        uk[uk["parent_name"].fillna("") != ""].assign(match_on=uk["parent_name"], via="parent"),
    ])
    uk_names = uk_names[~uk_names["match_on"].str.fullmatch(r"\s*[A-Z]{0,2}\d{6,8}\s*", na=False)]
    uk_names["name_norm"] = uk_names["match_on"].map(norm_name)
    uk_names = uk_names[uk_names["name_norm"].str.len() >= 4].drop_duplicates(["name_norm", "statement_year", "via"])
    return {"names": names, "uk": uk_names}


def load_decisions() -> pd.DataFrame:
    if DECISIONS.exists():
        return pd.read_csv(DECISIONS, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return pd.DataFrame(columns=DECISION_COLS)


def _candidates(vname: str, pool: pd.DataFrame, min_score: int = MIN_SCORE) -> list[tuple[int, float]]:
    v = norm_name(vname)
    if len(v) < 4:
        return []
    choices = pool["name_norm"].tolist()
    out = []
    for _, score, idx in process.extract(v, choices, scorer=fuzz.token_set_ratio, score_cutoff=min_score, limit=10):
        cand = choices[idx]
        one_word = len(cand.split()) == 1 or len(v.split()) == 1
        if one_word and cand != v:
            continue
        # token_set_ratio scores 100 when one name's tokens are a subset of the other's; require that the
        # shorter side keeps at least two tokens so "silicon" alone cannot match "hoshine silicon".
        if min(len(cand.split()), len(v.split())) < 2 and cand != v:
            continue
        # subset matches must also cover most of the longer name ("grid one" vs "national grid holdings one" fails),
        # unless the overall order-insensitive similarity is itself high
        a, b = set(v.split()), set(cand.split())
        coverage = len(a & b) / max(len(a), len(b))
        if coverage < 0.6 and fuzz.token_sort_ratio(v, cand) < min_score:
            continue
        out.append((idx, float(score)))
    return out


def match_vendors(vendor_names: list[str]) -> dict[str, dict]:
    """Return {vendor_name: {"enforcement": [...], "uk_statements": [...]}} with decisions applied."""
    L = load_lists()
    if L is None:
        return {}
    dec = load_decisions()
    dkey = {(r["vendor_name"], r["list"], r["record_id"]): r["decision"].strip().lower() for _, r in dec.iterrows()}
    res = {}
    for v in vendor_names:
        enf, uk = [], []
        for idx, score in _candidates(v, L["names"]):
            r = L["names"].iloc[idx]
            d = dkey.get((v, r["list"], r["record_id"]), "")
            if d == "rejected":
                continue
            enf.append({"list": r["list"], "record_id": r["record_id"], "matched_name": r["name"], "score": score,
                        "detail": r["detail"], "source_url": r["source_url"], "decision": d or "unreviewed"})
        for idx, score in _candidates(v, L["uk"], MIN_SCORE_UK):
            r = L["uk"].iloc[idx]
            rid = f"UK-{r['statement_year']}-{r['company_number'] or r['match_on']}"
            d = dkey.get((v, "UK MSR", rid), "")
            if d == "rejected":
                continue
            uk.append({"list": "UK MSR", "record_id": rid, "matched_name": r["match_on"], "via": r["via"], "score": score,
                       "statement_year": r["statement_year"], "url": r["statement_summary_url"],
                       "due_diligence_section": r["statement_includes_due_diligence"], "decision": d or "unreviewed"})
        # keep the best few, de-duplicated by record
        seen, enf2 = set(), []
        for m in sorted(enf, key=lambda m: -m["score"]):
            if m["record_id"] not in seen:
                seen.add(m["record_id"]); enf2.append(m)
        seen, uk2 = set(), []
        for m in sorted(uk, key=lambda m: (-m["score"], -int(m["statement_year"]))):
            if m["matched_name"] not in seen:
                seen.add(m["matched_name"]); uk2.append(m)
        res[v] = {"enforcement": enf2[:5], "uk_statements": uk2[:3]}
    return res


def write_review_queue(matches: dict[str, dict], path: Path):
    """All proposed matches still awaiting a decision, in the same columns as the decisions file."""
    rows = []
    for v, m in matches.items():
        for x in m["enforcement"] + m["uk_statements"]:
            if x["decision"] == "unreviewed":
                rows.append({"vendor_name": v, "list": x["list"], "record_id": x["record_id"], "matched_name": x["matched_name"],
                             "decision": "", "reviewer": "", "date": "", "note": f"score {x['score']:.0f}"})
    pd.DataFrame(rows, columns=DECISION_COLS).to_csv(path, index=False, encoding="utf-8-sig")
    return len(rows)
