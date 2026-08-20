#!/usr/bin/env bash
# ==============================================================================
# Flama - Run Lighthouse Audit with Isolated Test Profile
# ==============================================================================
# Golden Rule: Never use the user's default/personal profile for audits.
# ==============================================================================

set -euo pipefail

URL="${1:-http://localhost:5173}"
CATEGORIES="${2:-seo,performance,accessibility,best-practices}"
PROFILE_DIR="${3:-$HOME/.gemini/chrome-profiles/flama-devtools}"
OUTPUT_DIR="${4:-reports/lighthouse}"
FORM_FACTOR="${5:-desktop}"

echo "============================================================"
echo "🔍 Flama Lighthouse Audit (Isolated Test Profile)"
echo "============================================================"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_BASE="$OUTPUT_DIR/lighthouse_${FORM_FACTOR}_${TIMESTAMP}"

echo " Target URL        : $URL"
echo " Categories        : $CATEGORIES"
echo " Form Factor       : $FORM_FACTOR"
echo " Isolated Profile  : $PROFILE_DIR"
echo " Report Output     : ${REPORT_BASE}.report.html"
echo "------------------------------------------------------------"

CHROME_FLAGS="--user-data-dir=$PROFILE_DIR --no-first-run --no-default-browser-check"

PRESET_FLAG=""
if [ "$FORM_FACTOR" = "desktop" ]; then
  PRESET_FLAG="--preset=desktop"
else
  PRESET_FLAG="--form-factor=mobile"
fi

echo "🚀 Executing Lighthouse audit..."

if [ -f "./frontend/node_modules/.bin/lighthouse" ]; then
  ./frontend/node_modules/.bin/lighthouse \
    "$URL" \
    --chrome-flags="$CHROME_FLAGS" \
    --only-categories="$CATEGORIES" \
    --output=html \
    --output=json \
    --output-path="$REPORT_BASE" \
    $PRESET_FLAG \
    --view
else
  npx -y lighthouse \
    "$URL" \
    --chrome-flags="$CHROME_FLAGS" \
    --only-categories="$CATEGORIES" \
    --output=html \
    --output=json \
    --output-path="$REPORT_BASE" \
    $PRESET_FLAG \
    --view
fi

echo "============================================================"
echo "✅ Audit completed!"
echo "   📄 HTML: ${REPORT_BASE}.report.html"
echo "   📄 JSON: ${REPORT_BASE}.report.json"
echo "============================================================"
