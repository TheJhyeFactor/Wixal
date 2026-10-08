"""Open the canonical installed or staged native app."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
installed=Path("/Applications/Wixal.app")
app=installed if installed.exists() else root/"release/native/Wixal.app"
if not app.exists():raise SystemExit("Build the native app with ./script/build_and_run.sh --package-only first.")
subprocess.run(["codesign","--verify","--deep","--strict",str(app)],check=True)
subprocess.run(["open",str(app)],check=True)
print(app)
