# Source releases

Each release folder contains a source ZIP and a matching SHA-256 manifest. Packages exclude local credentials, databases, installed dependencies, caches and browser traces.

Generated ZIP files are kept locally and excluded from Git. Use GitHub's **Code → Download ZIP** for a repository snapshot, or generate an application-only package below. Existing local packages are in `2026-10-09-initial/` and `20261009T112138629868Z/`.

To package the current application, run from `application/`:

```powershell
.\backend\.venv\Scripts\python.exe .\tools\package_release.py
```

New packages are saved in a separate UTC timestamp folder here. Existing releases are preserved. The ZIP contains the application; the separate reference library and historical workspace documents are not included.
