"""Log MLflow metrics from Modal to an MLflow server behind Google Cloud IAP.

No service account keys: Modal gives each container a short-lived OIDC token,
GCP Workload Identity Federation swaps it for a Google token, and the
container acts as a service account that IAP lets through.

Settings come from the Modal Secret "iap-test" (see README).
"""

import json
import os

import modal

# GCP only lets one function act as the service account, identified by
# workspace:environment:app:function. Renaming the app or function breaks access.
app = modal.App("iap-test")

image = (
    modal.Image.debian_slim()
    .uv_pip_install("mlflow-skinny==3.18.0", "google-auth[requests]")
    .add_local_dir("mlflow_iap_auth", "/pkg/mlflow_iap_auth", copy=True)
    .run_commands("pip install --no-deps /pkg/mlflow_iap_auth")  # registers the MLflow plugin
)


def use_gcp_workload_identity():
    """Point Google's default credentials at this container's Modal OIDC token.

    Writes the same config `gcloud iam workload-identity-pools create-cred-config`
    produces. MODAL_IDENTITY_TOKEN_FILE is refreshed by Modal, so long jobs keep working.
    """
    config = {
        "type": "external_account",
        "audience": f"//iam.googleapis.com/{os.environ['WIF_PROVIDER']}",
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {"file": os.environ["MODAL_IDENTITY_TOKEN_FILE"]},
        "service_account_impersonation_url": (
            "https://iamcredentials.googleapis.com/v1/projects/-/"
            f"serviceAccounts/{os.environ['SERVICE_ACCOUNT']}:generateAccessToken"
        ),
    }
    with open("/tmp/gcp_wif_config.json", "w") as f:
        json.dump(config, f)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcp_wif_config.json"


@app.function(image=image, secrets=[modal.Secret.from_name("iap-test")])
def train(epochs: int = 20):
    """Pretend to train a model and log metrics to MLflow."""
    import math
    import random

    import mlflow

    use_gcp_workload_identity()
    os.environ["MLFLOW_TRACKING_AUTH"] = "gcp-iap"  # use the mlflow_iap_auth plugin
    mlflow.set_tracking_uri(os.environ["MLFLOW_URL"])
    mlflow.set_experiment("modal-iap-demo")

    with mlflow.start_run():
        mlflow.log_params({"epochs": epochs, "lr": 3e-4, "batch_size": 64})
        for epoch in range(epochs):
            loss = 2.5 * math.exp(-epoch / 6) + random.uniform(0, 0.08)
            acc = 1 - 0.9 * math.exp(-epoch / 5) - random.uniform(0, 0.03)
            mlflow.log_metrics({"loss": loss, "accuracy": acc}, step=epoch)
            print(f"epoch {epoch:2d}  loss {loss:.3f}  acc {acc:.3f}")


@app.local_entrypoint()
def main(epochs: int = 20):
    train.remote(epochs)
