import argparse
import shlex
import sys
from pathlib import Path

from .scanner import git, render, root_of, scan


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="RepoGuard · revisa lo que vas a subir, sin mostrar secretos"
    )
    parser.add_argument("--path", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("scan")
    inspect.add_argument(
        "--all",
        action="store_true",
        help="Revisar todos los archivos del índice, no solo los cambios preparados",
    )
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--strict", action="store_true", help="Tratar advertencias como fallo")
    commands.add_parser("init", help="Crear configuración vacía sin modificar Git")
    hook = commands.add_parser("hook", help="Instalar un pre-commit solo si no existe")
    hook.add_argument("--install", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            report = scan(args.path, args.all)
            print(render(report, args.json))
            return int(
                any(issue["severity"] == "error" or args.strict for issue in report["issues"])
            )
        root = root_of(args.path)
        if args.command == "init":
            with (root / ".repoguard.toml").open("x", encoding="utf-8") as file:
                file.write("max_file_mb = 5\nignore = []\n")
            print("Configuración creada.")
        elif args.command == "hook":
            import subprocess

            configured = subprocess.run(
                ["git", "-C", str(root), "config", "--get", "core.hooksPath"], capture_output=True
            )
            if configured.returncode == 0:
                raise ValueError(
                    "El repositorio ya usa core.hooksPath; integra RepoGuard manualmente."
                )
            hook_dir = Path(git(root, "rev-parse", "--git-path", "hooks").decode().strip())
            if not hook_dir.is_absolute():
                hook_dir = root / hook_dir
            hook_dir.mkdir(parents=True, exist_ok=True)
            target = hook_dir / "pre-commit"
            executable = shlex.quote(Path(sys.executable).as_posix())
            with target.open("x", encoding="utf-8", newline="\n") as file:
                file.write(
                    "#!/bin/sh\nexec "
                    + executable
                    + (" scan\n" if getattr(sys, "frozen", False) else " -m repoguard.cli scan\n")
                )
            target.chmod(0o755)
            print("Hook instalado. Usa la instalación actual de Python; conserva ese entorno.")
        return 0
    except (ValueError, OSError) as error:
        print("RepoGuard: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
