# Deck style

## What makes a deck look AI-generated (the P1 deck)

Avoid these, because together they read as a template rather than as the user's own engineering:

- dark full-bleed background on every slide, glowing accent colours;
- grids of rounded cards, each with an icon in a circle;
- giant stat callouts (a number in 60 pt with a tiny label) as the main content;
- generic titles ("Live Demo | API in Action", "Testing & Performance") instead of a statement;
- decorative dot patterns, progress bars, badges that carry no information.

## The direction (the approved P2 deck, `docs/presentations/p2/p2-slides.pptx`)

These rules override the design ideas in the `anthropic-skills:pptx` skill.

- **Light paper background** (off-white, e.g. `F7F5EF`), dark ink text (`1F2A1F`), **one** accent colour for the thing that matters on the slide (a muted green, e.g. `2F6B3A`), and one warning colour used only for failures (`B4532A`). Grey (`8A8F87`) for older layers and secondary text.
- **Headline = a sentence that states the point** and is clear when read aloud ("The browser talks only to the frontend server; the services stay behind it"), left-aligned, about 28 pt. Above it, small and grey, the review question it answers (left out on slides that answer none).
- **Monospace** (Courier New or Menlo) only for code, endpoints, ports and file names; a plain sans (Arial or Calibri) for everything else.
- **Diagrams with thin lines**: boxes with 1 pt outlines, no shadows, no gradients, labelled arrows. Numbered steps on sequence diagrams match the numbering in the notes.
- A quiet footer: assignment · slide number.

## Density limits

The first P2 deck carried 100–220 words on most slides with 11 pt text; that is why it felt long. Per slide:

- one visual (a diagram, a table or a short list) — not two competing ones;
- the review-question line and the headline: one line each (shorten a long or paired question on the slide; the full text goes in the notes);
- running text — everything outside the visual except the question line and the headline: about 30 words at most;
- a diagram: labels of one to four words;
- a table: at most 4 rows and 3 columns, cells of a few words — a table of full sentences belongs in the notes;
- body text at least 14 pt, labels at least 12 pt;
- no paragraph on a slide;
- numbers only when they mean something the reviewer cares about — one number per point (for example the p95 of the main call, or one p95 per hop to show where time goes), never a spread of percentiles or every measurement taken; the measurement's provenance belongs in the prep document, not necessarily on the slide.

If a slide needs more, it is either two points (split or drop one) or detail that belongs in the notes.
