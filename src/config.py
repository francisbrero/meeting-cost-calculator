import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)


class Config:
    def __init__(self):
        # Core configuration
        self.domain = os.environ.get("DOMAIN", "hginsights.com")
        self.default_rate = float(os.environ.get("DEFAULT_RATE", "125"))
        self.cost_tag = os.environ.get("COST_TAG", "[[MEETING_COST]]")
        self.internal_only = os.environ.get("INTERNAL_ONLY", "true").lower() == "true"
        self.max_users = int(os.environ.get("MAX_USERS", "10000"))
        self.window_days = int(os.environ.get("WINDOW_DAYS", "35"))
        self.admin_subject = os.environ.get("ADMIN_SUBJECT")
        
        # Load Google credentials from file or environment variable (fallback)
        self.google_credentials_json = self._load_google_credentials()
        
        self.scopes = [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/admin.directory.user.readonly"
        ]
    
    def _load_google_credentials(self) -> dict:
        """Load Google credentials from file path or environment variable."""
        # Try to load from file first (preferred method)
        creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH")
        if creds_path:
            creds_file = Path(creds_path)
            if not creds_file.is_absolute():
                # Resolve relative path from project root
                creds_file = project_root / creds_path
            
            if creds_file.exists():
                with open(creds_file, 'r') as f:
                    return json.load(f)
            else:
                raise FileNotFoundError(f"Google credentials file not found: {creds_file}")
        
        # Fallback to environment variable (for backwards compatibility)
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            return json.loads(creds_json)
        
        raise ValueError(
            "Google credentials not found. Set either:\n"
            "  - GOOGLE_CREDENTIALS_PATH to point to your credentials.json file, or\n"
            "  - GOOGLE_CREDENTIALS_JSON with the JSON content directly"
        )
    
    @property
    def has_admin_subject(self) -> bool:
        return self.admin_subject is not None and self.admin_subject.strip() != ""


config = Config()