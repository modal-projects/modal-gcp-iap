# Minimal MLflow tracking server for Cloud Run (demo only).
# Storage is the container's local disk, so runs are lost when the instance
# shuts down. For real use, point --backend-store-uri at Cloud SQL (and add
# --artifacts-destination gs://... if you log artifacts).
FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow==3.18.0

WORKDIR /tmp

# MLFLOW_HOST is set at deploy time to the Cloud Run hostname. MLflow rejects
# requests whose Host header isn't in --allowed-hosts.
CMD exec mlflow server \
      --host 0.0.0.0 --port "${PORT}" --workers 1 \
      --backend-store-uri sqlite:////tmp/mlflow.db \
      --allowed-hosts "${MLFLOW_HOST}" \
      --cors-allowed-origins "https://${MLFLOW_HOST}"
