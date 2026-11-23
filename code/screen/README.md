# Supplier register and screening (stages 1–3)

This implements the deterministic part of the screening method in `../Modern Slavery Supply Chain Screening.md`. No LLM is involved. It does not assign a due diligence priority: that comes after supplier research (stage 4), which is not built yet.

```bash
python screen.py ../synthetic/data/spend_fy2025_synthetic.xlsx
```

Outputs go to `output/`: `screening.html` (a reviewable table), `screening.csv` and `summary.json`.

## What it does

1. **Register.** Reads the spend file (column mapping in `config/settings.json`) and builds one entry per vendor ID with net spend (credits netted), category, sector and goods/services from the GL code (`config/categories.csv`). Products come from description keywords (`config/products.csv`). The vendor's domicile country comes from the spend file. The **sourcing country is only taken where the description names it** and is never inferred from domicile. Vendor records whose names normalise to the same key are flagged as possible duplicates, not merged.
2. **Stage 1.** Ranks by spend, then computes cumulative share and spend by category and country. Information gaps are flagged: missing or unrecognised country, sourcing not stated for goods, blank descriptions, credit notes, possible duplicates, unmapped GL codes.
3. **Stage 2.** The core population is the vendors that cover 80% of spend, including the one that crosses the line. This is a convention, not a risk threshold.
4. **Stage 3.** Exception screening outside the core:
   - **Country indicator:** the GSI 2023 prevalence is in the top third of 160 countries (≥ 7.1 per 1,000), or vulnerability is ≥ 50%. Sourcing countries are checked first, then domicile, and each indicator is labelled with which one it is.
   - **Product × country:** the GSI 2023 Importing Risk pairs. The US DOL List of Goods is added automatically once `../dol/data/dol.sqlite` exists. If origin is unknown, the tool lists the countries where the product is flagged.
   - **Sector:** the labour-intensive activities in the method. Only categories marked `sector_alone_elevates` select a vendor on their own; the others are noted.
   - **Vulnerable workforce:** labour hire, subcontracting and agency labour, from the category or from description keywords.
   - **User-directed:** vendors named in `user_nominated_vendors`.
   - **Entity lists:** possible matches against the US CBP orders/findings and the UFLPA Entity List. A person confirms each one via `config/entity_match_decisions.csv`, and the review queue is in `output/entity_match_review.csv`. CBP orders that cover a whole region or product (e.g. XUAR cotton) are checked against the supplier's goods and country. UK registry statements are linked for information. See `../entities/README.md`.
   - **Goods from the GL code:** when the description is blank, goods are inferred from the GL category (`default_products`), and this is flagged as an information gap.

Every convention can be edited in `config/` and is printed at the top of the output.

## Synthetic test data

`../synthetic/make_spend.py` generates a fictional AP extract: AUD, FY2025, 160 rows, 155 vendor IDs, about AUD 52m. It includes 19 planted cases, listed in `../synthetic/data/planted_cases.csv`. All 18 risk cases are selected. The 19th is a UK statement lookup, which is information only and not a selection basis. Three of the planted cases use **real names from public lists or the UK registry, purely to test matching**: the fictional company never bought from them, and nothing in the file says these entities supplied anyone. Every other name and amount is invented.

## Known limits

- Product detection is keyword-based. Real AP descriptions are poorer, so expect to add a manual classification step (a user-editable override file) for real data.
- The Australian MSA register isn't matched yet; it is planned as a stage 4 lookup.
- `products.csv` maps products to exact DOL 2024 good names (`dol_good_names`, `dol_downstream_names`); check these when a new DOL edition is loaded.
