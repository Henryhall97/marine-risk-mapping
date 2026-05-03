"""Launch ArcFace photo training on a remote AWS VM over SSH.

This helper is intentionally thin orchestration around the local
`train_arcface_classifier.py` script:

1. Sync the required project files to a remote machine (typically EC2)
   using `rsync` over SSH.
2. Bootstrap `uv` on the remote host if needed.
3. Run `uv sync` in the remote project directory.
4. Launch the ArcFace trainer remotely.
5. Optionally pull the trained model artifacts back to the local machine.

The remote VM only needs SSH access and outbound internet for Python
package/model downloads. No AWS SDK permissions are required unless you
want your own remote preparation step to fetch training data from S3.

Environment defaults
--------------------
The CLI reads these optional environment variables:

- `MR_AWS_TRAIN_HOST`
- `MR_AWS_TRAIN_USER`
- `MR_AWS_TRAIN_PORT`
- `MR_AWS_TRAIN_IDENTITY_FILE`
- `MR_AWS_TRAIN_REMOTE_DIR`

Example
-------
    uv run python pipeline/analysis/train_arcface_remote.py \
        --host ec2-3-12-34-56.eu-west-2.compute.amazonaws.com \
        --user ubuntu \
        --identity-file ~/.ssh/marine-risk.pem \
        --sync-photos \
        --download-artifacts
"""

from __future__ import annotations

import argparse
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from pipeline.config import (
    ARCFACE_BACKBONE,
    ARCFACE_BATCH_SIZE,
    ARCFACE_BROAD_MODEL_DIR,
    ARCFACE_EPOCHS,
    ARCFACE_IMAGE_SIZE,
    ARCFACE_MODEL_DIR,
)

log = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMOTE_ENV_PREFIX = "MR_AWS_TRAIN_"


def _env_default(name: str, default: str | None = None) -> str | None:
    return os.getenv(f"{REMOTE_ENV_PREFIX}{name}", default)


def _require_local_binary(name: str) -> None:
    """Fail fast if a required local CLI is missing."""
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required local binary '{name}' not found in PATH.")


def _run(cmd: list[str], dry_run: bool = False) -> None:
    """Run one local subprocess with logging."""
    log.info("$ %s", shlex.join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _ssh_base_args(
    user: str,
    host: str,
    port: int,
    identity_file: Path | None,
) -> tuple[list[str], str]:
    """Return SSH argv and rsync transport string."""
    ssh_args = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(port),
    ]
    if identity_file is not None:
        ssh_args.extend(["-i", str(identity_file)])
    ssh_args.append(f"{user}@{host}")

    transport_args = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(port),
    ]
    if identity_file is not None:
        transport_args.extend(["-i", str(identity_file)])
    return ssh_args, shlex.join(transport_args)


def _rsync_path(
    source: Path,
    remote_subdir: str,
    target: str,
    ssh_transport: str,
    remote_root: str,
    dry_run: bool = False,
) -> None:
    """Rsync one file or directory into the remote project tree."""
    if not source.exists():
        raise FileNotFoundError(f"Local path not found: {source}")

    remote_dest = f"{target}:{remote_root.rstrip('/')}/{remote_subdir}"
    cmd = ["rsync", "-az", "-e", ssh_transport]
    if source.is_dir():
        cmd.extend([f"{source}/", remote_dest.rstrip("/") + "/"])
    else:
        cmd.extend([str(source), remote_dest])
    _run(cmd, dry_run=dry_run)


def _pull_path(
    remote_subdir: str,
    target: str,
    ssh_transport: str,
    remote_root: str,
    local_dest: Path,
    dry_run: bool = False,
) -> None:
    """Rsync one directory back from the remote host."""
    local_dest.parent.mkdir(parents=True, exist_ok=True)
    remote_src = f"{target}:{remote_root.rstrip('/')}/{remote_subdir.rstrip('/')}/"
    cmd = [
        "rsync",
        "-az",
        "-e",
        ssh_transport,
        remote_src,
        str(local_dest),
    ]
    _run(cmd, dry_run=dry_run)


