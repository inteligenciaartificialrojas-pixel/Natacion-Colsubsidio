#!/usr/bin/env bash
# init.sh — Verificación e inicialización del entorno del Revisor de Natación
#
# Salida esperada: códigos de salida claros y bloques marcados con [OK]/[FAIL].

set -u
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$1"; }

EXIT_CODE=0

echo "── 1. Verificando entorno de Python ───────────────────────"

# Python disponible
if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 no está instalado"
  exit 1
fi
ok "python3 -> $(python3 --version)"

# Versión mínima 3.10
PY_VERSION_OK=$(python3 -c 'import sys; print(int(sys.version_info >= (3, 10)))')
if [ "$PY_VERSION_OK" != "1" ]; then
  fail "Se requiere Python >= 3.10"
  exit 1
fi
ok "Versión de Python compatible (>= 3.10)"

echo ""
echo "── 2. Verificando archivos base del arnés ──────────"

for f in AGENTS.md feature_list.json progress/current.md docs/architecture.md docs/conventions.md docs/verification.md CHECKPOINTS.md; do
  if [ ! -f "$f" ]; then
    fail "Falta archivo base en el arnés: $f"
    EXIT_CODE=1
  else
    ok "Existe $f"
  fi
done

# Verificar existencia de requirements.txt
if [ ! -f "../code/requirements.txt" ]; then
  warn "No se encuentra el archivo de requisitos en '../code/requirements.txt'"
else
  ok "Existe el archivo de dependencias '../code/requirements.txt'"
fi

echo ""
echo "── 3. Validando feature_list.json y specs ───────"

python3 - <<'PY'
import json, os, sys
try:
    data = json.load(open("feature_list.json", encoding="utf-8"))
    valid = {"pending", "spec_ready", "in_progress", "done", "blocked"}
    in_progress = [f for f in data["features"] if f["status"] == "in_progress"]
    if len(in_progress) > 1:
        print(f"[FAIL]  Hay {len(in_progress)} features en in_progress (máximo 1)")
        sys.exit(1)
    requires_spec = {"spec_ready", "in_progress", "done"}
    spec_errors = []
    for f in data["features"]:
        if f["status"] not in valid:
            print(f"[FAIL]  Estado inválido en feature {f['id']}: {f['status']}")
            sys.exit(1)
        if f.get("sdd") and f["status"] in requires_spec:
            spec_dir = os.path.join("specs", f["name"])
            for fname in ("requirements.md", "design.md", "tasks.md"):
                if not os.path.isfile(os.path.join(spec_dir, fname)):
                    spec_errors.append(
                        f"feature {f['id']} ({f['name']}) en {f['status']} "
                        f"sin {spec_dir}/{fname}"
                    )
    if spec_errors:
        for e in spec_errors:
            print(f"[FAIL]  {e}")
        sys.exit(1)
    print(f"[OK]    feature_list.json válido ({len(data['features'])} features)")
    print(f"[OK]    Specs presentes para features sdd con estado no-pending")
except SystemExit:
    raise
except Exception as e:
    print(f"[FAIL]  feature_list.json o specs inválidos: {e}")
    sys.exit(1)
PY

if [ $? -ne 0 ]; then EXIT_CODE=1; fi

echo ""
echo "── 4. Ejecutando tests unitarios con pytest ─"

if [ -d "tests" ]; then
  if python3 -m pytest tests/ -v 2>&1; then
    ok "Todos los tests de pytest pasan correctamente"
  else
    fail "Hay tests fallando bajo pytest"
    EXIT_CODE=1
  fi
else
  warn "Carpeta tests/ no existe todavía"
fi

echo ""
echo "── 5. Resumen de Inicialización ────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
  ok "Entorno listo. Puedes empezar a trabajar."
else
  fail "Entorno NO está listo. Resuelve los errores antes de avanzar."
fi

exit $EXIT_CODE
