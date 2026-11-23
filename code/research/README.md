# Stage 4: supplier research

The **core** researches one supplier. **Lookup mode** runs it on a name you type in. **Batch mode** runs it on the suppliers the screening selected.

```bash
python research.py lookup "Supplier name" --country MY --goods "nitrile gloves" --identifier "ABN 12 345 678 901"
```

```bash
python research.py batch --limit 5
```

```bash
python research.py batch --only "Supplier A" --only "Supplier B"
```

To build and save the prompts and context without calling the API, add `--dry-run` to either mode.

## What happens for one supplier

1. **Context from our own data.** This covers spend and screening indicators (batch mode), entity-list matches, UK registry statements, an Australian register search link, and, in lookup mode, country and product×country indicators for the country and goods you give.
2. **Research call.** Claude Opus 5.5 runs under your screening method (`../Modern Slavery Supply Chain Screening.md`, used as the system prompt) plus a stage 4 addendum. It uses server-side web search and web fetch. Every result the model actually received is captured into `sources.json` (URL, title, page age, retrieval time, and a SHA-256 of fetched text), and the research notes cite those URLs.
3. **Profile call.** Structured output turns the notes into `profile.json`: entity, locations, labour model, findings with evidence types, governance levels (commitment → process → implementation → outcomes), information gaps, a proposed priority band with its rationale and **how it could be wrong**, recommended actions, and limitations.
4. **Citation check.** Any citation that isn't a captured source is reported. So is any finding that rests only on URLs the model mentioned but that weren't captured as retrieved results. Both appear at the top of the profile page.
5. **Output.** Everything goes in `output/<date>_<supplier>/`: `profile.html` (read this), `profile.json`, `sources.json`, `research_notes.md`, `raw_research_response.json` and `context.json`.

The priority band is a **proposal**. It will go through the same review page as the entity matches before any report uses it (next step).

## Proportionate depth (batch mode)

- **full:** used for suppliers with any risk indicator beyond spend. Up to 8 searches and 8 page fetches, at high effort.
- **light:** used for suppliers selected on spend alone. Up to 3 searches and 3 fetches, at medium effort, covering entity, statement, enforcement and allegations.
- Use `--depth` to override. Lookup mode defaults to full.

## Backends

- **`claude_code` (default):** runs through the Claude Code CLI in headless mode (`claude -p`), so it uses your Claude subscription (Max plan) and needs no API key. Log the CLI in once: open a terminal, run `claude`, type `/login` and sign in. Search and fetch caps are instructions here, not hard limits, and there is no automatic refusal fallback. Code: `cc_backend.py`.
- **`api`:** `--backend api` uses the Anthropic API with an API key, billed separately (see Setup).

## Setup

- **API key:** set it in your own terminal, then open a new terminal. Don't paste the key into chat.

  ```bash
  setx ANTHROPIC_API_KEY "<your key>"
  ```

- **SDK version:** the code passes newer API parameters through `extra_body`, so it works with the installed `anthropic` package (0.69). Upgrading (`pip install -U anthropic`) is optional.
- **Cost:** indicative cost is shown on each profile, from token usage and the number of searches. Run a pilot of about 3–5 real suppliers you know well to measure cost and quality before any batch.

## Not yet verified

The code paths for source capture, citation checking and the profile page were tested offline with fake data. The live API calls haven't been run, because there is no API key on this machine yet. The first pilot will confirm the response shapes, especially how the web tools' dynamic filtering reports retrieved pages.
