"""Application settings loaded from the .env file.

All environment variables are accessed through this module;
nothing else in the codebase reads os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

OCI_REGION: str = os.getenv("OCI_REGION", "")
ADB_CONNECTION_STRING: str = os.getenv("ADB_CONNECTION_STRING", "")
ADB_USERNAME: str = os.getenv("ADB_USERNAME", "")
ADB_PASSWORD: str = os.getenv("ADB_PASSWORD", "")
WALLET_DIR: str = os.getenv("WALLET_DIR", "")
WALLET_PASSWORD: str = os.getenv("WALLET_PASSWORD", "")
OCI_GENAI_MODEL: str = os.getenv("OCI_GENAI_MODEL", "")
OCI_EMBEDDING_MODEL: str = os.getenv("OCI_EMBEDDING_MODEL", "")
SELECT_AI_PROFILE: str = os.getenv("SELECT_AI_PROFILE", "")
OCI_COMPARTMENT_OCID: str = os.getenv("OCI_COMPARTMENT_OCID", "")
OBJECT_STORAGE_BUCKET: str = os.getenv("OBJECT_STORAGE_BUCKET", "")
