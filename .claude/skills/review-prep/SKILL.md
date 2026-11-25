---
name: review-prep
description: Prepare the user for the instructor review of the current AgroPilot course assignment (P1, P2, P3 ...) — a code sweep that predicts the interviewer's questions with answers tied to the code, a written prep document, and a review deck (.pptx, at most 10 slides, English slides, Hebrew RTL speaker notes) built around the assignment's review questions and the system's architecture and flows. Use whenever the user mentions the review, the presentation or deck for an assignment, the interview or the instructors' questions, "prepare me", practising answers, or wants to record questions the reviewers asked — even if they don't say "review-prep". Also use when they ask "what will they ask me about X" for this project.
argument-hint: "[prep | deck | practice | record] [assignment, e.g. P3]"
---

# Review prep

Every AgroPilot assignment ends with a live review: the user presents a deck, then reviewers ask questions about what they built. The reviewers want to see that the user **understands the architecture** — which component talks to which, what happens on the client side and on the server side, on the happy path and when something fails, and what happens under load. A pretty deck does not help; an answer the user can't explain hurts.

The P2 review showed the gap this skill closes: the user was asked when the frontend's health check runs, what happens at maximum load, what changes with several instances, and how the weather cache behaves under load. All four answers were in the code, but nothing had prepared the user to find them. So the skill's core is the **code sweep** (part 1); the deck (part 2) is built on its findings.

Mode: $ARGUMENTS — `prep` (part 1 only), `deck` (part 1 then part 2), `practice` (part 3), `record` (part 4). No mode: do part 1, then ask whether to build the deck.

The user is learning. They must be able to explain every line on a slide and every sentence in the notes, so write for understanding, not for impressing.

## 0. Find the assignment and its sources

1. Read the project `CLAUDE.md`, section **Assignment**: the line marked **current** gives the assignment and its specification URL. Use the assignment in $ARGUMENTS if given.
2. Fetch the specification from the course repo (read-only, public): `gh api repos/alonitac/OzVeruach26/contents/tasks/<file> -H "Accept: application/vnd.github.raw"`. If it cannot be fetched, stop and say so — don't reconstruct the questions from memory.
3. Take the **Review questions** section at the end of the page, word for word. These are the instructor's guiding questions and the backbone of the deck. Their number and topics change between assignments: use this assignment's questions, not an earlier deck's questions or grouping. If the page has none (P1 had none), say so and propose questions derived from the spec's functional and non-functional requirements; the user approves them.
4. Read `docs/instructor-clarifications.md`, the entries of `docs/judgment-log.md` for this assignment, and the previous assignment's deck and prep doc in `docs/presentations/pM/` (M = N − 1) (to know what was already presented — this assignment adds one layer; present the new layer, summarise the old ones in a line).
5. Read [references/asked-questions.md](references/asked-questions.md): questions reviewers really asked before. Each one names the pattern behind it; check every pattern against this assignment's code.

## Where the outputs go

Everything the user keeps goes in the assignment's own folder, `docs/presentations/pN/` (N = assignment number, lower case; create the folder if it doesn't exist):

| File | What |
|---|---|
| `pN-interview-prep.md` | the sweep's findings (part 1), including the deck outline as its last section |
| `pN-slides.pptx` | the deck (part 2). If a deck by that name already exists (any capitalisation, e.g. `P2-slides.pptx`), write `pN-slides-draft.pptx`, then `-draft-2`, `-draft-3` — never overwrite an existing file. Name the prep doc to match (`pN-interview-prep-2.md`) |

Don't leave a deliverable only in the scratchpad: the user opens these files from the repo, in PowerPoint and VS Code, and a file under `/private/tmp` is hard to find and may not open there. Working files (build script, notes markdown, rendered images) stay in the scratchpad. Nothing is committed; the user decides.

## 1. Code sweep and the prep document

Go through the code of every service touched by this assignment with the checklist in [references/sweep-checklist.md](references/sweep-checklist.md). For each finding, record:

