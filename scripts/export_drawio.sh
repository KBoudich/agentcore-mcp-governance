#!/usr/bin/env bash
# Export every .drawio file in a directory to SVG (and PNG with --png) using the
# draw.io desktop CLI. Works headless on Linux through xvfb-run.
#
#   export_drawio.sh <dir> [--png]
#
# Set DRAWIO_BIN to override binary discovery. SVG_BACKGROUND (default #ffffff)
# is written onto the SVG root: draw.io omits a white page background on
# export, which leaves diagrams transparent and unreadable on dark pages.
set -euo pipefail

dir="${1:?usage: export_drawio.sh <dir> [--png]}"
want_png="${2:-}"

find_bin() {
  if [[ -n "${DRAWIO_BIN:-}" ]]; then echo "$DRAWIO_BIN"; return; fi
  for c in drawio draw.io /opt/drawio/drawio "/Applications/draw.io.app/Contents/MacOS/draw.io"; do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then echo "$c"; return; fi
  done
  echo "draw.io CLI not found; install draw.io desktop or set DRAWIO_BIN" >&2
  exit 1
}

bin="$(find_bin)"
runner=()
if [[ "$(uname)" == "Linux" && -z "${DISPLAY:-}" ]] && command -v xvfb-run >/dev/null; then
  runner=(xvfb-run -a)
fi

abs_dir="$(cd "$dir" && pwd)"
shopt -s nullglob
for f in "$abs_dir"/*.drawio; do
  base="${f%.drawio}"
  "${runner[@]}" "$bin" -x -f svg --embed-diagram -o "$base.svg" "$f" --no-sandbox --disable-gpu 2>/dev/null | grep -- '->' || true
  python3 - "$base.svg" "${SVG_BACKGROUND:-#ffffff}" <<'PY'
import re, sys
path, color = sys.argv[1], sys.argv[2]
svg = open(path, encoding="utf-8").read()
root = re.search(r"<svg\b[^>]*>", svg)
# Only the style attribute counts: the embedded `content` attribute mentions "background" too.
if root and not re.search(r'\sstyle="[^"]*background', root.group(0)):
    tag = root.group(0)
    svg = svg.replace(tag, tag[:-1].rstrip() + f' style="background-color: {color};">', 1)
    open(path, "w", encoding="utf-8").write(svg)
PY
  if [[ "$want_png" == "--png" ]]; then
    "${runner[@]}" "$bin" -x -f png -s 2 -o "$base.png" "$f" --no-sandbox --disable-gpu 2>/dev/null | grep -- '->' || true
  fi
done
