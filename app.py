"""Standalone competition demo for Codex Project Recovery Manager.

This application is intentionally read-only. It examines project metadata only
and never opens file contents, including `.env` files and credentials.
"""

from __future__ import annotations

import json
import os
import re
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, ttk


ROOT = Path(__file__).resolve().parent
README_NAMES = {"readme.md", "readme.txt"}
ENTRY_POINTS = {"main.py", "app.py", "run.py", "start.py", "server.py", "manage.py"}
DEPENDENCY_DIRS = {".venv", "venv", "env", "node_modules"}
SECRET_NAMES = {".env", ".env.local", "tokens.json", "passwords.json", "secrets.json", "credentials.json"}


@dataclass(frozen=True)
class Evidence:
    severity: str
    title: str
    detail: str


@dataclass(frozen=True)
class Report:
    name: str
    path: str
    priority: str
    score: int
    evidence: tuple[Evidence, ...]
    actions: tuple[str, ...]

    @property
    def prompt(self) -> str:
        evidence = "\n".join(f"- {item.title}: {item.detail}" for item in self.evidence) or "- No critical signals found."
        actions = "\n".join(f"- {item}" for item in self.actions)
        return f"""# Task: recover {self.name}

Work only in: `{self.path}`

## Audit evidence
{evidence}

## Requested work
{actions}

## Safety boundaries
- Show a short plan and the files you intend to change before editing.
- Do not delete, move, or overwrite files without explicit confirmation.
- Do not open or print `.env`, tokens, passwords, keys, or private data.
- Do not change business logic outside the requested scope.
- Run the safest available verification after changes and report the result.
"""


