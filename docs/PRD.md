# Paper Agent — PRD vNext
## Research-Question-Driven AI Literature Workspace

> **Document type:** Product Requirements Document  
> **Version:** vNext / Major Product Upgrade  
> **Repository context:** `SunWeizhou/ppr`, branch `codex/apple-claude-workspace-redesign`  
> **Product owner:** Weizhou  
> **Status:** Product direction locked through drill-me; ready for engineering planning

---

# 0. Executive Summary

Paper Agent is evolving from a local-first paper discovery and recommendation tool into a:

> **Research-question-driven AI literature workspace for graduate students and PhD researchers.**

Its purpose is not merely to search papers or summarize abstracts. Its purpose is to help a researcher move through the full lightweight literature workflow around a concrete research question:

1. Define a research question.
2. Discover candidate papers through Search, Recommendations, and Watches.
3. Use Preview + AI Analysis to decide which papers are worth deeper attention.
4. Send selected papers into Reading or Zotero.
5. Record reading progress with minimal user burden.
6. Build a workspace-specific literature memory.
7. Generate weekly reviews and maintain a human-AI coauthored Research Memo.
8. Export intermediate writing artifacts such as literature review outlines, related-work skeletons, and supervisor-ready progress summaries.

Paper Agent does **not** replace Zotero as the primary PDF reading and formal library management environment. Instead:

> **Paper Agent owns the research-question workspace before and after Zotero:**
>
> - **Before Zotero:** discovery, triage, reading decision.
> - **After Zotero:** reading record, weekly review, research memo, memory, idea support.

The next major version should prioritize:
- Research Question Workspace as the primary product object.
- A Notion-like Home and Workspace Overview experience.
- Low-friction reading logging.
- Research Memo as the long-term cognitive artifact.
- Layered Literature Memory / RAG.
- Workspace-aware AI Agent as a research assistant.
- Stronger positioning, interaction coherence, and design consistency.

---

# 1. Drill-Me Product Decisions

This PRD is based on a sequence of explicit product decisions.

## 1.1 Target User
**Primary user:**  
> Graduate students / PhD researchers who need to push specific research questions over weeks or months.

This product is not primarily for casual paper browsing, one-off homework search, or generic knowledge search.

---

## 1.2 First Core Pain
**Primary pain:**  
> Research literature work is fragmented across search, recommendation, preview, reading decisions, Zotero, informal notes, progress review, and later literature synthesis.

Paper Agent should unify this workflow around a research question.

---

## 1.3 Aha Moment
**Core value moment:**  
> A user sees papers from Search or Recommendations and, through Preview + AI Analysis, quickly judges which are worth truly reading before importing them to Zotero or adding them to Reading.

The product must optimize for **high-quality first-pass judgment**.

---

## 1.4 Product Positioning
**Primary positioning:**  
> Paper Agent is a research-question-driven AI literature workspace.

**Supporting value expression:**  
> It is an AI literature triage workspace that helps researchers judge papers before Zotero, then preserve and compound what they learn afterward.

---

## 1.5 Primary Organizational Object
**Top-level product object:**  
> Research Question Workspace.

The product should be organized around:
- “GraphRAG context compression”
- “Federated OOD for plankton detection”
- “Open-world semi-supervised FL”

rather than around a generic feed or a generic paper inbox.

---

## 1.6 Product Scope
**Chosen scope:**  
> Lightweight post-reading loop, not a full research operating system and not a PDF annotation replacement.

Paper Agent should support:
- Reading record
- Weekly review
- Workspace-specific literature memory
- Research Memo
- Writing-prep artifacts

But it should not try to fully replace:
- Zotero PDF reader
- Obsidian / Notion as a universal note system
- A full academic writing IDE

---

## 1.7 Product Rhythm
**Usage rhythm:**  
> Daily light loop + weekly deep loop.

### Daily light loop
- Review new recommendations or watch hits.
- Search a research question.
- Preview and triage.
- Add to Reading / import to Zotero.
- Optionally confirm “Read” or leave a takeaway.