def _sync_project(
    target: str,
    ssh_transport: str,
    remote_root: str,
    sync_photos: bool,
    sync_env: bool,
    dry_run: bool,
) -> None:
    """Sync the code and optionally the photo dataset to the remote VM."""
    _rsync_path(
        PROJECT_ROOT / "pipeline",
        "pipeline",
        target,
        ssh_transport,
        remote_root,
        dry_run,
    )
    # Also sync the GPU bootstrap script so --prepare-command can reference it
    _rsync_path(
        PROJECT_ROOT / "pipeline" / "analysis" / "setup_ec2_gpu.sh",
        "pipeline/analysis/setup_ec2_gpu.sh",
        target,
        ssh_transport,
        remote_root,
        dry_run,
    )
    _rsync_path(
        PROJECT_ROOT / "pyproject.toml",
        "",
        target,
        ssh_transport,
        remote_root,
        dry_run,
    )

    uv_lock = PROJECT_ROOT / "uv.lock"
    if uv_lock.exists():
        _rsync_path(
            uv_lock,
            "",
            target,
            ssh_transport,
            remote_root,
            dry_run,
        )

    python_version = PROJECT_ROOT / ".python-version"
    if python_version.exists():
        _rsync_path(
            python_version,
            "",
            target,
            ssh_transport,
            remote_root,
            dry_run,
        )

    if sync_env:
        env_file = PROJECT_ROOT / ".env"
        if not env_file.exists():
            raise FileNotFoundError(
                "--sync-env was requested but .env does not exist locally."
            )
        _rsync_path(
            env_file,
            "",
            target,
            ssh_transport,
            remote_root,
            dry_run,
        )

    if sync_photos:
        _rsync_path(
            PROJECT_ROOT / "data" / "raw" / "whale_photos",
            "data/raw/whale_photos",
            target,
            ssh_transport,
            remote_root,
            dry_run,
        )


def _build_remote_train_command(args: argparse.Namespace) -> str:
    """Build the remote `uv run python ...` training command."""
    train_cmd: list[str] = [
        "uv",
        "run",
        "python",
        "pipeline/analysis/train_arcface_classifier.py",
        "--stage",
        args.stage,
        "--backbone",
        args.backbone,
        "--image-size",
        str(args.image_size),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
    ]
    if args.manifest:
        train_cmd.extend(["--manifest", args.manifest])
    if args.tune:
        train_cmd.append("--tune")
        train_cmd.extend(["--n-trials", str(args.n_trials)])
    return shlex.join(train_cmd)


def _run_remote_training(
    args: argparse.Namespace,
    ssh_args: list[str],
    dry_run: bool,
) -> None:
    """Execute the remote bootstrap + train workflow over SSH."""
    steps = [
        "set -euo pipefail",
        f"mkdir -p {shlex.quote(args.remote_dir)}",
        f"cd {shlex.quote(args.remote_dir)}",
        'export PATH="$HOME/.local/bin:$PATH"',
        (
            "if ! command -v uv >/dev/null 2>&1; then "
            "curl -LsSf https://astral.sh/uv/install.sh | sh; "
            "fi"
        ),
        'export PATH="$HOME/.local/bin:$PATH"',
    ]
    if not args.skip_uv_sync:
        steps.append("uv sync")
    if args.prepare_command:
        steps.append(args.prepare_command)
    steps.append(_build_remote_train_command(args))

    remote_script = " && ".join(steps)
    _run([*ssh_args, remote_script], dry_run=dry_run)


def _model_subdir(stage: str) -> str:
    """Return the repo-relative model output directory for a training stage."""
    if stage == "broad":
        return ARCFACE_BROAD_MODEL_DIR.as_posix()
    return ARCFACE_MODEL_DIR.as_posix()


