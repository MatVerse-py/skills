#!/bin/bash
set -e

echo "🔍 Validando ambiente MatVerse..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

if ! command -v pip &> /dev/null; then
    echo "❌ pip não encontrado"
    exit 1
fi
echo "✅ pip: $(pip --version)"

if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
else
    echo "⚠️ Docker não encontrado – você usará modo manual"
fi

mkdir -p artifacts/ledger artifacts/reports artifacts/experiments

echo "📦 Instalando dependências Python..."
pip install -q -r requirements-oracle.txt 2>/dev/null || echo "⚠️ requirements-oracle.txt não encontrado, ignorado"
pip install -q -e . 2>/dev/null || echo "⚠️ Instalação local falhou, continuando"

echo "🧪 Testando motor..."
python -c "
from lib.matverse_engine import evaluateField
result = evaluateField([])
assert result['decision'] in ('PASS', 'CONDITIONAL', 'BLOCK')
print('✅ Motor OK, decisão:', result['decision'])
"

if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Bunker está respondendo"
else
    echo "⚠️ Bunker não está acessível (pode ser normal se não iniciado)"
fi

echo "✅ Validação concluída com sucesso!"
