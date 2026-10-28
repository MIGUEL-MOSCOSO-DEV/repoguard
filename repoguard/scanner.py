import fnmatch
import json
import re
import subprocess
import tomllib
from pathlib import Path

RULES = {
    "private-key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "github-token": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{40,255})"
    ),
    "aws-access-key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "stripe-secret": re.compile(rb"\bsk_live_[A-Za-z0-9]{20,255}"),
    "credential-assignment": re.compile(
        rb"(?i)(?:password|api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*[\"']([A-Za-z0-9_+/=-]{24,255})[\"']"
    ),
}


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError(
            "No se pudo leer Git. Comprueba que estás dentro de un repositorio válido."
        )
    return result.stdout


def root_of(path):
    return Path(git(path, "rev-parse", "--show-toplevel").decode().strip())


def config_for(root):
    path = root / ".repoguard.toml"
    if not path.exists():
        return {"ignore": [], "max_file_mb": 5}
    with path.open("rb") as file:
        config = tomllib.load(file)
    ignored = config.get("ignore", [])
    maximum = config.get("max_file_mb", 5)
    if (
        not isinstance(ignored, list)
        or not all(isinstance(item, str) for item in ignored)
        or type(maximum) is not int
        or not 1 <= maximum <= 100
    ):
        raise ValueError("Configuración inválida: ignore es una lista y max_file_mb va de 1 a 100.")
    return {"ignore": ignored, "max_file_mb": maximum}


def scan_bytes(content, path):
    issues = []
    if b"\0" in content[:8192]:
        return issues
    for rule, pattern in RULES.items():
        for match in pattern.finditer(content):
            issues.append(
                {
                    "severity": "error",
                    "rule": rule,
                    "path": path,
                    "line": content.count(b"\n", 0, match.start()) + 1,
                    "message": "Posible credencial. Revisa el archivo; el valor no se muestra.",
                }
            )
            if len(issues) >= 100:
                return issues
    return issues


def scan(path, all_tracked=False):
    root = root_of(path)
    config = config_for(root)
    changed = (
        None
        if all_tracked
        else set(
            item.decode("utf-8", errors="replace")
            for item in git(
                root, "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z"
            ).split(b"\0")
            if item
        )
    )
    entries = []
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode().split()
        entries.append((mode, object_id, stage, name.decode("utf-8", errors="replace")))
    issues = []
    scanned = 0
    ignored_count = 0
    for mode, object_id, stage, name in entries:
        if changed is not None and name not in changed:
            continue
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in config["ignore"]):
            ignored_count += 1
            continue
        if stage != "0":
            issues.append(
                {
                    "severity": "error",
                    "rule": "merge-conflict",
                    "path": name,
                    "line": None,
                    "message": "Resuelve el conflicto antes de subir cambios.",
                }
            )
            continue
        if mode == "160000":
            continue
        scanned += 1
        if mode == "120000":
            issues.append(
                {
                    "severity": "warning",
                    "rule": "symlink",
                    "path": name,
                    "line": None,
                    "message": "Enlace simbólico; el contenido de su destino no se inspecciona.",
                }
            )
        size = int(git(root, "cat-file", "-s", object_id))
        if size > config["max_file_mb"] * 1024**2:
            issues.append(
                {
                    "severity": "error",
                    "rule": "large-file",
                    "path": name,
                    "line": None,
                    "message": f"Archivo de {size} bytes; supera el límite configurado. No se inspeccionó su contenido.",
                }
            )
            continue
        basename = Path(name).name.lower()
        if basename == ".env" or (
            basename.startswith(".env.")
            and not basename.endswith(("example", "sample", "template"))
        ):
            issues.append(
                {
                    "severity": "error",
                    "rule": "environment-file",
                    "path": name,
                    "line": None,
                    "message": "Archivo de entorno preparado para Git. Revisa si debe excluirse.",
                }
            )
        issues.extend(scan_bytes(git(root, "cat-file", "blob", object_id), name))
    tracked = {name.lower() for _, _, stage, name in entries if stage == "0"}
    for required, alternatives in {
        "README": ["readme.md", "readme.rst", "readme"],
        "LICENSE": ["license", "license.md", "license.txt", "licence"],
        ".gitignore": [".gitignore"],
    }.items():
        if not any(name in tracked for name in alternatives):
            issues.append(
                {
                    "severity": "warning",
                    "rule": "missing-file",
                    "path": required,
                    "line": None,
                    "message": "No está incluido en el índice del repositorio.",
                }
            )
    return {
        "scanned": scanned,
        "ignored": ignored_count,
        "scope": "tracked" if all_tracked else "staged",
        "issues": issues,
    }


def render(report, json_output=False):
    if json_output:
        return json.dumps(report, indent=2, ensure_ascii=False)
    output = [
        f"RepoGuard / {report['scope']} / {report['scanned']} archivos inspeccionados / {report['ignored']} excluidos"
    ]
    for issue in report["issues"]:
        location = issue["path"] + (":" + str(issue["line"]) if issue["line"] else "")
        output.append(
            f"{issue['severity'].upper():7} {issue['rule']:24} {location}\n        {issue['message']}"
        )
    if not report["issues"]:
        output.append("No se encontraron coincidencias con las reglas activas.")
    return "\n".join(output)