### Weekly deep loop
- Review progress by workspace.
- Generate weekly review.
- Update Research Memo.
- Identify gaps in literature coverage.
- Ask Agent for next directions or missing papers.

---

## 1.8 Home Experience
**Home for returning users:**  
> A Notion-like personal research desk.

The first screen should combine:
1. **Continue Research** — active research workspaces.
2. **Today’s Papers** — papers worth attention from recommendations and watches.
3. **Quick Start** — new question or new search.
4. **Weekly Review status** — where appropriate.

Home should feel calm, personal, and immediately useful.

---

## 1.9 Workspace Experience
**Research Question Workspace default page:**  
> A Notion-like research homepage, not merely a search result page.

It should answer:
- What is this research question?
- What is my current understanding?
- What papers are newly relevant?
- What have I read?
- What should I do next?
- What is accumulating in this workspace?

---

## 1.10 Long-Term Cognitive Artifact
**Main long-term output:**  
> A living Research Memo.

Supporting artifacts serve the Memo:
- Curated paper list
- Reading history
- Weekly reviews
- Workspace RAG
- Writing export

---

## 1.11 Research Memo Authorship
**Authorship model:**  
> Human-AI coauthored.

- User owns the final text.
- AI proposes updates, summaries, gaps, and synthesis.
- User accepts, edits, rejects, or rewrites.

---

## 1.12 Research Memo Structure
**Memo format:**  
> Semi-structured.

It should start from a useful research scaffold but remain editable.

Suggested default sections:
1. Research Question
2. Why This Matters
3. Current Understanding
4. Key Papers
5. Method / Idea Map
6. Open Questions
7. Potential Research Gaps
8. Next Reading / Next Experiments

---

## 1.13 Writing Boundary
**Writing stance:**  
> Memo-first, writing-support second.

Paper Agent may produce:
- Weekly review
- Progress summary
- Literature review outline
- Related work skeleton
- Supervisor update draft

But should not market itself as a fully automatic academic paper writer.

---

## 1.14 AI Agent Identity
**Agent role:**  
> Research Assistant.

Not only an action executor, but not a pushy productivity coach and not an over-claimed “co-author.”

It should:
- Execute local tasks.
- Notice workspace gaps.
- Suggest next reading directions.
- Suggest Memo updates.
- Support literature review planning.
- Surface missing coverage.

---

## 1.15 Reading Log Philosophy
**Reading record philosophy:**  
> Low burden, behavior-first, with optional higher-value reflection.

The system should:
- Auto-record meaningful actions.
- Ask lightly at valuable moments.
- Never force journaling.

---

## 1.16 Reading Log Data Source
**Chosen model:**  
> Behavior-based logging first; weekly Agent reflection second; explicit manual input optional.

---

## 1.17 Literature Memory / RAG
**Memory architecture:**  
> Layered memory.

1. Candidate Layer
2. Reading Layer
3. Read Layer
4. Key Paper Layer

The system must preserve confidence distinctions:
- Seen ≠ selected ≠ read ≠ foundational.

---

## 1.18 Read Confirmation
**Read status decision:**  
> User-confirmed, system-assisted.

Paper Agent can suggest “you may have read this,” but only the user can confirm `Read`.

---

## 1.19 Key Paper Decision
**Chosen model:**  
> System-generated / system-curated Key Papers with explanations and user override.

The product should automatically surface likely key papers using:
- Citation signals
- Relevance to workspace
- Structural importance to the topic
- AI analysis
- User behavior signals

However:
- The system must explain why a paper is treated as key.
- Users must be able to accept, dismiss, pin, demote, or override system suggestions.
- “Key Paper” should never be a silent black-box label.

---

# 2. Product Definition

## 2.1 One-Sentence Positioning
> **Paper Agent helps researchers turn a research question into a living literature workspace: discover papers, judge what matters, record what was learned, and grow a research memo over time.**

---

## 2.2 Product Promise
For a graduate student or PhD researcher working on a concrete topic, Paper Agent should provide:

1. A calm place to continue a research question.
2. A strong first-pass paper triage experience.
3. A bridge to Zotero, not a substitute for it.
4. A low-friction reading memory.
5. A workspace-specific research knowledge base.
6. A Research Memo that becomes more valuable over time.
7. An AI research assistant that understands the workspace context.

---

# 3. User Personas

## 3.1 Primary Persona — Research-Driven Graduate Student
### Example
A PhD-bound master’s student or first/second-year PhD student working on 1–4 active research directions.

### Needs
- Track a few specific research questions.
- Understand which new papers deserve attention.
- Avoid drowning in arXiv / Scholar feeds.
- Build topic understanding gradually.
- Prepare advisor updates and literature summaries.
- Preserve why a paper mattered at the time it was read.

### Frustrations
- Search tools return too many papers.
- Zotero is good after selection, but weak at triage.
- Notes live in scattered places.
- Reading history is hard to review.
- Weekly progress is hard to reconstruct.
- Idea formation is not connected to the literature workflow.

---

## 3.2 Secondary Persona — Applied Research Engineer
### Needs
- Compare methods for a concrete implementation decision.
- Track a domain over several weeks.
- Produce a short internal research summary.

### Lower priority
This persona is useful but should not distort the product away from the graduate researcher workflow.

---

# 4. Jobs To Be Done

## 4.1 Discovery JTBD
“When I begin or continue a research question, help me quickly discover papers that plausibly matter.”

## 4.2 Triage JTBD
“When I face a list of candidate papers, help me decide which ones deserve serious reading.”

## 4.3 Reading Handoff JTBD
“When I decide a paper matters, help me move it into Reading or Zotero without losing workspace context.”

## 4.4 Reading Memory JTBD
“When I read papers over time, help me remember what I actually processed and what I learned without creating journaling burden.”

## 4.5 Synthesis JTBD
“When a workspace matures, help me turn scattered papers and reflections into a Research Memo and writing-prep artifacts.”

## 4.6 Review JTBD
“At the end of a week, help me summarize what moved forward and what remains unclear.”

---

# 5. Non-Goals

The following are explicitly out of scope for the next major version unless added later intentionally.

## 5.1 Not a Zotero Replacement
Paper Agent should not attempt to become:
- Full PDF reader
- Full citation library manager
- Reference style manager
- Annotation-first PDF tool

It may integrate with Zotero.

## 5.2 Not a Full Notion Replacement
Paper Agent should not become a generic workspace database tool.

## 5.3 Not a Fully Automatic Academic Writer
It may draft outlines and synthesis skeletons, but it must not promise “write your paper for you.”

## 5.4 Not a Productivity Coach App
Reading stats should feel supportive, not guilt-inducing.

## 5.5 Not a Generic AI Chat Shell
The Agent must remain grounded in workspace state and concrete research actions.

---

# 6. Product Principles

## 6.1 Research Question First
Every major feature should ask:
> Which research question does this help?

## 6.2 Triage Before Storage
The core magic is making the first read decision easier.

## 6.3 Low-Burden Logging
Do not turn reading into data entry.

## 6.4 Trustworthy Memory
Only higher-confidence papers should influence long-term research memory.

## 6.5 Human Owns Final Judgment
AI suggests. User decides.

## 6.6 Calm, Not Overbearing
The product should feel closer to Notion / Claude than a gamified productivity dashboard.

## 6.7 Local-First by Default
Preserve current project philosophy: local state, SQLite, no mandatory cloud.

---

# 7. Core Product Loops

## 7.1 Daily Light Loop

```text
Open Home
→ Continue a Workspace or review Today's Papers
→ Search / Recommendations / Watch hits
→ Preview paper
→ AI Analysis
→ Add to Reading / Send to Zotero / Ignore
→ Optional small reflection if marking Read
```

### Success metric
The user can process candidate literature with less friction and more confidence.

---

## 7.2 Weekly Deep Loop

```text
Open Weekly Review
→ See what happened by Workspace
→ Confirm reading progress
→ Answer 1–3 reflection prompts
→ Generate Weekly Review
→ Update Research Memo suggestions
→ Identify next reading and next research questions
```

