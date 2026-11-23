# Handoff: thematic modern slavery assessment of an export credit portfolio

## Your role and how to work with me

You are helping me run a thematic modern slavery risk assessment of an export credit portfolio: Export Finance Australia's FY26 exposure. I will give you the exposure data, a set of Python files from a supply chain screening tool I built elsewhere, and reference data files. This document explains the concepts and the decisions already made. How you implement them is up to you.

Work in stages and stop at the end of each one so I can review before you continue. Before you write any code, read this document and the files I give you. Then tell me your plan for the stage, what you need from me, and anything here that you think is wrong or that won't work in this environment. Don't silently work around a constraint. Tell me about it.

Be direct. If something I've asked for is a bad idea, say so and explain why.

## Environment constraints

- You can run Python in a sandbox, but the sandbox has **no internet access**. All screening must run offline against the reference files I provide.
- Web search is available in a normal Copilot chat session, not inside the Python sandbox. Web research is a separate stage that runs in separate sessions (see Stage 4).
- The exposure data is confidential. Never put exposure amounts, or the list of which customers were flagged, into a web search. Searches may contain only a customer name, plus industry and country where that helps.
- Before building anything, check the sandbox. Report the Python version, whether pandas, sqlite3, rapidfuzz and openpyxl are available, and any upload or file size limits. If rapidfuzz isn't available, use difflib from the standard library for fuzzy matching.

## Inputs

1. **Exposure data (FY26).** One row per facility × underlying country. Fields include: customer name, ANZSIC industry of the underlying activity the facility supports, country of that underlying activity, product type, facility limit, and drawn exposure. NAICS codes are available if ANZSIC mapping turns out to be a problem. Ask me if you need them.
2. **Python files from the existing tool, for reference.** Use them for logic and conventions. Don't run them unchanged, because they were built for supplier spend files.
   - `screen.py`: deterministic screening (population review, materiality, exception screening against reference data).
   - `entity_match.py`: name normalisation and fuzzy matching against enforcement lists, with a human confirmation step.
   - `research.py` and the method document (`Modern Slavery Supply Chain Screening.md`, `How supplier research works.md`): the research prompts, profile structure and priority bands for stage 4.
3. **Reference data**, as SQLite databases and/or CSV tables:
   - Global Slavery Index 2023: country prevalence, vulnerability and government response, plus G20 at-risk imports. Credit: "Global Slavery Index 2023 Dataset, Minderoo Foundation".
   - US DOL List of Goods Produced by Child Labor or Forced Labor, 2024. This includes `dol_goods` (good × country) and `dol_downstream` (listed input → downstream good made elsewhere, e.g. polysilicon from China into solar products).
   - CBP Withhold Release Orders and Findings, and the UFLPA Entity List.
   - ILO forced labour convention ratifications (NORMLEX) and country data.
4. **NSW Inherent Risk Identification Tool v2.0**, a file I'll supply for Stage 1b.

## Core concepts

### Transactions are not spend

The existing tool screens supplier spend. This is a portfolio of financing, so three things change:

1. **Where the risk sits.** For each row, the risk can sit in (a) the customer's own operations or workforce, (b) the project workforce, including EPC contractors and subcontractors, (c) upstream inputs to the financed activity, or (d) the trade flow being financed. Record which of these applies to each row as a "risk locus". The exposure data's underlying industry and country make this much easier than the public register would, but the product type still matters. For example, a risk participation with a foreign bank, an import contract for difference and a project loan are different kinds of exposure.
2. **Dollar materiality is not risk.** The existing tool's "80% of spend" core population is a prioritisation convention. Here, a few very large facilities (fuel, energy, project finance) would dominate it. Report exposure concentration, but don't use a dollar cut as the main selection rule. Selection should be driven by the exception indicators, with exposure used to rank within them.
3. **Inputs matter as much as location.** "Electricity generation, Thailand" scores on Thai country risk. But the main forced labour risk for a solar project is the polysilicon in its modules, which isn't Thai. Screening therefore needs an **input-risk overlay**: a table mapping industries to known high-risk inputs or workforces. Examples:
   - solar → polysilicon (China)
   - batteries → cobalt (DRC)
   - construction → migrant and recruited labour
   - fuel imports → seafarers
   - seafood → fishing crews
   - horticulture → seasonal and visa-dependent workers
   - apparel, footwear and leather → cotton and tanning

   This table is built in Stage 1b. Keep it as a separate, visible table with a source or rationale for every row, so it can be challenged.

