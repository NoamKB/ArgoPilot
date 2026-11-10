---
name: record-decision
description: Record a significant engineering decision in docs/judgment-log.md (AI recommendation, alternatives, chosen approach, reasoning, tradeoffs) after the user approves the exact entry. Use when the user runs /record-decision or asks to log, record, or document a decision. Also use when a significant decision has just been finalized, such as an architecture, data model, API contract, dependency, or testing-strategy choice between real alternatives, or the user rejecting or changing an AI recommendation, in order to offer recording it. Do not use for routine questions, explanations, small fixes, or choices the assignment specification already dictates.
argument-hint: "[decision topic]"
---

# Record Decision

Add one approved entry to `docs/judgment-log.md`, the project's record of how engineering decisions were made during AI-assisted development. Reviewers use this log to judge the user's reasoning, so an entry has value only if it reflects what actually happened.

Topic: $ARGUMENTS

If no topic is given, use the most recent decision in the conversation. If that is ambiguous, ask which decision to record.

## Offer or record

- **The user ran `/record-decision` or asked to record a decision:** follow the workflow below.
- **You noticed a significant decision yourself:** end your reply with a one-line offer, after answering whatever the user asked. For example: `Significant decision: <title>. Record it with /record-decision?` Start the workflow only if the user agrees, and do not repeat a declined offer.

A decision is significant if it does at least one of these:

- Chooses between real alternatives with consequences beyond the current change, such as architecture, data model, API contract, dependency, persistence, or testing strategy.
- Rejects or changes an AI recommendation.
- Settles an ambiguity in the assignment specification by choosing between options.

It is not significant if it is a question or explanation, a naming or style choice, a bug fix with one obvious answer, or something the specification or the instructor already dictates. An instructor clarification is not the user's decision, so do not record it as one. Only a choice the user made because of it qualifies. A decision still under discussion is not ready: wait until it is final.

## Workflow

1. **Gather.** Use the conversation and what the user tells you. Code shows what was chosen, not why, so do not reconstruct a decision from the code alone. Read `docs/judgment-log.md` if it exists and check that the decision is not already recorded.

2. **Find the gaps.** Every field must trace back to something actually said. If the decision or the reasoning is unclear, ask before drafting. Put all your questions in one message, then wait.
   - **Reasoning means the user's reasoning.** An argument you made for your recommendation counts only if the user adopted it. "I followed the recommendation because I could not evaluate it yet" is a valid answer: record it as stated.
   - **Alternatives and tradeoffs:** if none were discussed, ask whether the user wants to add any, and otherwise write `None discussed`. You may suggest one, labeled as your suggestion, but it enters the entry only if the user confirms it.

3. **Present the exact entry** in the format below, with the ID and date filled in, and ask for approval, then stop and wait. Only an explicit yes given after seeing this entry counts. Silence, moving on to other work, or approval given before the entry was shown is not approval, so show the entry even if the user says to skip that step. If the user requests changes, show the revised entry and ask again.

4. **Append** exactly the approved text to the end of the file.
   - If the file exists, read it and append with Edit, anchored on its last line. Never use Write on an existing log, because Write replaces the whole file.
   - If the file does not exist, create it with Write, starting with the header below.
   - Never change existing entries. If a decision is reversed, add a new entry and name the old entry's ID in its Context field.
   - Do not commit or push.

5. **Confirm** the entry ID and file path in one line.

## Entry format

Keep each field to one or two sentences. State reasons directly, without "I" or "the user": `No separate database server is needed.`

```markdown
## JL-001: <short decision title>

- **Date:** <YYYY-MM-DD the decision was made>
- **Assignment:** <current assignment from CLAUDE.md, or "General">
- **Context:** <the problem being decided>
- **AI recommendation:** <what the AI suggested, or "None" if the user decided without one>
- **Alternatives:** <other options and why they were set aside, or "None discussed">
- **Decision:** <what was chosen>
- **Reasoning:** <why the user chose it>
- **Tradeoffs:** <what was accepted or given up, or "None discussed">
```

Number entries by taking the highest existing `JL-` number and adding one. The first entry is `JL-001`.

## New file header

```markdown
# Engineering Judgment Log

Significant engineering decisions made during AI-assisted development of AgroPilot.
```