### Success metric
The user can reconstruct research progress in minutes, not hours.

---

## 7.3 Workspace Knowledge Growth Loop

```text
Read papers
→ Confirm Read
→ Capture optional takeaway
→ System enriches workspace memory
→ Key Paper system proposes foundations
→ Memo gains sharper synthesis
→ RAG improves idea / literature support
```

---

# 8. Information Architecture

## 8.1 Global Navigation — Target
1. Home
2. Workspaces
3. Search
4. Reading
5. Watch
6. Recommendations
7. Reviews
8. Agent / floating launcher
9. Settings

### Notes
- “Workspaces” should become first-class.
- Search should support a workspace context but not require it.
- Reviews may be introduced later but should be planned as a product surface.

---

# 9. Product Surfaces

## 9.1 Home — Personal Research Desk

### Purpose
A returning user should understand their active research landscape at a glance.

### Core Modules
1. Greeting / calm header
2. Continue Research
3. Today’s Papers
4. Quick Start
5. Weekly Review status
6. Recent activity or reading progress, lightly shown

### Required Behaviors
- Show active research workspaces sorted by recency / relevance.
- For each workspace, show:
  - Title / research question
  - Last active
  - New candidate count
  - Reading count
  - Review status if available
- Show a compact “Today’s Papers” module:
  - Recent recommendation candidates
  - Watch hits
  - Untriaged items
- Keep a quick composer for:
  - New research question
  - General paper search
- Avoid turning Home into a dashboard overload.

---

## 9.2 Workspace Overview — Research Question Homepage

### Purpose
The centerpiece of the new product.

### Header
- Workspace title / research question
- Optional intent statement
- Status: active / paused / archived
- Last updated
- Actions:
  - Search within workspace
  - Run planner
  - Open memo
  - Generate review
  - Export / share locally where appropriate

### Main Modules
1. **Current Understanding**
   - A short AI/user-authored workspace summary
   - May pull from Research Memo summary
2. **New Since Last Visit**
   - New recommendations
   - New Watch hits
3. **Candidate Papers**
   - Recently discovered but untriaged
4. **Reading**
   - To Read
   - In Progress
   - Read
5. **Key Papers**
   - System-surfaced with explanation and user override
6. **Research Memo Snapshot**
   - Recent edits / sections that need attention later
7. **Workspace Memory Status**
   - Papers indexed
   - Read papers
   - Key papers
8. **Next Best Actions**
   - Suggested by Agent / system

---

## 9.3 Search — Workspace-Aware Discovery

### Purpose
Discover papers for a specific workspace or for general exploration.

### Required Behaviors
- Search can be:
  - General
  - Scoped to a workspace
- Search results should show:
  - Title
  - Authors
  - Venue/year
  - Why surfaced if available
  - Previewable summary
- Preview pane should include:
  - Abstract
  - AI Analysis
  - Relevance to current workspace
  - Actions:
    - Add to Reading
    - Ignore
    - Send to Zotero
    - Open Detail
- User should not lose workspace context on detail navigation.

---

## 9.4 Recommendations — Workspace-Tied Recommendations

### Purpose
Recommend papers with strong context.

### Required Behaviors
- Recommendations can exist:
  - Global
  - Workspace-specific
- Workspace recommendations should answer:
  - Why this paper?
  - Which part of the research question does it support?
  - Is it a survey, method, benchmark, critical baseline, or adjacent idea?
- Recommendations should become a candidate source for the workspace, not a disconnected feed.

---

## 9.5 Paper Preview

### Purpose
Make the high-value “judge before reading” moment excellent.

### Required Content
- Full title
- Authors / venue / year / source
- Abstract or meaningful excerpt
- AI Analysis summary:
  - Problem
  - Method
  - Contribution
  - Limitations
  - Why it matters for this workspace
- Evidence / confidence where available

### Required Actions
- Add to Reading
- Ignore
- Open full detail
- Send to Zotero
- Optional: Ask Agent about this paper

---

## 9.6 Paper Detail