def _download_artifacts(
    stage: str,
    target: str,
    ssh_transport: str,
    remote_root: str,
    include_mlruns: bool,
    dry_run: bool,
) -> None:
    """Pull the model outputs and optional MLflow files back locally."""
    model_subdir = _model_subdir(stage)
    _pull_path(
        model_subdir,
        target,
        ssh_transport,
        remote_root,
        PROJECT_ROOT / model_subdir,
        dry_run,
    )

    artifact_subdir = "data/processed/ml/artifacts/photo_classifier_arcface"
    _pull_path(
        artifact_subdir,
        target,
        ssh_transport,
        remote_root,
        PROJECT_ROOT / artifact_subdir,
        dry_run,
    )

    if include_mlruns:
        _pull_path(
            "mlruns",
            target,
            ssh_transport,
            remote_root,
            PROJECT_ROOT / "mlruns",
            dry_run,
        )


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Launch ArcFace training on a remote AWS VM over SSH"
    )
    parser.add_argument(
        "--host",
        default=_env_default("HOST"),
        help="Remote hostname or EC2 public DNS name.",
    )
    parser.add_argument(
        "--user",
        default=_env_default("USER", "ubuntu"),
        help="Remote SSH username (default: ubuntu).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_env_default("PORT", "22") or "22"),
        help="Remote SSH port (default: 22).",
    )
    parser.add_argument(
        "--identity-file",
        type=Path,
        default=(
            Path(_env_default("IDENTITY_FILE")).expanduser()
            if _env_default("IDENTITY_FILE")
            else None
        ),
        help="Path to the SSH private key (.pem).",
    )
    parser.add_argument(
        "--remote-dir",
        default=_env_default("REMOTE_DIR", "~/marine_risk_mapping"),
        help="Remote project directory (default: ~/marine_risk_mapping).",
    )
    parser.add_argument(
        "--stage",
        choices=["critical", "broad"],
        default="critical",
        help="ArcFace stage to train remotely.",
    )
    parser.add_argument(
        "--backbone",
        default=ARCFACE_BACKBONE,
        help="Remote timm backbone name.",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=ARCFACE_IMAGE_SIZE,
        help="Training image size passed to the trainer.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=ARCFACE_EPOCHS,
        help="Training epochs passed to the trainer.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=ARCFACE_BATCH_SIZE,
        help="Training batch size passed to the trainer.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Manifest path to pass through to the trainer. If supplied, it must "
            "be valid on the remote VM."
        ),
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run Optuna tuning on the remote VM before the main training run.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=20,
        help="Optuna trials when --tune is enabled.",
    )
    parser.add_argument(
        "--prepare-command",
        default=None,
        help=(
            "Extra remote shell command to run after `uv sync` and before "
            "training. Use this to bootstrap CUDA on a plain Ubuntu 24.04 VM: "
            '"bash ~/marine_risk_mapping/pipeline/analysis/setup_ec2_gpu.sh".'
        ),
    )
    parser.add_argument(
        "--sync-photos",
        action="store_true",
        help="Sync `data/raw/whale_photos/` to the remote VM before training.",
    )
    parser.add_argument(
        "--sync-env",
        action="store_true",
        help="Sync the local `.env` file to the remote project root.",
    )
    parser.add_argument(
        "--skip-code-sync",
        action="store_true",
        help="Skip rsyncing the local codebase before training.",
    )
    parser.add_argument(
        "--skip-uv-sync",
        action="store_true",
        help="Skip `uv sync` on the remote VM.",
    )
    parser.add_argument(
        "--download-artifacts",
        action="store_true",
        help="Pull the trained ArcFace model directory back after training.",
    )
    parser.add_argument(
        "--download-mlruns",
        action="store_true",
        help="Also pull the remote `mlruns/` directory back locally.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rsync / ssh commands without executing them.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.host:
        parser.error("--host is required (or set MR_AWS_TRAIN_HOST).")

    _require_local_binary("ssh")
    _require_local_binary("rsync")

    identity_file = args.identity_file.expanduser() if args.identity_file else None
    ssh_args, ssh_transport = _ssh_base_args(
        args.user,
        args.host,
        args.port,
        identity_file,
    )
    target = f"{args.user}@{args.host}"

    if not args.skip_code_sync:
        log.info("Syncing project files to %s ...", target)
        _sync_project(
            target=target,
            ssh_transport=ssh_transport,
            remote_root=args.remote_dir,
            sync_photos=args.sync_photos,
            sync_env=args.sync_env,
            dry_run=args.dry_run,
        )

    log.info("Launching remote ArcFace training on %s ...", target)
    _run_remote_training(args, ssh_args, dry_run=args.dry_run)

    if args.download_artifacts:
        log.info("Downloading trained artifacts from %s ...", target)
        _download_artifacts(
            stage=args.stage,
            target=target,
            ssh_transport=ssh_transport,
            remote_root=args.remote_dir,
            include_mlruns=args.download_mlruns,
            dry_run=args.dry_run,
        )

    log.info("Remote ArcFace workflow complete.")


if __name__ == "__main__":
    main()
