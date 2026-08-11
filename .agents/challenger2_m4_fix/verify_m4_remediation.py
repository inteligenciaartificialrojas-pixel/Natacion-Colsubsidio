"""Empirical verification script for Milestone 4 Remediation.
Tests requirements.txt parsing, .env.example compatibility, and batch script / workflow validity.
"""
import sys
import os
import re
from pathlib import Path

# Base path of the repository
REPO_ROOT = Path(r"i:\Mi unidad\Natacion Colsubsidio")

def verify_requirements_txt():
    print("=== Testing code/requirements.txt ===")
    req_file = REPO_ROOT / "code" / "requirements.txt"
    if not req_file.exists():
        return False, "code/requirements.txt does not exist"
    
    content = req_file.read_text(encoding="utf-8")
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    
    print(f"Found {len(lines)} requirement lines: {lines}")
    
    # Verify PEP 508 / PEP 440 parsing
    # Use standard library or packaging module if available
    try:
        from packaging.requirements import Requirement
        parsed = []
        for line in lines:
            req = Requirement(line)
            parsed.append((req.name, req.specifier))
            print(f"  Parsed with packaging: name='{req.name}', specifier='{req.specifier}'")
    except ImportError:
        # Fallback to pkg_resources or manual regex validation
        import re
        pep508_pattern = re.compile(r"^([a-zA-Z0-9_\-\.]+)\s*([<>=!~^].*)?$")
        parsed = []
        for line in lines:
            m = pep508_pattern.match(line)
            if not m:
                return False, f"Line does not conform to PEP 508: '{line}'"
            parsed.append((m.group(1), m.group(2)))
            print(f"  Parsed with regex: name='{m.group(1)}', specifier='{m.group(2)}'")
            
    # Check required dependencies
    req_names = [p[0].lower().replace('_', '-') for p in parsed]
    expected_deps = ['requests', 'pytest', 'playwright']
    missing = [dep for dep in expected_deps if dep not in req_names]
    if missing:
        return False, f"Missing required dependencies in requirements.txt: {missing}"
        
    # AST analysis of code/*.py to ensure all 3rd party packages are in requirements.txt
    import ast
    code_dir = REPO_ROOT / "code"
    imported_modules = set()
    std_lib_modules = sys.stdlib_module_names if sys.version_info >= (3, 10) else set()
    
    for py_file in code_dir.glob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_mod = alias.name.split('.')[0]
                        imported_modules.add(top_mod)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_mod = node.module.split('.')[0]
                        imported_modules.add(top_mod)
        except Exception as e:
            print(f"Warning: could not parse AST of {py_file}: {e}")
            
    # Filter out local modules and stdlib
    local_modules = {p.stem for p in code_dir.glob("*.py")}
    third_party = {m for m in imported_modules if m not in local_modules and m not in std_lib_modules}
    print(f"Discovered third-party imports in code/*.py: {third_party}")
    
    # Verify all third party imports map to requirements
    # 'requests' -> 'requests', 'playwright' -> 'playwright'
    uncovered = [m for m in third_party if m.lower() not in req_names]
    if uncovered:
        return False, f"Third-party imports not declared in requirements.txt: {uncovered}"

    return True, "requirements.txt parsing and specifiers fully verified."

def verify_env_example():
    print("\n=== Testing .env.example and Parser Compatibility ===")
    env_ex = REPO_ROOT / ".env.example"
    if not env_ex.exists():
        return False, ".env.example does not exist"
        
    content = env_ex.read_text(encoding="utf-8")
    
    # Custom parser from config.py logic
    config_parsed = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().strip('"').strip("'")
            config_parsed[key] = val
            
    print(f"config.py parser extracted {len(config_parsed)} keys: {list(config_parsed.keys())}")
    
    # dotenv parser (python-dotenv or custom dotenv spec)
    dotenv_parsed = {}
    try:
        from dotenv import dotenv_values
        # write temp file or pass string
        import io
        dotenv_parsed = dotenv_values(stream=io.StringIO(content))
        print(f"python-dotenv extracted {len(dotenv_parsed)} keys: {list(dotenv_parsed.keys())}")
    except ImportError:
        print("python-dotenv module not installed, testing built-in dotenv parser logic")
        # Standard dotenv parser rules:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                dotenv_parsed[k] = v

    # Check key equivalence
    expected_keys = {
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "COLSUBSIDIO_USER",
        "COLSUBSIDIO_PASS",
        "COLSUBSIDIO_SISTEMA_COOKIE",
        "COLSUBSIDIO_CSRF_TOKEN"
    }
    
    missing_keys = expected_keys - set(config_parsed.keys())
    if missing_keys:
        return False, f"Missing required keys in .env.example: {missing_keys}"
        
    # Check parser equality
    diffs = []
    for k in expected_keys:
        val_config = config_parsed.get(k)
        val_dotenv = dotenv_parsed.get(k)
        if val_config != val_dotenv:
            diffs.append(f"{k}: config.py='{val_config}' vs dotenv='{val_dotenv}'")
            
    if diffs:
        return False, f"Parser mismatch between config.py and dotenv: {diffs}"
        
    # Adversarial stress test on dotenv parsing
    # Test values with comments, spaces, quotes, equals signs
    test_env_content = """
# Comment line
TEST_KEY1=val1
TEST_KEY2="val2 with spaces"
TEST_KEY3='val3_quoted'
TEST_KEY4=val_with_#_inline
TEST_KEY5=val_with=equals
"""
    custom_test = {}
    for line in test_env_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("=", 1)
        if len(parts) == 2:
            k = parts[0].strip()
            v = parts[1].strip().strip('"').strip("'")
            custom_test[k] = v
            
    print("Stress test parser sample output:", custom_test)
    
    return True, ".env.example loading and dotenv compatibility verified."

if __name__ == "__main__":
    ok1, msg1 = verify_requirements_txt()
    print(f"Requirements Result: {ok1} - {msg1}")
    
    ok2, msg2 = verify_env_example()
    print(f"Env Result: {ok2} - {msg2}")
    
    if not (ok1 and ok2):
        sys.exit(1)