### Purpose
A deeper, still focused pre-reading evaluation page.

### Required Content
- Full abstract
- Structured AI analysis
- Evidence claims
- Relevance to workspace
- Reading state
- Zotero handoff / export
- Activity history when useful, demoted and compact

### New Requirement
The detail page should support:
- Mark as Read
- Optional takeaway capture
- Link the paper to one or more workspaces
- Show whether it is:
  - Candidate
  - Reading
  - Read
  - Key Paper

---

## 9.7 Reading

### Purpose
Manage selected literature without replacing Zotero.

### Reading States — Proposed
1. To Read
2. In Progress
3. Read
4. Archived / Dropped

### Notes
Current queue states may need consolidation or migration from older categories such as Skim / Deep Read.

### Required Behaviors
- Every item should retain workspace association.
- Users can:
  - Open detail
  - Send to Zotero
  - Mark In Progress
  - Mark Read
  - Archive
- Mark Read triggers optional reflection:
  - One takeaway
  - Why it matters
  - Add to Memo?
  - Add to workspace memory?
- None of the above should be mandatory.

---

## 9.8 Reading Log

### Purpose
Create research memory without creating journaling burden.

### Automatically Recorded Events
- Added to Reading
- Opened Detail
- Exported / sent to Zotero
- Marked In Progress
- Marked Read
- Added takeaway
- Linked to workspace
- Added to Memo
- Key Paper system surfaced / accepted / dismissed

### Optional Manual Inputs
- One-line takeaway
- “Changed my view because…”
- “Potential use in my project…”
- “Worth citing later?”

### System Suggestions
Based on behavior:
- “You revisited this paper several times. Mark as Read?”
- “You marked this as Read. Add one takeaway?”

---

## 9.9 Weekly Review

### Purpose
Turn low-friction activity into meaningful reflection.

### Inputs
- Workspace activity
- Reading actions
- Takeaways
- New recommendations triaged
- Key papers surfaced
- Memo changes
- Agent conversations if explicitly allowed

### Output
A weekly review per user and optionally per workspace:
- What I explored
- What I read
- What changed in my understanding
- Open questions
- Next actions
- Suggested Memo updates

### UX
- Start from an AI-generated draft.
- Ask 1–3 short reflection prompts.
- Let the user edit before saving.
- Allow export as Markdown.

---

## 9.10 Research Memo

### Purpose
The long-term cognitive artifact of the workspace.

### Memo Sections — Default
1. Research Question
2. Why This Matters
3. Current Understanding
4. Key Papers
5. Method / Idea Map
6. Open Questions
7. Potential Research Gaps
8. Next Reading / Next Experiments

### Behaviors
- User edits directly.
- AI suggests additions or revisions.
- Each suggestion should indicate:
  - Why now?
  - Based on which papers / reflections?
  - Which section it targets?
- User can:
  - Accept
  - Edit and accept
  - Reject
  - Defer

### Versioning
At minimum:
- Last updated timestamp
- Change history or snapshot support later

---

## 9.11 Workspace Literature Memory / RAG

### Purpose
Power trustworthy workspace question-answering, idea exploration, and memo support.

## Memory Layers

### 1. Candidate Layer
Papers surfaced by Search / Recommendations / Watch.
- Not part of long-term RAG.
- Useful for short-term ranking context only.

### 2. Reading Layer
Papers added to Reading.
- May influence candidate ranking or suggestion context.
- Not considered trusted knowledge.

### 3. Read Layer
Papers explicitly marked Read by the user.
- Indexed into workspace RAG.
- Eligible to support memo suggestions and review synthesis.

### 4. Key Paper Layer
System-curated, explainable high-importance papers.
- Can include read papers and, when appropriate, influential not-yet-read papers clearly labeled as system suggestions.
- Strongly weighted in Memo / outline / idea generation.
- User can confirm, dismiss, or override.

### RAG Sources
Possible retrieval materials:
- Full abstract
- AI analysis
- User takeaway
- Weekly review mention
- Memo references
- Future: PDF chunks if Zotero/PDF ingestion is added with legal/technical clarity

