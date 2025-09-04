from typing import Optional
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from config import config


def impersonated_creds(subject_email: str) -> Credentials:
    """Create impersonated credentials for a specific user."""
    creds = service_account.Credentials.from_service_account_info(
        config.google_credentials_json, 
        scopes=config.scopes, 
        subject=subject_email
    )
    return creds.with_scopes(config.scopes)


def admin_creds() -> Credentials:
    """Create admin credentials for Directory API access."""
    if config.has_admin_subject:
        return impersonated_creds(config.admin_subject)
    else:
        return service_account.Credentials.from_service_account_info(
            config.google_credentials_json, 
            scopes=config.scopes
        )


def calendar_service(subject_email: str) -> Resource:
    """Build Calendar API service for a specific user."""
    return build("calendar", "v3", credentials=impersonated_creds(subject_email), cache_discovery=False)


def directory_service() -> Resource:
    """Build Directory API service with admin credentials."""
    return build("admin", "directory_v1", credentials=admin_creds(), cache_discovery=False)