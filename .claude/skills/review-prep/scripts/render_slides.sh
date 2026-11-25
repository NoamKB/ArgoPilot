#!/usr/bin/env bash
# Render every slide of a .pptx to JPEG with Keynote, for visual checks.
# LibreOffice is not installed on this Mac; Keynote is. Keynote does not draw pptxgenjs charts — check those in XML.
# Run outside the sandbox: Keynote is driven through AppleScript.
#
# Usage: render_slides.sh deck.pptx outdir
set -euo pipefail

deck="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mkdir -p "$2"
outdir="$(cd "$2" && pwd)"

# The paths go in as arguments, not spliced into the script text, so a quote in a path can't change the script.
osascript - "$deck" "$outdir" <<'EOF'
on run argv
  tell application "Keynote"
    set doc to open POSIX file (item 1 of argv)
    export doc to POSIX file (item 2 of argv) as slide images with properties {image format:JPEG, export style:IndividualSlides}
    close doc saving no
  end tell
end run
EOF

ls "$outdir"
