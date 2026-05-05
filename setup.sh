#!/usr/bin/env bash
set -e

echo "[*] Job-AI-Agent Linux Setup"

if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[*] Installing Playwright Chromium (bundled, no system Chrome needed)..."
playwright install chromium
playwright install-deps chromium

if [ ! -f "authorization.txt" ]; then
    echo "[!] Creating authorization.txt template..."
    cat > authorization.txt << 'EOF'
OPENAI_API_KEY=your-key-here
RECIPIENT_EMAIL=your-email@example.com
AI_ENABLED=True
FILTER_ENABLED=True
AUTO_SCAN_ENABLED=False
EOF
    echo "[!] Fill in authorization.txt before running."
fi

echo ""
echo "[OK] Done. Run: source venv/bin/activate && python run_pipeline.py"