### Retrieval Policy
- Prefer Read and Key layers.
- Downweight or exclude untriaged candidates.
- Expose retrieval provenance in UI where practical.

---

## 9.12 Writing-Prep Outputs

### Purpose
Convert research accumulation into editable intermediate artifacts.

### Supported Exports
- Weekly Review Markdown
- Workspace Summary
- Literature Review Outline
- Related Work Skeleton
- “What changed this month?” progress note
- Supervisor-ready research update draft

### Not Supported as Core Claim
- One-click complete academic paper writing

---

## 9.13 Zotero Integration

### Product Role
Zotero is the primary downstream destination for formal PDF reading and citation library management.

### Desired Capabilities
- Send paper metadata to Zotero
- Export BibTeX / DOI / URL where direct API integration is unavailable
- Track that the user chose “Send to Zotero”
- Use this action as a weak signal that the paper matters

### Potential Stages
1. MVP:
   - BibTeX / RIS export
   - Copy DOI / metadata
   - “Open in Zotero workflow” documentation
2. Better:
   - Zotero Web API integration
   - Send to chosen collection
3. Advanced:
   - Round-trip linkage between Paper Agent workspace and Zotero item

---

## 9.14 AI Agent — Research Assistant

### Positioning
A workspace-aware research assistant.

### It should help with:
- Search and discovery
- Triage support
- Watch creation
- Memo suggestion
- Review drafting
- Gap spotting
- Coverage checks
- “What should I read next?”

### It should not:
- Pretend to know what the user read without confirmation
- Treat weak candidates as established literature memory
- Overwhelm the user with constant nudges
- Replace final research judgment

### Example Agent Interactions
- “You have focused heavily on prompt compression. Want me to find graph-level compression work for this workspace?”
- “Three newly read papers suggest an update to your ‘Potential Gaps’ section.”
- “Would you like a weekly review draft for this workspace?”
- “This paper looks foundational for your topic based on citations, relevance, and method centrality. Mark as Key?”

---

# 10. Core Data Model — Proposed Additions

## 10.1 Research Workspace
A richer layer over existing Research Question.

Suggested fields:
- id
- title
- research_question_text
- intent_statement
- status
- created_at
- updated_at
- last_active_at
- summary_text
- memo_id
- default_recommendation_mode
- workspace_color / icon optional

## 10.2 Workspace Paper Link
Allows papers to belong to workspaces with stage/state.

Fields:
- workspace_id
- paper_id
- relationship_type:
  - candidate
  - reading
  - read
  - key_suggested
  - key_confirmed
  - dismissed
- reason
- source
- created_at
- updated_at

## 10.3 Reading Event
Fields:
- id
- user/local profile
- workspace_id
- paper_id
- event_type
- metadata_json
- created_at

## 10.4 Reading Takeaway
Fields:
- id
- workspace_id
- paper_id
- text
- created_at
- updated_at

## 10.5 Weekly Review
Fields:
- id
- workspace_id nullable
- week_start
- week_end
- draft_json
- final_markdown
- prompts_json
- created_at
- updated_at

## 10.6 Research Memo
Fields:
- id
- workspace_id
- title
- sections_json or markdown structure
- last_ai_suggestion_at
- created_at
- updated_at

## 10.7 Memo Suggestion
Fields:
- id
- memo_id
- target_section
- suggestion_text
- evidence_refs_json
- status:
  - pending
  - accepted
  - edited_accepted
  - rejected
  - deferred

## 10.8 Workspace Memory Chunk
Fields:
- id
- workspace_id
- source_type:
  - paper_abstract
  - ai_analysis
  - takeaway
  - review
  - memo
- source_id
- layer:
  - read
  - key
- embedding_ref
- chunk_text
- created_at

---

# 11. Metrics and Success Criteria

## 11.1 Product Activation
- User creates first research workspace.
- User triages at least 5 papers within a workspace.
- User adds at least 1 paper to Reading.

