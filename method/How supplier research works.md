# How supplier research works

23 Nov 2026 · AG. Live version: https://claude.ai/artifact/MkoZ8w8jnZJo85Bj9gFzRc (this file is a copy; the live document is the one to edit).

## In short

Supplier research produces a short, sourced profile of one supplier and proposes how closely that supplier should be looked at for modern slavery risk. An AI research assistant does the reading and drafting. Software controls what it is given, records every source it retrieves, and checks its citations. A person reviews the result before it is used.

The research answers one question: does this supplier warrant closer due diligence, and why? It does not decide whether modern slavery is occurring at a supplier.

It can be run for a single named supplier, or for the group of suppliers that the earlier screening of a company's spend selected for a closer look.

## Step by step

Each supplier goes through the same six steps. A full review takes a few minutes of computer time.

1. **Gather what we already know.** The software pulls together what our own data says about the supplier: what we buy from them and how much (when a spend file was screened), any risk flags for the country and goods involved, and any match against government enforcement lists.
2. **Decide how deep to go.** A supplier with a risk flag gets a full review, as does any supplier looked up individually by name. A supplier selected only because we spend a lot with them gets a lighter check of its identity, its published statements, and any enforcement action or allegations.
3. **Research on the web.** The AI assistant searches the web and opens the most relevant pages. It works to a written method that tells it what to look for, which kinds of sources to prefer, and how to describe what it finds.
4. **Record the sources.** The software, not the AI, keeps the list of every search result and page that was actually retrieved, and numbers them.
5. **Write the profile.** The AI turns its research notes into a profile in a fixed format, with each statement pointing to a numbered source. The software then checks that every source cited is one that was really retrieved, and flags any that is not at the top of the profile.
6. **Human review.** The profile ends with a proposed priority. A person must read the profile, open the key sources, and confirm or change that priority before it is used. For now that review is done by hand; the tool does not yet record it.

## The sources

The research draws on two kinds of source: reference data we hold and keep up to date, and whatever the AI finds on the open web for that supplier.

### Reference data we already hold

These are published datasets, downloaded from the publisher. A refresh is run by hand, and the tool flags when a source is due or a newer edition is out. The software checks the supplier against them and hands the results to the AI as background.

| Source | Publisher | What it tells us | Version held (last refresh 6 Nov 2026) |
| --- | --- | --- | --- |
| Global Slavery Index | Walk Free | Estimated prevalence of modern slavery and vulnerability, by country; products at risk in G20 imports | 2023 edition |
| List of Goods Produced by Child Labor or Forced Labor | US Department of Labor | Which goods from which countries are linked to child or forced labour | 2024 edition |
| Withhold Release Orders and Findings | US Customs and Border Protection | Named producers, goods and regions whose products are barred from US import over forced labour | Current orders, file of 29 Sep 2026 |
| UFLPA Entity List | US Department of Homeland Security | Named Chinese entities presumed to use forced labour | Page updated 28 Oct 2026 |
| Modern slavery statement registry | UK Home Office | Whether the supplier has filed a UK modern slavery statement, with a link to it | Statements for 2020 to 2027 |
| Modern Slavery Statements Register | Australian Government | The AI is given a search link to look the supplier up | Live website |

A name match against an enforcement list is treated as a possible match until a person confirms it is the same company.

### Open web research

The AI runs a limited number of searches and opens a limited number of pages: up to 8 of each for a full review, and up to 3 of each for a light check. The method tells it to prefer sources in this order:

1. **Primary and authoritative sources:** the supplier's own modern slavery statements, policies and annual reports; government, regulator and court records; the International Labour Organization and the United Nations.
2. **Established datasets and international bodies:** for example the OECD and UNICEF.
3. **Credible secondary sources:** reputable media, recognised human rights organisations, trade unions, and academic research. These are used mainly to find allegations and controversies.

It is told not to treat anonymous claims, unverified social media posts, or content with no stated evidence as established.

### How sources are logged and cited

- Every search result and every opened page is saved in a numbered source list with its web address, title and the time it was retrieved.
- Every statement in the profile cites one or more of those numbers, so a reader can click through to the source.
- Most of the list is search results. In our test runs a full review listed about 100 sources but opened only 7 or 8 pages.
- When a statement rests only on a search result summary, not an opened page, the profile says so and marks it "requires confirmation".

## Who decides what

The work is split three ways, so that the AI's judgement is boxed in by fixed rules on one side and human review on the other.

| | Does | Does not |
| --- | --- | --- |
| **The software** (fixed rules, same result every time) | Gathers our own data on the supplier; sets the depth of research; records the sources; checks citations; fixes the format of the profile | Read or interpret any source |
| **The AI assistant** (judgement, guided by the written method) | Chooses what to search for and which pages to open; reads and summarises them; labels each finding by type of evidence; lists what is unknown; proposes a priority | Decide the final priority. It is also instructed never to state that modern slavery is present or absent |
| **The reviewer** (a person) | Confirms enforcement-list matches; checks the key sources; confirms or changes the priority | Redo the research; they judge what the profile presents |

## What the profile contains

- **The supplier's identity:** legal entity, corporate group, and how confident we are that we have the right company.
- **What it supplies and where:** goods and services, and the places of incorporation, operation, manufacturing and sourcing. A registered office is not treated as the place goods are made.
- **Labour model:** use of subcontractors, labour hire and recruitment agents.
- **Findings,** each labelled by type of evidence: company-reported, allegation, media or NGO investigation, regulatory action, government finding, court judgment, country or product indicator, or our own analytical observation. Allegations are never presented as established facts.
- **Governance:** modern slavery statement, policies, audits, grievance channels, recruitment practices and remediation. Each is rated on how strong the evidence is, from "commitment stated" to "evidence of results". A policy on paper is not treated as proof it works.
- **Information gaps:** what is not known, why it matters, and what would resolve it.
- **Proposed priority,** one of three: priority for further due diligence; further enquiry warranted; routine screening or monitoring. It comes with the reasons, and a statement of how the proposal could be wrong.
- **Recommended next steps, limitations, and the full source list.**

## Limits to keep in mind

- **The priority is a proposal.** No rule or formula calculates it. It is the AI's reading of the evidence, and it only counts once a person has confirmed it.
- **The citation check proves a source was retrieved, not that it says what the profile claims.** The reviewer still needs to open the sources behind the important findings.
- **Results vary between runs.** Researching the same supplier twice gives similar but not identical profiles, because the AI may choose different searches and pages.
- **It is desktop research on public information.** It cannot see inside a supplier's operations. Finding nothing adverse is not evidence of low risk.
- **Coverage is shallow by design.** A handful of pages is opened per supplier, and the search and page limits are guidance to the AI, not a hard stop.
- **Our enforcement data holds current orders only.** An order that has since been lifted will not be in it, though the web research often finds it.
- **Public information can be out of date, incomplete, or about a similarly named company.** The profile states how sure it is about the supplier's identity for this reason.
- **It is not legal advice** and does not conclude whether any company has complied with a reporting law.
- **Sources are saved as links, not copies.** A page can change or disappear after the research was done.
- **Supplier details are sent to the AI service.** The supplier's name, country and goods, and spend figures where a spend file was screened, are part of what the AI is given.
