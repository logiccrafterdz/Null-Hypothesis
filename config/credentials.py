"""
Credentials Management for Phoenix Protocol Trading System
Handles encrypted storage and retrieval of broker credentials.
"""

import os
from typing import Dict, Optional
from pathlib import Path
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class CredentialsManager:
    """Securely manage trading platform credentials."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize credentials manager.
        
        Args:
            encryption_key: Optional encryption key. If not provided, uses env var.
        """
        self.encryption_key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable must be set")
        
        self.cipher_suite = Fernet(self._get_fernet_key())
        self.credentials_file = Path(__file__).parent.parent / ".env.encrypted"
    
    def _get_fernet_key(self) -> bytes:
        """Derive Fernet key from encryption key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'phoenix_protocol_salt',  # In production, use random salt
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
        return key
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt string data."""
        encrypted = self.cipher_suite.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = self.cipher_suite.decrypt(encrypted_bytes)
        return decrypted.decode()
    
    def save_credentials(self, credentials: Dict[str, str]) -> None:
        """
        Save encrypted credentials to file.
        
        Args:
            credentials: Dictionary of credential key-value pairs
        """
        encrypted_dict = {
            key: self.encrypt_data(value)
            for key, value in credentials.items()
        }
        
        with open(self.credentials_file, 'w') as f:
            json.dump(encrypted_dict, f, indent=2)
    
    def load_credentials(self) -> Dict[str, str]:
        """
        Load and decrypt credentials from file.
        
        Returns:
            Dictionary of decrypted credentials
        """
        if not self.credentials_file.exists():
            return {}
        
        with open(self.credentials_file, 'r') as f:
            encrypted_dict = json.load(f)
        
        return {
            key: self.decrypt_data(value)
            for key, value in encrypted_dict.items()
        }
    
    def get_credential(self, key: str) -> Optional[str]:
        """
        Get a specific credential by key.
        
        Args:
            key: Credential key
            
        Returns:
            Credential value or None if not found
        """
        credentials = self.load_credentials()
        return credentials.get(key)


# Initialize credentials manager
try:
    creds_manager = CredentialsManager()
except ValueError:
    # If encryption key not set, create a dummy manager for development
    creds_manager = None


def get_mt5_credentials() -> Dict[str, str]:
    """Get MetaTrader 5 credentials."""
    if creds_manager:
        return {
            "login": creds_manager.get_credential("MT5_LOGIN") or os.getenv("MT5_LOGIN", ""),
            "password": creds_manager.get_credential("MT5_PASSWORD") or os.getenv("MT5_PASSWORD", ""),
            "server": creds_manager.get_credential("MT5_SERVER") or os.getenv("MT5_SERVER", ""),
        }
    return {
        "login": os.getenv("MT5_LOGIN", ""),
        "password": os.getenv("MT5_PASSWORD", ""),
        "server": os.getenv("MT5_SERVER", ""),
    }


def get_telegram_credentials() -> Dict[str, str]:
    """Get Telegram bot credentials."""
    if creds_manager:
        return {
            "bot_token": creds_manager.get_credential("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": creds_manager.get_credential("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", ""),
        }
    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }


def get_database_credentials() -> Dict[str, str]:
    """Get database credentials."""
    if creds_manager:
        return {
            "host": creds_manager.get_credential("DB_HOST") or os.getenv("DB_HOST", "localhost"),
            "port": creds_manager.get_credential("DB_PORT") or os.getenv("DB_PORT", "5432"),
            "database": creds_manager.get_credential("DB_NAME") or os.getenv("DB_NAME", "phoenix_protocol"),
            "user": creds_manager.get_credential("DB_USER") or os.getenv("DB_USER", "postgres"),
            "password": creds_manager.get_credential("DB_PASSWORD") or os.getenv("DB_PASSWORD", ""),
        }
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "phoenix_protocol"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
