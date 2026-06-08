# init.ps1 - Verificacion e inicializacion del entorno del Revisor de Natacion en Windows
#
# Este script comprueba la salud del entorno de desarrollo.
# Salida esperada: codigos de salida claros y bloques marcados con [OK]/[FAIL].

$ErrorActionPreference = "Stop"

function Write-Ok ($msg) {
    Write-Host "[OK]    $msg" -ForegroundColor Green
}

function Write-Warn ($msg) {
    Write-Host "[WARN]  $msg" -ForegroundColor Yellow
}

function Write-Fail ($msg) {
    Write-Host "[FAIL]  $msg" -ForegroundColor Red
}

$ExitCode = 0

Write-Host "-- 1. Verificando entorno de Python -------------"

# Deteccion robusta de Python en Windows (evitando el alias dummy de WindowsApps)
$pythonCmd = ""
$possiblePaths = @(
    "$env:LOCALAPPDATA\Python\bin\python.exe",
    "$env:USERPROFILE\AppData\Local\Python\bin\python.exe",
    "python.exe"
)

foreach ($path in $possiblePaths) {
    if ($path -eq "python.exe") {
        try {
            $ver = & python.exe --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pythonCmd = "python.exe"
                break
            }
        } catch {}
    } else {
        if (Test-Path $path) {
            try {
                $ver = & $path --version 2>&1
                $pythonCmd = $path
                break
            } catch {}
        }
    }
}

if ($pythonCmd -eq "") {
    Write-Fail "Python no esta instalado o no se encuentra en los paths esperados."
    exit 1
}

Write-Ok "python -> $pythonCmd ($ver)"

# Verificar version minima 3.10
$pyCheck = & $pythonCmd -c "import sys; print(int(sys.version_info >= (3, 10)))"
if ($pyCheck -ne "1") {
    Write-Fail "Se requiere Python >= 3.10 para el Revisor."
    exit 1
}
Write-Ok "Version de Python compatible (>= 3.10)"

Write-Host ""
Write-Host "-- 2. Verificando archivos base del arnes ----------"

$baseFiles = @("AGENTS.md", "feature_list.json", "progress/current.md", "docs/architecture.md", "docs/conventions.md", "docs/verification.md", "CHECKPOINTS.md")
foreach ($f in $baseFiles) {
    if (-not (Test-Path $f)) {
        Write-Fail "Falta archivo base en el arnes: $f"
        $ExitCode = 1
    } else {
        Write-Ok "Existe $f"
    }
}

# Verificar existencias de requirements
if (-not (Test-Path "../code/requirements.txt")) {
    Write-Warn "No se encuentra el archivo de requisitos en '../code/requirements.txt'"
} else {
    Write-Ok "Existe el archivo de dependencias '../code/requirements.txt'"
}

Write-Host ""
Write-Host "-- 3. Validando feature_list.json y specs -------"

$pythonScript = @'
import json, os, sys
try:
    data = json.load(open("feature_list.json", encoding="utf-8"))
    valid = {"pending", "spec_ready", "in_progress", "done", "blocked"}
    in_progress = [f for f in data["features"] if f["status"] == "in_progress"]
    if len(in_progress) > 1:
        print(f"[FAIL]  Hay {len(in_progress)} features en in_progress (maximo 1)")
        sys.exit(1)
    requires_spec = {"spec_ready", "in_progress", "done"}
    spec_errors = []
    for f in data["features"]:
        if f["status"] not in valid:
            print(f"[FAIL]  Estado invalido en feature {f['id']}: {f['status']}")
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
    print(f"[OK]    feature_list.json valido ({len(data['features'])} features)")
    print(f"[OK]    Specs presentes para features sdd con estado no-pending")
except SystemExit:
    raise
except Exception as e:
    print(f"[FAIL]  feature_list.json o specs invalidos: {e}")
    sys.exit(1)
'@

$pythonScript | Out-File -FilePath "__temp_validate.py" -Encoding ascii
try {
    $res = & $pythonCmd "__temp_validate.py" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "feature_list.json o specs invalidos:"
        Write-Host $res
        $ExitCode = 1
    } else {
        foreach ($line in ($res -split "`n")) {
            if ($line -like "*[OK]*") {
                Write-Ok ($line -replace "\[OK\]\s+", "")
            } elseif ($line -like "*[FAIL]*") {
                Write-Fail ($line -replace "\[FAIL\]\s+", "")
            }
        }
    }
} finally {
    if (Test-Path "__temp_validate.py") {
        Remove-Item "__temp_validate.py" -Force
    }
}

Write-Host ""
Write-Host "-- 4. Ejecutando tests unitarios con pytest -"

if (Test-Path "tests") {
    try {
        $testOut = & $pythonCmd -m pytest tests/ -v 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Todos los tests de pytest pasan correctamente"
        } else {
            Write-Fail "Hay tests fallando bajo pytest"
            Write-Host $testOut
            $ExitCode = 1
        }
    } catch {
        Write-Fail "Ocurrio un error al ejecutar pytest."
        $ExitCode = 1
    }
} else {
    Write-Warn "Carpeta tests/ no existe todavia"
}

Write-Host ""
Write-Host "-- 5. Resumen de Inicializacion ----------"

if ($ExitCode -eq 0) {
    Write-Ok "Entorno listo. Puedes empezar a trabajar."
} else {
    Write-Fail "Entorno NO esta listo. Resuelve los errores antes de avanzar."
}

exit $ExitCode
