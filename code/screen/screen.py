"""Supplier register + deterministic screening (stages 1-3 of the screening method).

    python screen.py SPEND_FILE [--config config/settings.json] [--out output]

Stage 1  population review: net spend per vendor, rank, cumulative share, concentration, data gaps.
Stage 2  core detailed-review population: vendors covering ~80% of spend (a prioritisation
         convention, not a risk threshold).
Stage 3  exception screening against the reference data (country, product x country,
         labour-intensive categories, labour hire/subcontracting, user nominations).

It does NOT assign a due diligence priority: that follows supplier research (stage 4).
It never infers sourcing country from domicile; sourcing comes only from the data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

import entity_match

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FLO_DB = ROOT / "flo" / "data" / "flo.sqlite"
GSI_DB = ROOT / "gsi" / "data" / "gsi.sqlite"
DOL_DB = ROOT / "dol" / "data" / "dol.sqlite"
CARDS = ROOT / "flo" / "data" / "cards"
GSI_CREDIT = "Global Slavery Index 2023 Dataset, Minderoo Foundation, available from: www.globalslaveryindex.org"


# --------------------------------------------------------------------------- reference data

def q(db: Path, sql: str) -> pd.DataFrame:
    con = sqlite3.connect(db)
    try:
        return pd.read_sql(sql, con)
    finally:
        con.close()


def load_reference(settings: dict) -> dict:
    countries = q(FLO_DB, "SELECT iso_code, country_name FROM countries")
    gsi = q(GSI_DB, "SELECT iso_code, gsi_country_name, prevalence_per_1000, vulnerability_total_pct, "
                    "government_response_total_pct FROM gsi_country_summary")
    g20 = q(GSI_DB, "SELECT product, origin_country, origin_iso, importer, importer_iso, import_value_kusd FROM gsi_g20_import_risk")
    ci = settings["country_indicator"]
    p_thr = gsi["prevalence_per_1000"].quantile(ci["prevalence_percentile"])
    gsi["flag_prevalence"] = gsi["prevalence_per_1000"] >= p_thr
    gsi["flag_vulnerability"] = gsi["vulnerability_total_pct"] >= ci["vulnerability_pct"]
    ent_db = ROOT / "entities" / "data" / "entities.sqlite"
    cbp = q(ent_db, "SELECT * FROM cbp_wro") if ent_db.exists() else None
    dol = dol_ds = None
    if DOL_DB.exists():
        dol = q(DOL_DB, "SELECT * FROM dol_goods")
        dol_ds = q(DOL_DB, "SELECT * FROM dol_downstream")
    # name -> iso lookup: FLO names, GSI names, aliases
    names = {}
    for _, r in countries.iterrows():
        names[r["country_name"].lower()] = r["iso_code"]
    for _, r in gsi.iterrows():
        names.setdefault(str(r["gsi_country_name"]).lower(), r["iso_code"])
    for k, v in settings["country_aliases"].items():
        names[k.lower()] = v
    iso_name = dict(zip(countries["iso_code"], countries["country_name"]))
    return {"countries": countries, "gsi": gsi.set_index("iso_code"), "g20": g20, "dol": dol, "dol_ds": dol_ds, "cbp": cbp,
            "names": names, "iso_name": iso_name, "prev_threshold": float(p_thr)}


# --------------------------------------------------------------------------- register

SUFFIX_RE = re.compile(r"\b(pty\.?|ltd\.?|limited|p/l|co\.?|inc\.?|llc|sdn\.? bhd\.?|jsc|group|holdings)\b", re.I)


def vendor_key(name: str) -> str:
    s = SUFFIX_RE.sub(" ", str(name).lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def countries_in_text(text: str, names: dict) -> list[str]:
    """ISO codes of countries named in free text, longest names first, whole words only."""
    found, t = [], f" {str(text).lower()} "
    for n in sorted(names, key=len, reverse=True):
        if len(n) < 4:  # avoid short aliases like 'au' matching inside words
            continue
        if re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", t):
            iso = names[n]
            if iso not in found:
                found.append(iso)
            t = re.sub(rf"(?<![a-z]){re.escape(n)}(?![a-z])", " ", t)
    return found


def build_register(spend: pd.DataFrame, settings: dict, cats: pd.DataFrame, prods: pd.DataFrame, ref: dict) -> pd.DataFrame:
    c = settings["spend_file"]["columns"]
    df = spend.rename(columns={v: k for k, v in c.items()})
    df["gl_code"] = df["gl_code"].astype(str).str.strip()
    df["description"] = df["description"].fillna("").astype(str)
    df["country"] = df["country"].fillna("").astype(str).str.strip()
    df["amount"] = pd.to_numeric(df["amount"])
    df["vendor_key"] = df["vendor_name"].map(vendor_key)
    cat = cats.set_index("gl_code")
    unknown_gl = sorted(set(df["gl_code"]) - set(cat.index))

    # One register entry per vendor ID. Vendor records whose names normalise to the same key are
    # flagged as possible duplicates, never merged automatically.
    ids_per_key = df.groupby("vendor_key")["vendor_id"].unique().to_dict()
    names_per_id = df.groupby("vendor_id")["vendor_name"].first().to_dict()
    out = []
    for vid, g in df.groupby("vendor_id", sort=False):
        key = g["vendor_key"].iloc[0]
        doms = sorted({x for x in g["country"] if x})
        dom_iso = sorted({ref["names"].get(x.lower()) or f"?{x}" for x in doms})
        text = " ".join(g["description"].tolist())
        gls = sorted(set(g["gl_code"]))
        cinfo = cat.reindex(gls)
        goods = (cinfo["goods_or_services"] == "goods").any()
        products = [p["product"] for _, p in prods.iterrows() if re.search(p["keywords_regex"], text, re.I)]
        products_source = "description"
        if not products and "default_products" in cinfo.columns:
            products = sorted({x for v in cinfo["default_products"].fillna("") for x in str(v).split(";") if x})
            products_source = "inferred from GL category" if products else ""
        sourcing = countries_in_text(text, ref["names"]) if goods else []
        gaps = []
        if not doms:
            gaps.append("vendor country missing")
        if any(x.startswith("?") for x in dom_iso):
            gaps.append("vendor country not recognised: " + ", ".join(x[1:] for x in dom_iso if x.startswith("?")))
        if goods and not sourcing:
            gaps.append("manufacturing/sourcing country not stated")
        if (g["description"].str.strip() == "").any():
            gaps.append("blank line description")
        if products and products_source != "description":
            gaps.append(f"goods ({', '.join(products)}) inferred from GL category, not from the description")
        others = [o for o in ids_per_key.get(key, []) if o != vid]
        if others:
            gaps.append("possible duplicate vendor record: " + "; ".join(f"{o} ({names_per_id[o]})" for o in others)
                        + " (not merged; confirm)")
        if (g["amount"] < 0).any():
            gaps.append("credit notes netted")
        if set(gls) & set(unknown_gl):
            gaps.append("GL code not in category map")
        out.append({
            "vendor_key": key,
            "vendor_name": g.loc[g["amount"].idxmax(), "vendor_name"],
            "vendor_id": vid,
            "net_spend": round(g["amount"].sum(), 2),
            "gl_codes": ";".join(gls),
            "category": "; ".join(sorted(set(cinfo["category"].dropna()))),
            "goods_or_services": "goods" if goods else "services",
            "sector": "; ".join(sorted(set(cinfo["sector"].dropna()))),
            "labour_intensive": bool(cinfo["labour_intensive"].fillna(False).astype(bool).any()),
            "sector_alone_elevates": bool(cinfo["sector_alone_elevates"].fillna(False).astype(bool).any()),
            "labour_hire_category": bool(cinfo["labour_hire_or_subcontracting"].fillna(False).astype(bool).any()),
            "labour_hire_keyword": bool(re.search(settings["labour_hire_keywords_regex"], text, re.I)),
            "domicile_iso": ";".join(x for x in dom_iso if not x.startswith("?")),
            "sourcing_iso": ";".join(sourcing),
            "products": ";".join(products),
            "products_source": products_source if products else "",
            "description": text[:300],
            "information_gaps": gaps,
        })
    reg = pd.DataFrame(out).sort_values("net_spend", ascending=False).reset_index(drop=True)
    return reg, unknown_gl


# --------------------------------------------------------------------------- screening

def country_evidence(iso: str, ref: dict) -> str | None:
    g = ref["gsi"]
    if iso not in g.index:
        return None
    r = g.loc[iso]
    bits = []
    if bool(r["flag_prevalence"]):
        bits.append(f"prevalence {r['prevalence_per_1000']:.1f} per 1,000 (at or above the {ref['prev_threshold']:.1f} threshold)")
    if bool(r["flag_vulnerability"]):
        bits.append(f"vulnerability {r['vulnerability_total_pct']:.0f}%")
    return (f"{ref['iso_name'].get(iso, iso)}: GSI 2023 " + "; ".join(bits)) if bits else None


def product_country_evidence(product: str, iso: str, prods: pd.DataFrame, ref: dict) -> list[str]:
    ev = []
    p = prods.set_index("product").loc[product]
    g20 = ref["g20"]
    if isinstance(p["gsi_g20_product"], str) and p["gsi_g20_product"]:
        m = g20[(g20["product"] == p["gsi_g20_product"]) & (g20["origin_iso"] == iso)]
        if len(m):
            au = "Australia" in set(m["importer"])
            ev.append(f"GSI 2023 Importing Risk lists {product} from {ref['iso_name'].get(iso, iso)} as at risk of forced labour "
                      f"(in the imports of {m['importer'].nunique()} G20 countries{', incl. Australia' if au else ''})")
    dol = ref["dol"]
    if dol is not None and isinstance(p["dol_good_names"], str):
        goods = [x.strip().lower() for x in p["dol_good_names"].split("|")]
        m = dol[(dol["iso_code"] == iso) & (dol["good"].str.lower().isin(goods))]
        for _, r in m.iterrows():
            ev.append(f"US DOL List of Goods {r['edition']}: {r['good']} from {r['country']} ({r['exploitation_type']})")
    ds = ref.get("dol_ds")
    if ds is not None and isinstance(p.get("dol_downstream_names"), str) and p["dol_downstream_names"]:
        names = [x.strip().lower() for x in p["dol_downstream_names"].split("|")]
        m = ds[(ds["downstream_iso"] == iso) & (ds["downstream_good"].str.lower().isin(names))]
        for _, r in m.drop_duplicates(["downstream_good", "input_good", "input_iso"]).iterrows():
            kinds = "; ".join(k for k, b in [("child labor", r["child_labor"]), ("forced labor", r["forced_labor"])] if b)
            ev.append(f"US DOL downstream goods {r['edition']}: {r['downstream_good']} made in {r['downstream_country']} "
                      f"may contain {r['input_good']} from {ref['iso_name'].get(r['input_iso'], r['input_iso'])} ({kinds})")
    return ev


def product_anywhere(product: str, prods: pd.DataFrame, ref: dict) -> list[str]:
    p = prods.set_index("product").loc[product]
    isos = set()
    if isinstance(p["gsi_g20_product"], str) and p["gsi_g20_product"]:
        isos |= set(ref["g20"].loc[ref["g20"]["product"] == p["gsi_g20_product"], "origin_iso"])
    if ref["dol"] is not None and isinstance(p["dol_good_names"], str):
        goods = [x.strip().lower() for x in p["dol_good_names"].split("|")]
        isos |= set(ref["dol"].loc[ref["dol"]["good"].str.lower().isin(goods), "iso_code"])
    return sorted(i for i in isos if isinstance(i, str))


def screen(reg: pd.DataFrame, settings: dict, prods: pd.DataFrame, ref: dict, matches: dict | None = None) -> pd.DataFrame:
    total = reg["net_spend"].sum()
    reg = reg.copy()
    reg["rank"] = range(1, len(reg) + 1)
    reg["spend_share"] = reg["net_spend"] / total
    reg["cumulative_share"] = reg["spend_share"].cumsum()
    thr = settings["core_population_spend_share"]
    reg["core_population"] = reg["cumulative_share"].shift(fill_value=0) < thr  # includes the vendor that crosses the threshold
    nominated = {vendor_key(x) for x in settings.get("user_nominated_vendors", [])}

    bases, indicators = [], []
    for _, r in reg.iterrows():
        b, ind = [], []
        if r["core_population"]:
            b.append("material expenditure")
        # country indicators: sourcing countries first, then domicile (labelled as such)
        for iso in [x for x in r["sourcing_iso"].split(";") if x]:
            ev = country_evidence(iso, ref)
            if ev:
                b.append("country indicator"); ind.append(f"[sourcing country] {ev}")
        for iso in [x for x in r["domicile_iso"].split(";") if x]:
            ev = country_evidence(iso, ref)
            if ev:
                b.append("country indicator"); ind.append(f"[vendor domicile, not necessarily sourcing] {ev}")
        # product x country
        prod_list = [x for x in r["products"].split(";") if x]
        check_isos = [x for x in r["sourcing_iso"].split(";") if x] or [x for x in r["domicile_iso"].split(";") if x]
        basis_iso_label = "sourcing" if r["sourcing_iso"] else "vendor domicile"
        for p in prod_list:
            hit = False
            for iso in check_isos:
                ev = product_country_evidence(p, iso, prods, ref)
                if ev:
                    hit = True
                    b.append("product or commodity indicator")
                    ind += [f"[{basis_iso_label}] {x}" for x in ev]
            if not hit and not r["sourcing_iso"]:
                anywhere = product_anywhere(p, prods, ref)
                if anywhere:
                    b.append("product or commodity indicator")
                    names = ", ".join(ref["iso_name"].get(i, i) for i in anywhere[:8]) + ("…" if len(anywhere) > 8 else "")
                    ind.append(f"{p}: listed as at-risk from {names}; origin of this supplier's goods not stated")
        if r["labour_intensive"]:
            if r["sector_alone_elevates"]:
                b.append("sector indicator"); ind.append(f"labour-intensive activity: {r['sector']}")
            else:
                ind.append(f"labour-intensive activity: {r['sector']} (noted; does not on its own select the vendor)")
        if r["labour_hire_category"] or r["labour_hire_keyword"]:
            b.append("vulnerable workforce indicator"); ind.append("labour hire, subcontracting or agency labour")
        if r["vendor_key"] in nominated:
            b.append("user-directed review")
        m = (matches or {}).get(r["vendor_name"], {})
        for x in m.get("enforcement", []):
            if x["decision"] == "confirmed":
                b.append("government or regulatory indicator")
                ind.append(f"{x['list']} (confirmed match): {x['matched_name']} - {x['detail']}")
            else:
                b.append("possible enforcement-list match - requires confirmation")
                ind.append(f"{x['list']} possible match ({x['score']:.0f}%): {x['matched_name']} - {x['detail']}. Confirm or reject in config/entity_match_decisions.csv")
        # CBP orders that cover a whole product or region (e.g. Turkmenistan cotton): product x country check
        for x in cbp_product_orders(r, ref):
            b.append("government or regulatory indicator"); ind.append(x)
        bases.append(sorted(set(b), key=b.index))
        indicators.append(ind)
    reg["selection_basis"] = bases
    reg["indicators"] = indicators
    reg["selected_for_detailed_review"] = reg["selection_basis"].map(bool)
    reg["selected_by_exception_only"] = reg["selected_for_detailed_review"] & ~reg["core_population"]
    reg["due_diligence_priority"] = "To be determined after supplier research (stage 4)"
    reg["entity_matches"] = reg["vendor_name"].map(lambda v: (matches or {}).get(v, {}).get("enforcement", []))
    reg["uk_statement_candidates"] = reg["vendor_name"].map(lambda v: (matches or {}).get(v, {}).get("uk_statements", []))
    return reg


def cbp_product_orders(r, ref) -> list[str]:
    """Active CBP orders whose merchandise matches this vendor's goods in its sourcing (else domicile) country."""
    cbp = ref.get("cbp")
    if cbp is None or not r["products"]:
        return []
    isos = [x for x in r["sourcing_iso"].split(";") if x] or [x for x in r["domicile_iso"].split(";") if x]
    out = []
    words = {"garments": r"garment|apparel|cotton", "textiles": r"textile|cotton|yarn", "electronics": r"electronic|laptop|computer",
             "solar panels": r"silic|polysilicon|solar", "fish": r"fish|seafood|tuna|shrimp", "rubber gloves": r"glove",
             "timber": r"timber|wood", "coffee": r"coffee", "cocoa": r"cocoa", "palm oil": r"palm", "sugarcane": r"sugar",
             "gold": r"gold", "cattle": r"cattle|beef"}
    for p in r["products"].split(";"):
        pat = words.get(p)
        if not pat:
            continue
        # only orders that cover a whole country, region or product class; orders against named producers are
        # handled by entity matching, not applied to every supplier in the country
        wide = cbp["entity"].str.contains(r"all|produced in|region|autonomous|artisanal|fields", case=False, regex=True)
        m = cbp[wide & cbp["iso_code"].isin(isos) & cbp["status"].str.startswith("Active")
                & cbp["merchandise"].str.contains(pat, case=False, regex=True)]
        for _, o in m.iterrows():
            out.append(f"US CBP {o['wro_or_finding']} ({o['effective_date']}, {o['status']}): {o['merchandise']} - {o['entity']} "
                       f"[region- or product-wide order; check whether this supplier's goods or inputs originate there]")
    return out


