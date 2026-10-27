"""Refresh the approved public snapshot and static build in one local command."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group-id", type=int, default=233120758)
    parser.add_argument("--group-name", default="ALT Studios!")
    parser.add_argument("--counts-only", action="store_true")
    parser.add_argument("--no-balance", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Commit only the public JSON and push using this repository's existing Git remote")
    args = parser.parse_args()
    command = [sys.executable, str(ROOT / "tools" / "export_analytics.py"),
               "--group-id", str(args.group_id), "--group-name", args.group_name]
    if not args.counts_only:
        command.append("--include-financials")
    if not args.no_balance:
        command.append("--include-balance")
    subprocess.run(command, check=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py")], check=True)
    if args.publish:
        public_file = "data/ugc-stats.json"
        subprocess.run(["git", "add", "--", public_file], cwd=ROOT, check=True)
        changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", public_file], cwd=ROOT)
        if changed.returncode == 1:
            subprocess.run(["git", "commit", "--only", "-m", "Refresh public UGC analytics", "--", public_file], cwd=ROOT, check=True)
        elif changed.returncode != 0:
            raise SystemExit("Could not inspect the public snapshot change; publish stopped.")
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        print("Public snapshot pushed. Cloudflare can deploy it through the existing GitHub integration.")
    print('Preview: python -m http.server 8000 --bind 127.0.0.1 --directory "' + str(ROOT / "dist") + '"')


if __name__ == "__main__":
    main()
