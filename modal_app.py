"""Log MLflow metrics from Modal to an MLflow server behind Google Cloud IAP.

No service account keys: Modal gives each container a short-lived OIDC token,
GCP Workload Identity Federation swaps it for a Google token, and the
container acts as a service account that IAP lets through.

Needs gcp_credentials.json and the Modal Secret "iap-test" (see README).
"""

import modal

# GCP only lets one function act as the service account, identified by
# workspace:environment:app:function. Renaming the app or function breaks access.
app = modal.App("iap-test")

image = (
    modal.Image.debian_slim()
    .uv_pip_install("mlflow-skinny==3.18.0", "google-auth[requests]")
    .add_local_dir("mlflow_iap_auth", "/pkg/mlflow_iap_auth", copy=True)
    .run_commands("pip install --no-deps /pkg/mlflow_iap_auth")  # registers the MLflow plugin
    .env(
        {
            "GOOGLE_APPLICATION_CREDENTIALS": "/root/gcp_credentials.json",  # Google clients find this
            "MLFLOW_TRACKING_AUTH": "gcp-iap",  # use the mlflow_iap_auth plugin
        }
    )
    .add_local_file("gcp_credentials.json", "/root/gcp_credentials.json")
)


@app.function(image=image, secrets=[modal.Secret.from_name("iap-test")])
def train(epochs: int = 20):
    """Pretend to train a model and log metrics to MLflow (at MLFLOW_TRACKING_URI)."""
    import math
    import random

    import mlflow

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