def reference_status() -> dict:
    """Versions and freshness of the reference data, from the last refresh.py run."""
    f = ROOT / "data_status.json"
    if not f.exists():
        return {"line": "Reference data status unknown: run python refresh.py first.", "all_current": False}
    d = json.loads(f.read_text(encoding="utf-8"))
    parts, ok = [], True
    for k, s in d["sources"].items():
        ok &= s["status"] == "current"
        ed = s.get("edition") or ", ".join(f"{c} {p.get('saved', 'missing')}" for c, p in s.get("pages", {}).items())
        parts.append(f"{k.upper()} {ed} [{s['status']}]")
    return {"line": f"Reference data (refresh {d['refreshed_at'][:16]}): " + "; ".join(parts), "all_current": ok,
            "sources": {k: {"status": s["status"], "edition": s.get("edition")} for k, s in d["sources"].items()}}


def indicator_rationale() -> str:
    """Cited evidence for the sector and vulnerable-workforce indicators (Global Estimates key figures)."""
    f = ROOT / "reference" / "gems_2022_key_figures.csv"
    if not f.exists():
        return ""
    k = pd.read_csv(f, dtype=str).set_index("figure_id")
    g = lambda i: k.loc[i]
    return (f"Why sector and workforce indicators: the ILO/Walk Free/IOM Global Estimates of Modern Slavery (2022) find that five sectors "
            f"account for {g('five_sectors_share')['value']}% of adult forced labour exploitation (services excl. domestic work "
            f"{g('sector_services')['value']}%, manufacturing {g('sector_manufacturing')['value']}%, construction {g('sector_construction')['value']}%, "
            f"agriculture {g('sector_agriculture')['value']}%, domestic work {g('sector_domestic_work')['value']}%; report p. {g('sector_services')['printed_page']}), "
            f"and that adult migrant workers' forced labour prevalence is more than {g('migrant_multiplier')['value']} times that of non-migrants "
            f"(p. {g('migrant_multiplier')['printed_page']}).")


