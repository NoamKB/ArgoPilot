"""Write speaker notes into a .pptx, one right-to-left paragraph per line for Hebrew.

PowerPoint shows Hebrew notes in the wrong order unless each paragraph is marked right-to-left
(`<a:pPr algn="r" rtl="1"/>`) and each run carries `lang="he-IL"`. python-pptx's `notes_text_frame.text = ...`
does neither, so this script writes the paragraphs itself.

Notes file format (markdown):

    ## slide 1
    ### שאלה:
    "Explain the user flow from the browser to the services and back"
    ### מה אומרים:
    ...

    ## slide 2
    ...

`## slide N` starts slide N's notes. A `### ` line becomes a bold heading. Every other line becomes one paragraph;
blank lines are kept. Lines with Hebrew letters are right-to-left; lines without are left-to-right.

Usage: python set_notes.py deck.pptx notes.md -o out.pptx
Needs python-pptx and lxml.
"""

import argparse
import re
import sys

from lxml import etree
from pptx import Presentation

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
HEBREW = re.compile(r"[֐-׿]")
SLIDE = re.compile(r"^##\s+slide\s+(\d+)\s*$", re.IGNORECASE)


def parse_notes(text: str) -> dict[int, list[str]]:
    notes: dict[int, list[str]] = {}
    current = None
    for line in text.splitlines():
        match = SLIDE.match(line)
        if match:
            current = int(match.group(1))
            notes[current] = []
        elif current is not None:
            notes[current].append(line)
    # Drop blank lines at the start and end of each slide's notes.
    for lines in notes.values():
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return notes


def write_paragraphs(slide, lines: list[str]) -> None:
    body = slide.notes_slide.notes_text_frame._txBody
    for paragraph in body.findall(f"{{{A}}}p"):
        body.remove(paragraph)
    for line in lines:
        bold = line.startswith("### ")
        text = line[4:] if bold else line
        rtl = bool(HEBREW.search(text))
        lang = "he-IL" if rtl else "en-US"
        paragraph = etree.SubElement(body, f"{{{A}}}p")
        etree.SubElement(paragraph, f"{{{A}}}pPr", algn="r" if rtl else "l", rtl="1" if rtl else "0")
        if text.strip():
            run = etree.SubElement(paragraph, f"{{{A}}}r")
            attributes = {"lang": lang, "dirty": "0"}
            if bold:
                attributes["b"] = "1"
            etree.SubElement(run, f"{{{A}}}rPr", **attributes)
            etree.SubElement(run, f"{{{A}}}t").text = text
        etree.SubElement(paragraph, f"{{{A}}}endParaRPr", lang=lang, dirty="0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck")
    parser.add_argument("notes")
    parser.add_argument("-o", "--output", required=True, help="output .pptx (may equal the input)")
    args = parser.parse_args()

    presentation = Presentation(args.deck)
    with open(args.notes, encoding="utf-8") as handle:
        notes = parse_notes(handle.read())

    count = len(presentation.slides)
    unknown = sorted(n for n in notes if not 1 <= n <= count)
    if unknown:
        sys.exit(f"notes for slides {unknown}, but the deck has {count} slides")
    missing = [n for n in range(1, count + 1) if n not in notes]

    for number, lines in notes.items():
        write_paragraphs(presentation.slides[number - 1], lines)
    presentation.save(args.output)
    print(f"wrote notes for {len(notes)} of {count} slides to {args.output}")
    if missing:
        print(f"warning: no notes for slides {missing}")


if __name__ == "__main__":
    main()
