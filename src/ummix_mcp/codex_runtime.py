"""Descoberta do executável nativo sem depender do PATH particular do app Codex."""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexExecutable:
    path: str | None
    source: str
    error: str | None = None


def discover_codex(command: str | None = None) -> CodexExecutable:
    configured = command if command is not None else os.environ.get("UMMIX_CODEX_PATH")
    if configured is not None:
        value = os.path.expandvars(configured.strip().strip('"'))
        candidate = Path(value).expanduser()
        resolved = str(candidate.resolve()) if value and candidate.is_file() else shutil.which(value) if value else None
        if not resolved or Path(resolved).suffix.lower() in {".cmd", ".bat", ".ps1"}:
            return CodexExecutable(None, "configurado", "UMMIX_CODEX_PATH/--codex-path inválido: indique o executável nativo codex.exe, não um comando shell ou atalho.")
        return CodexExecutable(str(Path(resolved).resolve()), "configurado")

    for name in (("codex.exe", "codex") if sys.platform == "win32" else ("codex",)):
        resolved = shutil.which(name)
        if resolved and Path(resolved).suffix.lower() not in {".cmd", ".bat", ".ps1"}:
            return CodexExecutable(str(Path(resolved).resolve()), "PATH")

    # O instalador desktop observado mantém binários em uma pasta por versão.
    # Busca limitada à instalação do fornecedor; não varre disco nem lê credenciais.
    if sys.platform == "win32":
        roots = {Path.home() / "AppData/Local/OpenAI/Codex/bin"}
        if os.environ.get("LOCALAPPDATA"):
            roots.add(Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin")
        try:
            candidates = [p for root in roots for p in [root / "codex.exe", *root.glob("*/codex.exe")] if p.is_file()]
            candidates.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
            if candidates:
                return CodexExecutable(str(candidates[0].resolve()), "instalação desktop Codex")
        except OSError:
            pass
    return CodexExecutable(None, "não encontrado", "Codex CLI não encontrado no PATH ou na instalação desktop. Use --codex-path com o executável nativo instalado.")
