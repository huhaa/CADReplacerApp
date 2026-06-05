# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoCAD批量文字替换工具 (AutoCAD Batch Text Replacer) — a Windows desktop GUI application that performs find-and-replace on text inside AutoCAD DWG files. Built with PySide6 and COM automation (win32com).

## Python Environment

All Python operations MUST use the fixed virtual environment at `C:\Users\DHB_HOME\opense`:

```bash
# Run the app (V2)
C:\Users\DHB_HOME\opense\Scripts\python.exe run.py

# Run tests
C:\Users\DHB_HOME\opense\Scripts\python.exe -m pytest tests/

# Install dependencies
C:\Users\DHB_HOME\opense\Scripts\python.exe -m pip install <package>
```

## Build (Standalone EXE)

Use PyInstaller with the spec file:

```bash
C:\Users\DHB_HOME\opense\Scripts\python.exe -m PyInstaller CADReplacerApp.spec
```

The spec file bundles `src/main.py` as a windowed (no console) EXE with the DHB.ico icon and UPX compression. It includes `pictures/` and `help_file/` as bundled data directories.

## Architecture (V2 — Modular MVP)

The application uses an **MVP (Model-View-Presenter)** architecture split across the `src/` package:

```
run.py                     # Launcher script
src/
├── main.py                # App entry point, QApplication + logging setup
├── model.py               # Data classes (ReplaceRule, ScopeConfig, FileStatus, FileResult)
├── view.py                # PySide6 GUI (MainView + IMainView interface)
├── presenter.py           # Business logic, connects View ↔ Model
├── cad_worker.py          # QThread worker for AutoCAD COM automation
└── config.py              # JSON config persistence (ConfigManager)
```

### Core Classes

- **`IMainView` (ABC)** — Abstract interface that Presenter depends on; no direct Qt coupling.
- **`MainView(QMainWindow, IMainView)`** — Main window implementing the view interface. Manages find/replace rule list, file selection list, scope checkboxes (plain text / multiline text / block attributes / nested blocks / paper space), progress bar, and action buttons.
- **`ViewSignals(QObject)`** — Signal bus emitted by the view, connected by the Presenter.
- **`ReplacerModel`** — Holds all application state: rule list, file list, processing state, undo snapshot.
- **`ReplacerPresenter`** — Orchestrates the pipeline: validates input, spawns CADWorker, updates progress, handles undo.
- **`CADWorker(QThread)`** — Runs AutoCAD COM automation in a background thread. Opens DWG files, iterates entities in model space and paper space (including nested block references), applies find/replace rules, saves and closes.
- **`ConfigManager`** — Loads/saves `config.json` (rules, scope, recent files, window geometry).

### Processing Pipeline

1. User adds find→replace rules and selects DWG files via the GUI.
2. On "Start", Presenter validates inputs and spawns a `CADWorker` thread.
3. `CADWorker` connects to AutoCAD via COM (`win32com.client.Dispatch` / `GetActiveObject`).
4. For each DWG file, it opens the document, retrieves `ModelSpace` (and `PaperSpace` if enabled), and iterates entities.
5. Handles `AcDbText`, `AcDbMText`, and `AcDbBlockReference` (recursing into nested blocks via `GetAttributes()` for `AcDbAttribute` and iterating block definition entities).
6. `apply_rules()` performs regex or literal `str.replace()` for each find/replace pair on `entity.TextString`.
7. Each file is saved and closed. AutoCAD is quit after all files are processed.
8. Progress updates are emitted via Qt Signals to the main thread.

### Key Dependencies

- **PySide6** — Qt for Python (GUI framework)
- **pywin32** (`win32com.client`, `pythoncom`) — COM automation to drive AutoCAD
- **PyInstaller** — Packaging into standalone Windows EXE

### Critical COM Details

- `pythoncom.CoInitialize()` must be called before any COM Dispatch (single-threaded apartment requirement).
- File open retry logic (3 attempts) handles `HRESULT -2147418111` (COM call rejected) by re-initializing the AutoCAD connection.
- A 5-second sleep after connecting to AutoCAD and 2-second sleeps after opening files are intentional — AutoCAD needs time to fully load documents.
- The `update_progress` Signal is used to safely update the progress bar from the worker thread (Qt requires GUI updates on the main thread).

### Legacy Files

- `CADReplacerApp.py` — V1 monolithic single-file version (kept for reference only, not the active version).
- Numbered files (`01`–`05`) — Prior iterations kept for historical reference.
- `no_gui_test.py` — Standalone non-GUI test script for COM connectivity.