- the answer in two or three plain sentences;
- the evidence: `path:line`, a test, or the command that measured it;
- a label: **MEASURED** (run or measured — say how), **READ IN CODE** (seen in the code or the official docs, not run), or **REASONED** (follows from the code but nothing shows it directly). Never present a reasoned answer as measured. Never invent a number; if a number is needed and doesn't exist, say how to measure it and offer to.

For measurements, record the relevant environment, workload, method, and code revision when available. Keep provenance in the prep document, not necessarily on the slides. Never invent missing details.

Numbers: prefer numbers already measured and documented — the presenter guide and deck notes in `docs/presentations/pN/`, the judgment log, the service READMEs. Run the test suites to get current counts (fast). Benchmarks take minutes and need running services — offer them; don't run them unasked.

Write `docs/presentations/pN/pN-interview-prep.md` in Hebrew, RTL (wrap in `<div dir="rtl">`), code and identifiers in English. Near the top, say once that `file.py:42` means line 42 of that file. Structure:

1. **The system in one paragraph** and an ASCII diagram of who calls whom (ports, protocols).
2. **The review questions**, each with: the short answer to say out loud, the longer explanation, evidence, the label, and the slide that covers it.
3. **Likely follow-ups** from the sweep, grouped by checklist category, same format. The asked-questions patterns go here, answered for this assignment.
4. **Flows**: client side (browser ↔ frontend server) and server side (service ↔ service), happy path and each error path, step by step with `path:line`.
5. **Under load**: what is measured, what saturates first if known, what happens with several instances of each service, which state breaks when you scale (in-memory caches, local files, connection pools).
6. **Glossary**: every technical term used in the doc and the deck, one line each, in plain Hebrew.
7. **Known gaps, honestly**: what is not tested, not measured, or wrong in docs.
8. **Deck outline** (added in part 2): the approved slide table.

## 2. The review deck

The deck tells the story of this assignment: what the system was before, what this layer added, how the parts talk to each other, and how the work answers the review questions. The review questions are what the reviewers focus on, so they are woven through the slides and the notes — not parked on one slide each.

### Plan first, and wait for approval

Before building, show the outline as a table: slide number · review question(s) it answers · headline · the one visual · what the user must be able to explain. Every review question must map to a slide. Wait for the user's approval — the project rules require a plan before significant work, and the outline is where the user catches a slide they can't defend.

### Shape: as few slides as the content needs

The first P2 deck had 20 dense slides; that is what this skill exists to prevent. Use as few slides as tell the story — fewer is better, and about 10 is a ceiling, not a target. A shape that fits most assignments (merge or drop slides when the content allows):

1. **Title and the layer** — the question this assignment answers for the grower, and what was added on top of the previous assignment.
2. **Architecture** — who talks to whom: every component, port and protocol; this assignment's parts highlighted, earlier assignments' parts in grey and labelled as such (the user liked the P1/P2 split). This is the slide reviewers care about most.
3. **Client-side flow** — browser ↔ frontend server: what runs where, what the browser never sees.
4. **Server-side happy path** — the sequence of calls between services, numbered.
5. **Server-side error path** — what fails, where it is caught, what each layer passes up, what the user sees, where the detail is logged.
6+. **The remaining review questions**, grouped by topic (in P2: data and security; testing; performance, load and scaling; external limits; validating the requirements). When there are more questions than slides, pair questions that share an answer — in P2, for example "why a weather service" with "rate limits", "testing the weather service" with "testing the planner", "registry down" with the error path.
Last. **Limits and next steps**, then "Questions".

No backup slides: the prep doc holds the detail.

### Make it memorable

Reviewers remember concrete cases and good design answers more than coverage. Read the "What reviewers liked" section of [references/asked-questions.md](references/asked-questions.md), and for this assignment find the equivalents: a vivid domain case (in P2: the out-of-season crop that gets a 409 instead of a made-up plan), a short live demo of the UI, and a design answer to a scaling question (in P2: moving the cache out of the instances into a shared, managed cache). Give each a place in the deck or the notes, and mention the demo where it fits.

