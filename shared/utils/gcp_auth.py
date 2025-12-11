# For Google Cloud authentication

# Works automatically in Cloud Run
# To authenticate locally set GOOGLE_APPLICATION_CREDENTIALS to a service account key file.

# In order to give a service account access to invoke a cloud run service:
# gcloud run services add-iam-policy-binding <service_name> --member="serviceAccount:<service_account_email>" --role="roles/run.invoker" --region=europe-west1

from google.auth.transport.requests import Request
from google.oauth2 import id_token


def get_bearer_token(service_url: str) -> str:
    """Fetch a bearer token to make an authenticated call to the given service with the service account running the process."""
    return id_token.fetch_id_token(Request(), service_url)
