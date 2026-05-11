# Multi-Agent Product Development Workflow

> **Note**: This document describes the *development* workflow (how AI coding
> agents collaborate on building this project). It does NOT describe the
> in-product Paper Agent assistant that users interact with via the Agent drawer.
> For the product Agent specification, see `PRD.md` Section 8.

This document is a reusable workflow for agent-assisted product development
projects. It is intentionally product-agnostic: each project should provide its
own PRD, architecture notes, and acceptance criteria.

## Operating Principles

- Work from explicit user intent and repository evidence.
- Keep tasks small enough to review and verify independently.
- Prefer existing project conventions over new abstractions.
- Separate product decisions from implementation mechanics.
- Report facts, tradeoffs, risks, and verification results without hiding
  uncertainty.

## Roles

One agent may play multiple roles in a small task. For larger work, split these
roles across independent agents only when their responsibilities do not require
shared mutable state.

| Role | Responsibility | Output |
| --- | --- | --- |
| Lead | Owns task framing, sequencing, and final report | Scope, plan, handoff prompts, status |
| Context Scanner | Reads repository, docs, tests, and existing behavior | Findings with file references |
| Planner | Turns intent and findings into executable steps | Plan with acceptance checks |
| Implementer | Makes scoped code or documentation changes | Patch, notes, changed files |
| Reviewer | Looks for bugs, scope drift, missing tests, and regressions | Findings ordered by severity |
| Verifier | Runs commands and product checks | Evidence: commands, results, residual risk |

## Workflow

### 1. Receive

Clarify the requested outcome before touching files.

Required output:
- One-sentence task understanding.
- Key assumptions.
- Explicit out-of-scope items when useful.
- Blocking questions only when no reasonable local assumption is safe.

### 2. Context Scan

Read the smallest useful set of files and commands that reveal current behavior.

Checklist:
- Inspect relevant docs and tests before implementation.
- Locate existing conventions and similar code paths.
- Identify files likely to change.
- Record constraints that affect the plan.

### 3. Plan

Create a concrete implementation path before editing.

A good plan includes:
- Goal.
- Ordered tasks.
- Files or modules likely to change.
- Acceptance criteria.
- Verification commands.
- Known risks and rollback notes.

For small tasks, the plan can be short and inline. For large tasks, write it as
a checked document or handoff prompt.

### 4. Implement

Execute the plan in small, reviewable steps.

Rules:
- Keep each change aligned with a specific acceptance criterion.
- Do not mix unrelated refactors into feature work.
- Preserve user or teammate changes already present in the worktree.
- Update tests and documentation when behavior or product contracts change.
- Pause and re-plan if implementation reveals a materially different problem.

### 5. Review

Review the patch as if it came from another engineer.

Focus on:
- Behavioral regressions.
- Missing tests or weak assertions.
- Broken links or stale docs.
- Security and privacy issues.
- Product contradictions between docs and implementation.
- Overbroad changes that make future work harder.

### 6. Verify

Run the narrowest meaningful checks first, then broader checks.

Verification should include:
- Targeted tests for changed behavior.
- Relevant full suites where practical.
- Browser or product smoke checks for user-facing surfaces.
- Documentation link and terminology checks when docs changed.

Never report success without the command or product evidence that supports it.

### 7. Report

End with a concise report.

Include:
- What changed.
- What was verified.
- Any failures or skipped checks.
- Remaining risks.
- Clear next steps when work remains.

## DeepSeek v4 Adaptation Rules

DeepSeek v4-class agents work best when ambiguity is reduced and verification is
externalized. When assigning work to them:

- Give one task objective per prompt.
- Provide exact file paths and expected output format.
- Include acceptance tests or commands up front.
- Keep context focused; summarize background instead of pasting large docs.
- Prefer small patches over broad redesigns.
- Make product decisions explicit before asking for implementation.
- Ask for a final report containing changed files, tests run, and unresolved
  risks.
- Avoid giving two agents write access to the same file set at the same time.

Recommended handoff shape:

```text
Task:
<one concrete outcome>

Context:
<short summary and relevant files>

Files you may edit:
<paths>

Do not edit:
<paths or concerns>

Acceptance:
<observable behavior and tests>

Report:
- changed files
- commands run
- remaining risks
```

## Multi-Agent Coordination

Use parallel agents only for independent work:

- Good split: one agent fixes tests while another updates a standalone document.
- Good split: one agent reviews product copy while another checks backend
  behavior.
- Bad split: two agents editing the same route, template, or state model.

The Lead should integrate outputs, resolve conflicts, and run final
verification. Agents should not assume their local task passing means the whole
project is complete.

## Completion Standard

A task is complete only when:

- The requested outcome is implemented or the blocker is clearly documented.
- Relevant docs, tests, and links agree with the new behavior.
- Verification commands have been run and reported.
- Residual risks are explicit enough for the next agent or human reviewer to
  act on them.