def _children(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def _priority(score: int) -> str:
    if score >= 8:
        return "now"
    if score >= 3:
        return "later"
    return "archive for confirmation"


def scan_project(project: dict, all_projects: list[dict], now: datetime | None = None) -> Report:
    """Scan names, folders and dates only; no file content is read."""
    name = str(project.get("name") or "Untitled project").strip()
    raw_path = str(project.get("path") or "").strip()
    path = Path(raw_path)
    evidence: list[Evidence] = []
    actions: list[str] = []
    score = 0
    if not raw_path or not path.is_dir():
        evidence.append(Evidence("high", "Project folder unavailable", "The recorded folder does not exist or cannot be accessed."))
        actions.append("Confirm the current project location; do not recreate or move folders automatically.")
        score = 8
    else:
        children = _children(path)
        names = {child.name.casefold() for child in children}
        if not names.intersection(README_NAMES):
            evidence.append(Evidence("medium", "README missing", "No README was found in the project root."))
            actions.append("Add a short README with purpose, installation, run and test instructions.")
            score += 3
        if not any((child.is_dir() and child.name.casefold() in {"tests", "test"}) or (child.is_file() and child.name.casefold().startswith("test_") and child.suffix == ".py") for child in children):
            evidence.append(Evidence("medium", "No visible tests", "No tests folder or top-level test_*.py file was found."))
            actions.append("Add one safe test for the most important behavior.")
            score += 3
        if ".git" not in names:
            evidence.append(Evidence("low", "Local Git metadata missing", "No .git folder was found in the project root."))
            actions.append("Confirm whether this project should be tracked with Git.")
            score += 1
        if not names.intersection(ENTRY_POINTS):
            evidence.append(Evidence("low", "No obvious entry point", "No common Python entry-point filename was found."))
            actions.append("Document the correct way to start this project.")
            score += 1
        dependencies = sorted(child.name for child in children if child.is_dir() and child.name.casefold() in DEPENDENCY_DIRS)
        if dependencies:
            evidence.append(Evidence("low", "Local dependencies found", f"Detected: {', '.join(dependencies)}. Do not publish these folders."))
        secret_files = sorted(child.name for child in children if child.name.casefold() in SECRET_NAMES)
        if secret_files:
            evidence.append(Evidence("low", "Secret-like filename detected", f"Detected: {', '.join(secret_files)}. Contents were not read."))
        mtimes = []
        for child in children:
            try:
                mtimes.append(child.stat().st_mtime)
            except OSError:
                pass
        if mtimes:
            reference = now or datetime.now(timezone.utc)
            age_days = int(max(0, (reference.timestamp() - max(mtimes)) / 86400))
            if age_days >= 180:
                evidence.append(Evidence("medium", "Stale project", f"The newest top-level change is about {age_days} days old."))
                actions.append("Decide whether to resume, document, or archive this project.")
                score += 3
    same_name = sum(1 for item in all_projects if str(item.get("name") or "").casefold() == name.casefold())
    if same_name > 1:
        evidence.append(Evidence("medium", "Duplicate project name", "More than one project has the same name."))
        actions.append("Compare the entries and mark the current version without deleting copies.")
        score += 3
    if not actions:
        actions.append("Verify the project run path and document its current state before new work.")
    return Report(name, raw_path, _priority(score), score, tuple(evidence), tuple(actions))


def scan_projects(projects: list[dict]) -> list[Report]:
    return sorted((scan_project(project, projects) for project in projects), key=lambda report: (-report.score, report.name.casefold()))


def render_report(report: Report) -> str:
    evidence = "\n".join(f"- [{item.severity}] {item.title}: {item.detail}" for item in report.evidence) or "- No critical signals found."
    actions = "\n".join(f"- {item}" for item in report.actions)
    return f"""# {report.name}

Priority: **{report.priority}** (score {report.score})
Path: `{report.path}`

## Evidence
{evidence}

## Recommended next steps
{actions}

## Safe Codex prompt
{report.prompt}
"""


class RecoveryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Codex Project Recovery Manager")
        self.geometry("1180x760")
        self.minsize(850, 580)
        self.reports: list[Report] = []
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        tk.Label(self, text="A read-only audit. It inspects metadata only and never opens secrets or changes projects.", anchor="w", wraplength=1080).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        controls = tk.Frame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        tk.Button(controls, text="Load safe demo", command=self.load_demo).pack(side="left", padx=(0, 5))
        tk.Button(controls, text="Copy Codex prompt", command=self.copy_prompt).pack(side="left", padx=(0, 5))
        tk.Button(controls, text="Export Markdown report", command=self.export_report).pack(side="left")
        pane = ttk.Panedwindow(self, orient="vertical")
        pane.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 5))
        top, bottom = tk.Frame(pane), tk.Frame(pane)
        pane.add(top, weight=2)
        pane.add(bottom, weight=3)
        top.columnconfigure(0, weight=1); top.rowconfigure(0, weight=1)
        columns = ("project", "priority", "score", "evidence")
        self.tree = ttk.Treeview(top, columns=columns, show="headings")
        for column, title, width in (("project", "Project", 260), ("priority", "Priority", 170), ("score", "Score", 70), ("evidence", "Evidence", 650)):
            self.tree.heading(column, text=title); self.tree.column(column, width=width, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected())
        scrollbar = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.grid(row=0, column=1, sticky="ns")
        bottom.columnconfigure(0, weight=1); bottom.rowconfigure(0, weight=1)
        self.details = tk.Text(bottom, wrap="word", font=("Consolas", 10), state="disabled")
        self.details.grid(row=0, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(bottom, orient="vertical", command=self.details.yview)
        self.details.configure(yscrollcommand=detail_scroll.set); detail_scroll.grid(row=0, column=1, sticky="ns")
        self.status = tk.StringVar(value="Load the safe demo to begin.")
        tk.Label(self, textvariable=self.status, anchor="w").grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

    def load_demo(self):
        entries = json.loads((ROOT / "demo_projects.json").read_text(encoding="utf-8"))
        for entry in entries:
            entry["path"] = str((ROOT / entry["path"]).resolve())
        self.reports = scan_projects(entries)
        self.tree.delete(*self.tree.get_children())
        for index, report in enumerate(self.reports):
            summary = "; ".join(item.title for item in report.evidence[:3]) or "No critical signals"
            self.tree.insert("", "end", iid=str(index), values=(report.name, report.priority, report.score, summary))
        if self.reports:
            self.tree.selection_set("0"); self.show_selected()
        self.status.set("Loaded three safe demo projects. No private folders or credentials are used.")

    def selected(self) -> Report | None:
        selected = self.tree.selection()
        return self.reports[int(selected[0])] if selected else None

    def show_selected(self):
        report = self.selected()
        if not report:
            return
        self.details.configure(state="normal"); self.details.delete("1.0", "end")
        self.details.insert("1.0", render_report(report)); self.details.configure(state="disabled")

    def copy_prompt(self):
        report = self.selected()
        if report:
            self.clipboard_clear(); self.clipboard_append(report.prompt)
            self.status.set("Copied a bounded, safe prompt for Codex.")

    def export_report(self):
        report = self.selected()
        if not report:
            return
        filename = re.sub(r"[^A-Za-z0-9_-]+", "-", report.name) + ".md"
        target = filedialog.asksaveasfilename(defaultextension=".md", initialfile=filename, filetypes=[("Markdown", "*.md")])
        if target:
            Path(target).write_text(render_report(report), encoding="utf-8")
            self.status.set(f"Exported report: {target}")


if __name__ == "__main__":
    RecoveryApp().mainloop()
