# Codex Project Recovery Manager

Codex Project Recovery Manager is a standalone, read-only desktop audit for people who have many local software projects. It turns metadata into evidence, a priority, recommended next steps, and a bounded prompt for Codex.

## Safety

The tool reads only metadata: paths, names of files and folders, and modification dates. It never opens project file contents. In particular, it never reads `.env`, passwords, tokens, keys, or private customer data. It never changes scanned projects.

## Run

Requires Python 3.11+ with Tkinter (included in standard Windows Python).

```powershell
python app.py
```

Click **Load safe demo**. The three included demonstration projects are synthetic and contain no private data.

## Test

```powershell
python -m unittest discover -s tests -v
```

## Competition materials

The full Devpost draft and video script are in the parent competition-planning folder. Before publishing, add the factual Codex `/feedback` session ID and verify that no private material is included.
