"""MLflow Model Registry management for marine risk models.

Provides utilities for promoting models from experiment runs to
the MLflow Model Registry, with staging → production lifecycle.

Usage:
    # Register the best SDM run as staging
    uv run python pipeline/analysis/register_model.py \\
        --experiment whale_sdm --model-name whale_sdm_xgboost

    # Register the best ISDM blue whale run
    uv run python pipeline/analysis/register_model.py \\
        --experiment isdm_species_sdm \\
        --model-name isdm_blue_whale_xgboost \\
        --filter "tags.species = 'blue_whale'"

    # Register the best seasonal right whale run
    uv run python pipeline/analysis/register_model.py \\
        --experiment whale_sdm_seasonal \\
        --model-name seasonal_right_whale_xgboost \\
        --filter "tags.target = 'right_whale_present'"

    # Promote staging → production
    uv run python pipeline/analysis/register_model.py \\
        --experiment whale_sdm --model-name whale_sdm_xgboost \\
        --promote production
"""

import argparse
import logging

import mlflow
from mlflow.tracking import MlflowClient

from pipeline.config import MLFLOW_TRACKING_URI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


def find_best_run(
    experiment_name: str,
    metric: str = "cv_avg_precision_mean",
    filter_string: str = "",
) -> str:
    """Find the run_id with the highest metric value.

    Parameters
    ----------
    experiment_name : str
        MLflow experiment name.
    metric : str
        Metric to rank runs by (descending).
    filter_string : str
        Optional MLflow search filter, e.g.
        ``"tags.species = 'blue_whale'"`` or
        ``"tags.target = 'right_whale_present'"``.
    """
    client = MlflowClient()
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise ValueError(f"Experiment '{experiment_name}' not found")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=filter_string,
        order_by=[f"metrics.{metric} DESC"],
        max_results=1,
    )
    if not runs:
        msg = f"No runs found in experiment '{experiment_name}'"
        if filter_string:
            msg += f" matching filter: {filter_string}"
        raise ValueError(msg)

    best_run = runs[0]
    log.info(
        "Best run: %s  %s=%.4f",
        best_run.info.run_id,
        metric,
        best_run.data.metrics.get(metric, 0),
    )
    return best_run.info.run_id


def register_model(
    run_id: str,
    model_name: str,
    artifact_path: str = "model",
) -> int:
    """Register a model from an MLflow run.

    Returns the new model version number.
    """
    client = MlflowClient()
    model_uri = f"runs:/{run_id}/{artifact_path}"

    # Create registered model if it doesn't exist
    try:
        client.create_registered_model(
            model_name,
            description=(
                f"Marine risk mapping — {model_name}. Registered from run {run_id}."
            ),
        )
        log.info("Created registered model: %s", model_name)
    except mlflow.exceptions.MlflowException:
        log.info("Registered model '%s' already exists", model_name)

    # Create new version
    mv = client.create_model_version(
        name=model_name,
        source=model_uri,
        run_id=run_id,
    )
    log.info(
        "Registered model version %s for '%s'",
        mv.version,
        model_name,
    )
    return int(mv.version)


def transition_model(
    model_name: str,
    version: int | None = None,
    stage: str = "Staging",
) -> None:
    """Transition a model version to a new stage.

    If no version is specified, transitions the latest version.
    Valid stages: 'Staging', 'Production', 'Archived', 'None'.
    """
    client = MlflowClient()

    if version is None:
        # Get the latest version
        versions = client.get_latest_versions(model_name)
        if not versions:
            raise ValueError(f"No versions found for model '{model_name}'")
        version = max(int(v.version) for v in versions)

    client.transition_model_version_stage(
        name=model_name,
        version=str(version),
        stage=stage,
    )
    log.info(
        "Transitioned '%s' v%d → %s",
        model_name,
        version,
        stage,
    )


def main() -> None:
    """Register and optionally promote a model."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    parser = argparse.ArgumentParser(description="Register and promote MLflow models")
    parser.add_argument(
        "--experiment",
        required=True,
        help="MLflow experiment name (e.g., 'strike_risk')",
    )
    parser.add_argument(
        "--model-name",
        required=True,
        help="Registered model name (e.g., 'strike_risk_xgboost')",
    )
    parser.add_argument(
        "--metric",
        default="cv_avg_precision_mean",
        help="Metric to select the best run (default: cv_avg_precision_mean)",
    )
    parser.add_argument(
        "--promote",
        choices=["Staging", "Production", "Archived"],
        default="Staging",
        help="Stage to promote to (default: Staging)",
    )
    parser.add_argument(
        "--filter",
        default="",
        help=(
            "MLflow search filter to narrow runs, e.g. "
            "\"tags.species = 'blue_whale'\" or "
            "\"tags.target = 'right_whale_present'\""
        ),
    )
    args = parser.parse_args()

    # Find best run
    best_run_id = find_best_run(
        args.experiment,
        metric=args.metric,
        filter_string=args.filter,
    )

    # Register
    version = register_model(best_run_id, args.model_name)

    # Transition
    transition_model(args.model_name, version=version, stage=args.promote)

    log.info(
        "Done: '%s' v%d is now in %s",
        args.model_name,
        version,
        args.promote,
    )


if __name__ == "__main__":
    main()
