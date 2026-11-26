"""MLflow request-auth plugin for MLflow servers behind GCP Identity-Aware Proxy.

Enable it with MLFLOW_TRACKING_AUTH=gcp-iap. Each request to the tracking
server gets `Authorization: Bearer <Google access token>`, refreshed before
it expires.

Credentials come from Google's Application Default Credentials, so this works
anywhere those are set up: on Modal via a Workload Identity Federation config
file in GOOGLE_APPLICATION_CREDENTIALS, or on a laptop via
`gcloud auth application-default login --impersonate-service-account=...`.
"""

import threading

import google.auth
import requests
from google.auth.transport.requests import Request
from mlflow.tracking.request_auth.abstract_request_auth_provider import RequestAuthProvider

# IAP accepts a service account access token that carries these scopes.
IAP_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


class _BearerAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


class GcpIapAuthProvider(RequestAuthProvider):
    def __init__(self):
        self._credentials = None
        self._lock = threading.Lock()

    def get_name(self):
        return "gcp-iap"

    def get_auth(self):
        # MLflow calls this for every request; reuse the token until it nears expiry.
        with self._lock:
            if self._credentials is None:
                self._credentials, _ = google.auth.default(scopes=IAP_SCOPES)
            if not self._credentials.valid:
                self._credentials.refresh(Request())
            return _BearerAuth(self._credentials.token)