## 11.2 Triage Value
- % of candidate papers moved to Reading / Ignore.
- Time from search results to decision.
- Return rate to preview/detail workflows.

## 11.3 Reading Memory Value
- % of Read-marked papers with optional takeaway.
- Weekly review generation rate.
- Memo suggestion acceptance rate.

## 11.4 Research Workspace Retention
- Workspaces revisited weekly.
- Number of active workspaces per user.
- Candidate → Reading → Read conversion by workspace.

## 11.5 RAG / Memo Quality
- Key Paper suggestion acceptance rate.
- User rating of memo suggestions.
- Retrieval answer helpfulness for workspace Q&A.
- Literature review outline usage.

---

# 12. Functional Requirements by Priority

## P0 — Must Have for the Major Upgrade Foundation
1. Research Workspace as first-class navigation object.
2. Home redesigned as personal research desk.
3. Workspace Overview page.
4. Search / Recommendations properly scoped to workspace.
5. Add to Reading with workspace context.
6. Reading states consolidated toward To Read / In Progress / Read.
7. Mark as Read with optional takeaway prompt.
8. Reading event logging.
9. Minimal Research Memo data model and page shell.
10. Weekly Review data model or placeholder flow foundation.
11. Agent becomes workspace-aware in prompt/context layer.

## P1 — Strong Product Expansion
1. Working Research Memo editor.
2. AI memo suggestions.
3. Weekly Review draft generation.
4. Layered workspace memory model.
5. Read-layer RAG ingestion.
6. Key Paper system-generated suggestions with explanations.
7. Workspace-aware Recommendation quality improvements.
8. Zotero MVP handoff.

## P2 — Later Enhancements
1. Full Zotero API sync.
2. PDF chunk ingestion if desired.
3. Advanced memo versioning.
4. Cross-workspace synthesis.
5. More formal writing exports.
6. Visual analytics of reading progress.

---

# 13. UX Requirements

## 13.1 Visual Tone
- Calm
- Warm
- Precise
- Notion-like organization
- Claude-like softness
- Apple-like restraint

## 13.2 Interaction Philosophy
- Preserve context across navigation.
- Avoid surprising redirects.
- Make state visible after actions.
- Do not over-modalize.
- Offer reflection, never force it.

## 13.3 Copy Tone
- Gentle, research-aware
- Avoid productivity guilt
- Prefer:
  - “Continue research”
  - “Worth revisiting”
  - “Add one takeaway?”
over:
  - “You failed to complete your reading goal”

---

# 14. Technical Compatibility With Current System

The current project already includes:
- Local-first Flask/Jinja architecture
- Search, Recommendations, Reading, Watch, Paper Detail, Settings
- Entity system
- Agent sessions and drawer
- SQLite state store
- AI analysis service
- Recommendation workspace service
- Research Question concept
- Planner beginnings
- Watch subscriptions
- Visual design system under active refactor

The major upgrade should evolve this existing system, not replace it wholesale.

---

# 15. Risks

## 15.1 Scope Creep
The vision is broad. The next engineering phase must focus on foundation first.

## 15.2 Overbuilding Journaling
Reading record must remain low-burden.

## 15.3 RAG Pollution
Do not index low-trust candidate content as if it were user-approved knowledge.

## 15.4 Memo Over-Automation
AI suggestions must remain transparent and editable.

## 15.5 Product UI Becoming Too Dashboard-Like
Home and workspace surfaces should be informative but calm.

---

# 16. Open Product Questions for Later

1. Exact taxonomy of reading states after migration.
2. Whether Key Papers can include unread but influential system-suggested papers, and how to label them.
3. Whether workspace memory should index PDF content or only abstract/analysis/takeaway at first.
4. Best Zotero MVP integration path.
5. Whether Reviews should be global-first or workspace-first.
6. Whether a workspace can contain multiple sub-questions.

---

# 17. Definition of Success for This Product Direction

Paper Agent succeeds when a researcher can say:

> “I opened my workspace, saw what mattered, decided what to read, preserved what I learned, and after a few weeks I had a better research memo than I could have built from scattered tools alone.”