### Industry × country is the main signal; customer name is the check

Searching by customer name alone is weak, for four reasons:
- Many customers are financing vehicles, funds, banks or SPVs, not the operator.
- Risk often sits below the customer (inputs, contractors).
- Most small customers have no web footprint, so a clean search usually means no coverage, not low risk.
- Enforcement lists are short and mostly name non-Australian entities.

So inherent risk comes from industry × country plus the input overlay. Customer names are used for enforcement-list matching (offline) and for confirming or escalating in stage 4.

### Indicators, not conclusions

Follow the existing tool's principles:
- Screening produces indicators and a selection basis. It does not assign a due diligence priority.
- A reference-data listing is a product and country indicator, not evidence about any particular customer.
- Never state that modern slavery is present or absent.
- Priority bands come only after research, are proposals, and must be confirmed by a person.
- Fuzzy entity matches are "possible" until I confirm or reject them.

## Stages

### Stage 1: Load and reconcile (offline, Python)

Load the exposure data and the reference data. Map ANZSIC codes to the categories used by DOL goods and the overlay. Show me the mapping and flag anything uncertain, because this mapping is the biggest judgement in the screening. Map countries to ISO codes.

**Reconciliation is mandatory.** Print the row count, total facility limit and total drawn exposure in, and the same after every transformation. If anything is dropped, merged or unmapped, list it. I'll compare these numbers against my source.

### Stage 1b: Build the input-risk overlay (offline, Python plus judgement)

Build the overlay table described under "Inputs matter as much as location" before any screening runs. Stage 2 depends on it.

Sources, in this order:
1. **DOL downstream goods** (`dol_downstream` in the reference data): listed inputs and the downstream goods made with them.
2. **NSW Anti-slavery Commissioner's Inherent Risk Identification Tool (IRIT) v2.0.** I'll download it and supply it as a file, because the sandbox has no internet. It rates risk by NSW procurement category (the "Spend Cube" taxonomy), not by industry. Mapping its categories to ANZSIC is therefore a judgement step, so show the mapping. Tell me what the file contains and how it expresses risk before deciding how to use it.
3. **Verité Responsible Sourcing Tool**, if I can supply extracts.
4. **Judgement**, only where the sources above leave gaps. Label each of these rows "judgement" and give the reasoning.

Each overlay row should hold:
- the ANZSIC class or classes it applies to
- the input or workforce at risk
- the origin countries of that input, where known
- the risk type (forced labour, child labour, or recruitment/debt bondage)
- the source and its date
- a short rationale
- your confidence: high, medium or low

Only include ANZSIC classes that actually appear in the exposure data. Don't build a universal table.

Stop for my review. I expect to correct this table. Stage 3a may later propose changes to it, which also need my confirmation.

### Stage 2: Screening (offline, Python)

For each row:
- country indicators (GSI and others)
- industry × country indicators (DOL goods)
- input-overlay indicators (from the confirmed Stage 1b table)
- labour-intensive or vulnerable-workforce indicators
- possible matches against the enforcement lists (CBP, UFLPA)
- risk locus

Aggregate to customer level as well, since a customer can have several rows.

Output: a row-level and customer-level table with the indicators and the selection basis, plus a review queue of possible entity matches for me to confirm.

### Stage 3: Thematic view (offline, Python)

Group exposure into themes, for example:
- renewables and the solar supply chain
- construction and infrastructure with migrant labour
- seafood and fishing
- agriculture and horticulture
- apparel, footwear and leather
- mining and critical minerals
- fuel and shipping
- defence and shipbuilding
- trade finance for agricultural commodities

Propose the theme list from the data rather than forcing these.

For each theme, show: facility limit and drawn exposure, number of customers, main countries, which indicators drive it, and risk locus. Rank themes by inherent risk, with exposure shown alongside rather than multiplied into a single score.

