from typing import List
from auth import directory_service
from config import config


def list_active_users() -> List[str]:
    """
    Get list of active users from Google Workspace Directory API.
    Returns list of email addresses.
    """
    svc = directory_service().users()
    users = []
    token = None
    
    while True:
        resp = svc.list(
            customer="my_customer",
            maxResults=500,
            orderBy="email",
            query="isSuspended=false",
            pageToken=token,
            fields="users(primaryEmail),nextPageToken"
        ).execute()
        
        for user in resp.get("users", []):
            if "primaryEmail" in user:
                users.append(user["primaryEmail"])
        
        token = resp.get("nextPageToken")
        if not token or len(users) >= config.max_users:
            break
    
    return users[:config.max_users]