# --------------------------------------------------------------------------- outputs

def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def entity_cell(r) -> str:
    parts = []
    for x in r["entity_matches"]:
        tag = "CONFIRMED" if x["decision"] == "confirmed" else "possible match, confirm"
        parts.append(f'<li><b>{esc(x["list"])}</b> ({tag}, {x["score"]:.0f}%): {esc(x["matched_name"])}<div class="m">{esc(x["detail"])}</div></li>')
    for x in r["uk_statement_candidates"]:
        tag = "confirmed" if x["decision"] == "confirmed" else "possible match"
        parts.append(f'<li>UK statement ({tag}): <a href="{esc(x["url"])}">{esc(x["matched_name"])} {esc(x["statement_year"])}</a></li>')
    return f"<ul>{''.join(parts)}</ul>" if parts else ""


def write_html(res: pd.DataFrame, summary: dict, path: Path):
    rows = []
    for _, r in res.iterrows():
        isos = [x for x in (r["sourcing_iso"] + ";" + r["domicile_iso"]).split(";") if x]
        cards = " ".join(f'<a href="{(CARDS / (i + ".html")).as_uri()}">{esc(i)}</a>' for i in dict.fromkeys(isos)
                         if (CARDS / f"{i}.html").exists())
        sel = "core" if r["core_population"] else ("exception" if r["selected_by_exception_only"] else "")
        rows.append(
            f'<tr class="{sel or "unsel"}"><td>{r["rank"]}</td><td><b>{esc(r["vendor_name"])}</b><div class="m">{esc(r["category"])}</div></td>'
            f'<td class="n">{r["net_spend"]:,.0f}</td><td class="n">{r["cumulative_share"]:.0%}</td>'
            f'<td>{esc(r["domicile_iso"]) or "<span class=m>missing</span>"}</td><td>{esc(r["sourcing_iso"]) or ("<span class=m>not stated</span>" if r["goods_or_services"] == "goods" else "<span class=m>n/a (services)</span>")}</td>'
            f'<td>{esc(r["products"].replace(";", ", "))}</td>'
            f'<td>{"<br>".join(esc(x) for x in r["selection_basis"]) or "<span class=m>not selected</span>"}</td>'
            f'<td><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["indicators"])}</ul></td>'
            f'<td><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["information_gaps"])}</ul></td>'
            f'<td>{entity_cell(r)}</td><td>{cards}</td></tr>')
    s = summary
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Supplier screening</title><style>
:root{{--bg:#f7f7f5;--p:#fff;--i:#1d1f21;--m:#6b7075;--l:#e3e3df;--a:#2f5d8a;--core:#eef3fa;--exc:#fdf3e1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141618;--p:#1c1f22;--i:#e6e6e3;--m:#9aa0a6;--l:#2c3034;--a:#8fb4dc;--core:#1d2a38;--exc:#3a2f1a}}}}
body{{margin:0;background:var(--bg);color:var(--i);font:14px/1.45 system-ui,Segoe UI,sans-serif}}main{{max-width:1500px;margin:0 auto;padding:20px 16px}}
a{{color:var(--a)}}.m{{color:var(--m);font-size:12px}}.n{{text-align:right;white-space:nowrap}}
.box{{background:var(--p);border:1px solid var(--l);border-radius:8px;padding:12px 16px;margin:12px 0}}
.kp{{display:flex;flex-wrap:wrap;gap:24px}}.kp div b{{display:block;font-size:22px}}
table{{border-collapse:collapse;width:100%;background:var(--p);font-size:13px}}th,td{{border-bottom:1px solid var(--l);padding:6px 8px;vertical-align:top;text-align:left}}
th{{position:sticky;top:0;background:var(--p);color:var(--m)}}tr.core{{background:var(--core)}}tr.exception{{background:var(--exc)}}
ul{{margin:0;padding-left:16px}}.warn{{border-left:4px solid #c08a2b}}
label{{margin-right:12px}}</style></head><body><main>
<h1>Supplier screening: stages 1–3</h1>
<div class="box warn"><b>Prioritisation, not determination.</b> This screening identifies which suppliers warrant closer due diligence and why.
Country, product and sector indicators are not evidence that modern slavery exists at any supplier. Not being selected does not mean low risk.
Sourcing countries come only from the spend data; a vendor's domicile is not treated as where goods are made.
Due diligence priority is set after supplier research (stage 4). {"<b>SYNTHETIC TEST DATA.</b>" if s.get("synthetic") else ""}</div>
<div class="box kp"><div><b>{s['vendors']}</b>vendors</div><div><b>{s['currency']} {s['total_spend']:,.0f}</b>net spend, {esc(s['period'])}</div>
<div><b>{s['core_vendors']}</b>core vendors ({s['core_share']:.0%} of spend)</div><div><b>{s['exception_vendors']}</b>added by exception ({s['exception_share']:.1%} of spend)</div>
<div><b>{s['not_selected_vendors']}</b>not individually selected ({s['not_selected_share']:.0%} of spend)</div>
<div><b>{s.get('entity_matches_to_review', 0)}</b>entity-list / statement matches to confirm: <a href="entity_match_review.html">open the review page</a></div></div>
<div class="box"><b>Conventions used</b> (editable in config/settings.json): core population = vendors covering {s['core_threshold']:.0%} of spend; country indicator = GSI 2023 prevalence ≥ {s['prevalence_threshold']:.1f} per 1,000
(top third of 160 countries) or vulnerability ≥ {s['vulnerability_threshold']}%. Product × country sources: {esc(', '.join(s['product_sources']))}.
<div class="m">{esc(s.get('indicator_rationale',''))}</div><div class="m">{esc(GSI_CREDIT)}. Run {esc(s['run_at'])}.</div><div class="m">{esc(s['reference_data']['line'])}</div></div>
<div class="box"><label><input type="checkbox" id="f" onchange="document.querySelectorAll('tr.unsel').forEach(t=>t.style.display=this.checked?'none':'')"> Show only selected vendors</label>
<span class="m">Blue = core population (material spend); amber = added by exception screening.</span></div>
<table><thead><tr><th>#</th><th>Vendor / category</th><th>Net spend</th><th>Cum.</th><th>Domicile</th><th>Sourcing (stated)</th><th>Goods</th><th>Selection basis</th><th>Indicators</th><th>Information gaps</th><th>Entity lists / statements</th><th>Country cards</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></main></body></html>"""
    path.write_text(body, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spend_file", type=Path)
    ap.add_argument("--config", type=Path, default=HERE / "config" / "settings.json")
    ap.add_argument("--out", type=Path, default=HERE / "output")
    args = ap.parse_args(argv)
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    cats = pd.read_csv(HERE / "config" / "categories.csv", dtype={"gl_code": str})
    prods = pd.read_csv(HERE / "config" / "products.csv", keep_default_na=False)
    ref = load_reference(settings)

    sf = settings["spend_file"]
    spend = (pd.read_excel(args.spend_file, sheet_name=sf.get("sheet", 0)) if args.spend_file.suffix.lower() in (".xlsx", ".xls")
             else pd.read_csv(args.spend_file, encoding="utf-8-sig", keep_default_na=False))
    reg, unknown_gl = build_register(spend, settings, cats, prods, ref)
    matches = entity_match.match_vendors(reg["vendor_name"].tolist())
    res = screen(reg, settings, prods, ref, matches)

    total = res["net_spend"].sum()
    sel = res[res["selected_for_detailed_review"]]
    exc = res[res["selected_by_exception_only"]]
    run_at = dt.datetime.now().isoformat(timespec="seconds")
    summary = {
        "run_at": run_at, "spend_file": str(args.spend_file), "synthetic": "synthetic" in args.spend_file.name.lower(),
        "currency": sf["currency"], "period": sf["period"],
        "spend_rows": int(len(spend)), "vendors": int(len(res)), "total_spend": float(total),
        "core_threshold": settings["core_population_spend_share"],
        "core_vendors": int(res["core_population"].sum()), "core_share": float(res.loc[res["core_population"], "net_spend"].sum() / total),
        "exception_vendors": int(len(exc)), "exception_share": float(exc["net_spend"].sum() / total),
        "selected_vendors": int(len(sel)),
        "not_selected_vendors": int((~res["selected_for_detailed_review"]).sum()),
        "not_selected_share": float(res.loc[~res["selected_for_detailed_review"], "net_spend"].sum() / total),
        "prevalence_threshold": ref["prev_threshold"], "vulnerability_threshold": settings["country_indicator"]["vulnerability_pct"],
        "product_sources": ["GSI 2023 G20 Importing Risk"] + (["US DOL List of Goods"] if ref["dol"] is not None else []),
        "unknown_gl_codes": unknown_gl,
        "reference_data": reference_status(),
        "indicator_rationale": indicator_rationale(),
        "spend_by_category": res.groupby("category")["net_spend"].sum().sort_values(ascending=False).round(0).to_dict(),
        "spend_by_domicile": res.groupby("domicile_iso")["net_spend"].sum().sort_values(ascending=False).round(0).to_dict(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    flat = res.copy()
    for c in ("entity_matches", "uk_statement_candidates"):
        flat[c] = flat[c].map(lambda v: " | ".join(f"{x['list']}: {x['matched_name']} ({x['score']:.0f}%, {x['decision']})" for x in v))
    for c in ("selection_basis", "indicators", "information_gaps"):
        flat[c] = flat[c].map(lambda v: " | ".join(v))
    flat.to_csv(args.out / "screening.csv", index=False, encoding="utf-8-sig")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    n_queue = entity_match.write_review_queue(matches, args.out / "entity_match_review.csv")
    import review_page
    review_page.write_page(res, args.out, run_at)
    summary["entity_matches_to_review"] = n_queue
    write_html(res, summary, args.out / "screening.html")
    print(f"{summary['vendors']} vendors; core {summary['core_vendors']} ({summary['core_share']:.0%}); "
          f"exceptions {summary['exception_vendors']}; not selected {summary['not_selected_vendors']} ({summary['not_selected_share']:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