### Look: plain, light, not "AI-made"

The P1 deck is the example to avoid; the approved P2 deck (`docs/presentations/p2/p2-slides.pptx`, built by this skill) is the direction. The rules are in [references/deck-style.md](references/deck-style.md). They override the design ideas in the `anthropic-skills:pptx` skill (icons in circles, giant stat callouts, dark title slides): that skill is for the file mechanics only.

### Notes: the most important part

The notes are the user's study sheet first and script second: they must help the user understand what they built and explain it in their own words — not lines to memorise — so they can present the slide and answer follow-ups without opening the code. Read [references/notes-guide.md](references/notes-guide.md) before writing them — it has the headings, the rules, and examples of what confused the user in the P2 dry run. In short:

- Start with **על מה השקף** (one line), then the question it answers if there is one. Leave out any heading that doesn't apply — never write "no question" or "load is not relevant".
- Slide 1's notes open with the system overview: what earlier assignments built, what this one added.
- Explain content, not formatting ("the headline in grey" helps no one).
- Every term gets a few words of explanation the first time it appears; every number says what it means and what happens when it's exceeded.
- No raw identifiers in the spoken text: describe what a test checks instead of quoting its function name; give code locations as file and function names in a separate "איפה בקוד" line, without line numbers.

### Build

- Use the `anthropic-skills:pptx` skill for the file mechanics. 16:9 wide (13.33 × 7.5 in). If `require('pptxgenjs')` fails, build with python-pptx; both are fine.
- Write the notes as a markdown file (`## slide N` sections, `### heading` lines for bold headings), then put them into the deck with `scripts/set_notes.py`, which writes the right-to-left paragraphs PowerPoint's notes need.
- Save in the assignment folder ("Where the outputs go") and add the approved outline to the end of the prep doc.
- **Look at every slide.** Tell the user before rendering: it opens and closes Keynote windows, and macOS may ask to allow Keynote into the output folder (it is empty until the export runs). Copy the deck to a folder under the repo's `docs/presentations/pN/` or the home directory first — Keynote may refuse files under `/private/tmp`. Run `scripts/render_slides.sh deck.pptx outdir` outside the sandbox. If rendering fails, say so, check density from the XML (word counts, font sizes), and ask the user to open the deck and report what looks wrong; don't keep retrying other renderers.
- Fix overflow, overlap, text under 14 pt, and slides over the density limits. Then run the pptx skill's `validate.py`.

### When the assignment already has a deck

If `docs/presentations/pN/` already holds a deck or a presenter guide, read them: their notes often hold the measured numbers (benchmarks are rarely in the READMEs). Reuse what is verified, check it against the code (the P2 dry run found a wrong explanation in the old deck's notes), and write the new deck as `pN-slides-draft.pptx`.

### Fact-check before handing over

Every number, identifier, endpoint, file name and status code on the slides and in the notes must trace to the code or to a measurement. Grep for each identifier; re-read each number's source. List anything you could not verify, and either fix it or mark it as an estimate. This is the rule the user set: nothing in the deck they can't explain.

Don't commit. Report the files, the outline, and what was not verified; the user decides when to commit.

## 3. Practice

Ask one question at a time — from the review questions, then the follow-ups and the asked-questions patterns, mixing easy and hard. Wait for the user's answer. Then say what was right, what was missing or wrong (with `path:line`), and give a model answer of two or three sentences. Keep a running list of weak topics and suggest revisiting them at the end. Don't reveal the answer before the user tries; give a hint if they ask.

## 4. Record what the reviewers asked

After a review, the user tells you what they were asked. For each question, propose an entry for [references/asked-questions.md](references/asked-questions.md) in its format — the question, the assignment, the short answer, and the **pattern** (the general kind of question, so it can be checked in future assignments). Show the exact entries and write them only after the user approves. If a pattern is new, also add a line to the sweep checklist.