This stage is a deliverable on its own. State plainly that it shows **inherent risk only** and says nothing about how well any customer manages it.

Then propose a provisional research sample for each theme: the largest exposures, anything with a confirmed or possible enforcement-list match, and a few representative mid-sized customers. Also list customers that can't be assessed for lack of data. The sample is confirmed after Stage 3a.

### Stage 3a: Theme-level web research (Copilot chat session with web search)

Research each theme as a whole before researching any individual customer. These searches use **no customer names**. They cover only the theme, its industries, its main countries and its key inputs. That makes this the lowest-risk web step from a confidentiality point of view.

For each theme, look for recent evidence, preferring the last three years. Good sources are ILO and UN bodies, government enforcement and trade actions, credible NGO and academic research, investigative journalism, and sector initiatives. Produce a short theme brief covering:
- **Risk mechanisms:** how modern slavery typically arises in this theme, e.g. recruitment fees and debt bondage, retained passports, state-imposed forced labour in an input, or isolation at sea.
- **Who is affected:** which worker groups and where, including tiers below the financed entity.
- **Key inputs and geographies:** whether the evidence supports the input-overlay rows for this theme, or suggests adding, changing or removing any. Present these as proposed changes for me to confirm. Don't edit the overlay directly.
- **Recent enforcement and incidents:** withhold release orders, UFLPA additions, prosecutions, and major reports, with dates.
- **What good management looks like** in this theme, e.g. IFC Performance Standard 2, Employer Pays principle, traceability for a specific input. This is the benchmark for Stage 4.
- **Questions for customer research:** the specific things Stage 4 should look for in this theme's customers.
- **Effect on the inherent risk picture:** whether the evidence supports, raises or lowers the Stage 3 ranking for this theme, and why.

Apply the same source controls as Stage 4: a source table with URL, title, date accessed and a short verbatim quote for every finding, with unquoted findings labelled unverified. End each brief with a footer giving the number of searches, the number of sources and the main gaps. Do one theme per session, or two at most.

After the briefs, propose any changes to the overlay table and the research sample, and stop for my review. The confirmed briefs become the theme context given to every Stage 4 session for customers in that theme.

### Stage 4: Web research (Copilot chat sessions with web search, separate from the Python sessions)

There are two tiers:
- **Light, for every customer:** 2–3 searches each covering adverse media, enforcement actions, and whether the customer publishes a modern slavery statement (Australian register, UK registry).
- **Full, for the theme samples only:** follow the research and profile structure in the method document, adapted to financed activity. Look at the operator and the project rather than just the borrowing entity, at EPC contractors and subcontractors, recruitment fees and practices, worker accommodation, grievance mechanisms, IFC Performance Standard 2 where it applies, upstream inputs from the overlay, and any public environmental and social impact assessment.

Give each full-research session the confirmed Stage 3a brief for the customer's theme. Assess the customer against that brief's risk mechanisms and its "what good management looks like" benchmark, and answer its questions for customer research.

Controls, because these sessions don't capture source pages automatically:
- Every finding cites its source in a table: URL, title, date accessed, and a short verbatim quote supporting the finding. A finding without a quote is labelled unverified.
- Every profile ends with a fixed footer: customer name, number of searches run, number of sources cited, and the main information gaps.
- Research in batches of about 5 customers per session, and keep a tracker of what's done. Before scaling up, I'll test drift by running 10 customers in one session and comparing the first profile with the last.
- Before full research on the whole sample, I'll pilot it on 3–5 customers I know well.

### Stage 5: Synthesis

Combine the thematic view, the Stage 3a theme briefs and the customer research findings. Show for each theme whether the customer evidence confirms, moderates or raises the inherent risk picture. Give proposed priority bands for the researched customers, each with its rationale and how the proposal could be wrong. State the limitations: inherent-risk data, coverage gaps, unverified findings, and the outside-in nature of web evidence.

## What I want from you first

1. Your understanding of the task in a few lines.
2. The sandbox check results.
3. Your plan for Stage 1, including how you'll handle the ANZSIC mapping.
4. Any concerns or disagreements with the approach above.

Don't start Stage 1 until I reply.
