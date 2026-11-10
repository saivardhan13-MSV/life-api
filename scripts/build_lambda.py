"""Build build/lambda.zip for the arm64 Python 3.12 Lambda runtime.

Works on Windows, macOS and Linux: pip downloads manylinux aarch64 wheels
instead of building for the local machine. boto3 is already in the Lambda
runtime, so it's left out to keep the package small.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# LIFE_BUILD_DIR helps on Windows, where deep paths can hit the 260-char limit.
BUILD = Path(os.environ.get("LIFE_BUILD_DIR", ROOT / "build"))
PKG = BUILD / "package"
ZIP = BUILD / "lambda.zip"
EXCLUDE = {"boto3", "botocore", "s3transfer", "jmespath"}


def main() -> None:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    deps = [d for d in deps if d.split(">")[0].split("=")[0].strip() not in EXCLUDE]

    shutil.rmtree(BUILD, ignore_errors=True)
    PKG.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--target",
            str(PKG),
            "--platform",
            "manylinux2014_aarch64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--only-binary=:all:",
            *deps,
        ],
        check=True,
    )
    shutil.copytree(ROOT / "src" / "life_api", PKG / "life_api")

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in PKG.rglob("*"):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            zf.write(path, path.relative_to(PKG))
    print(f"built {ZIP} ({ZIP.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
