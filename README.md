# MSRisk: handoff pack for a thematic modern slavery assessment

These are the files for running the assessment in a Microsoft 365 Copilot session. Copilot can run Python in a sandbox with no internet access, and has web search in normal chat sessions.

Start with `HANDOFF_PROMPT.md` and give it to Copilot along with the rest of this folder. The exposure data is **not** included here and must never be added to this repository.

## Contents

| Path | What it is |
|---|---|
| `HANDOFF_PROMPT.md` | The prompt for Copilot: concepts, stages, controls |
| `code/screen/screen.py`, `entity_match.py` | Reference logic from the supplier spend screening tool (stages 1-3, entity matching). For Copilot to adapt, not to run unchanged |
| `code/screen/config/` | Example settings and the product → DOL goods mapping used by the spend tool |
| `code/research/research.py` | Reference for the stage 4 research prompts and profile structure (it calls the Anthropic API or Claude Code, which aren't available in Copilot) |
| `method/` | The screening method and how supplier research works |
| `reference/dol/` | US DOL List of Goods 2024: `dol_goods.csv` (good × country), `dol_downstream.csv` (input → downstream good) |
| `reference/gsi/` | Global Slavery Index 2023: country summary, G20 import risk |
| `reference/entities/` | CBP Withhold Release Orders/Findings, UFLPA Entity List, normalised entity names |
| `reference/ilo/` | ILO country list and forced labour convention ratifications (NORMLEX) |
| `reference/gems_2022_key_figures.csv` | ILO/Walk Free/IOM Global Estimates 2022 key figures (context only) |

Not included: the NSW Inherent Risk Identification Tool (download it yourself and supply it for Stage 1b), the UK Modern Slavery Statement Registry extract (too large; Stage 4 checks it by web), and research outputs from the spend tool.

## Sources and credits

- **Global Slavery Index 2023 Dataset, Minderoo Foundation, available from: www.globalslaveryindex.org.** Used under the Global Slavery Index Data Licence. No endorsement by Minderoo Foundation or Walk Free is implied.
- US Department of Labor, List of Goods Produced by Child Labor or Forced Labor (2024). US government work, public domain.
- US CBP Withhold Release Orders and Findings; DHS UFLPA Entity List. US government works, public domain.
- ILO NORMLEX ratification data. Check the ILO's terms of use before reusing it.
- Data as of 2026-11-06 unless the manifest files say otherwise. Refresh on the home machine with `refresh.py` and replace these files.

Reference listings are product and country indicators, not evidence about any particular company.
