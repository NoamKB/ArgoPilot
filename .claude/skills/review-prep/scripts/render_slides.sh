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

osascript <<EOF
tell application "Keynote"
  set doc to open POSIX file "$deck"
  export doc to POSIX file "$outdir" as slide images with properties {image format:JPEG, export style:IndividualSlides}
  close doc saving no
end tell
EOF

ls "$outdir"
