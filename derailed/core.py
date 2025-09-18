import base64
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Generator, Generic, TypeVar

from addict import Dict as AddictDict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .serialization import yaml_dump, yaml_load


class CredentialsError(Exception):
    """Base exception for credentials-related errors."""


class MasterKeyMissing(CredentialsError):
    """Raised when master key is not found."""


class MasterKeyAlreadyExists(CredentialsError):
    """Raised when generating a master key and a master key is found."""


K = TypeVar("K")
V = TypeVar("V")


class DotDict(AddictDict, Generic[K, V]):
    """A dictionary whose values are gettable using attributes."""

    def __missing__(self, key):
        raise KeyError(key)


class Credentials:
    """
    Encrypted configuration management system inspired by Rails credentials.

    Stores configuration data in an encrypted YAML file and provides methods
    to read, write, and edit the configuration securely.
    """

    DEFAULT_CREDENTIALS_PATH = "config/credentials.yml.enc"
    DEFAULT_MASTER_KEY_PATH = "config/master.key"
    MASTER_KEY_ENV = "MASTER_KEY"
    SALT = b"credentials_salt"

    def __init__(
        self,
        credentials_path: str | None = None,
        master_key_path: str | None = None,
    ):
        """
        Initialize credentials manager.

        Args:
            credentials_path: Path to encrypted credentials file
            master_key_path: Path to master key file
        """

        self.credentials_path = Path(credentials_path or self.DEFAULT_CREDENTIALS_PATH)
        self.master_key_path = Path(master_key_path or self.DEFAULT_MASTER_KEY_PATH)

        self._config_cache: DotDict[str, Any] | None = None

        # Ensure config directory exists
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def master_key(self) -> str:
        """Get master key from environment variable or file."""

        # Try environment variable first
        key = os.environ.get(self.MASTER_KEY_ENV)
        if key:
            return key.strip()

        # Try master key file
        if self.master_key_path.exists():
            return self.master_key_path.read_text().strip()

        raise MasterKeyMissing(
            f"Master key not found. Set {self.MASTER_KEY_ENV} environment variable "
            f"or create {self.master_key_path}"
        )

    @property
    def _cipher(self) -> Fernet:
        """Get Fernet cipher instance."""

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=self.SALT, iterations=100000
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)

    def _encrypt(self, data: str) -> str:
        """Encrypt data and return base64 encoded string."""

        encrypted = self._cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted data."""

        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        return self._cipher.decrypt(encrypted_bytes).decode()

    def _read_encrypted_file(self) -> str:
        """Read and decrypt credentials file."""

        if not self.credentials_path.exists():
            return ""  # Return empty YAML object if file doesn't exist

        encrypted_content = self.credentials_path.read_text()
        if not encrypted_content.strip():
            return ""

        return self._decrypt(encrypted_content)

    def _write_encrypted_file(self, content: str) -> None:
        """Encrypt and write content to credentials file."""

        encrypted_content = self._encrypt(content)
        self.credentials_path.write_text(encrypted_content)

    @property
    def config(self) -> DotDict[str, Any]:
        """
        Get the configuration dictionary.

        Args:
            reload: Force reading the credentials file.

        Returns:
            Dictionary containing all credentials
        """

        if self._config_cache is None:
            try:
                content = self._read_encrypted_file()
                self._config_cache = DotDict(yaml_load(content) or {})
            except Exception as e:
                raise CredentialsError(f"Failed to load credentials: {e}")

        return self._config_cache

    @config.setter
    def config(self, config: Dict[str, Any]) -> None:
        """Save configuration to encrypted file."""

        yaml_content = yaml_dump(config)
        self._write_encrypted_file(yaml_content)
        self._config_cache = DotDict(config)

    def __getattr__(self, name):
        """Delegates getting attributes from the configuration dictionary."""
        return getattr(self.config, name)

    def show(self) -> str:
        """Return decrypted credentials as YAML string."""
        return yaml_dump(self.config.to_dict())

    @contextmanager
    def change(self) -> Generator[str, None, None]:
        """
        Edit credentials in an external editor.

        Returns:
            True if the credentials have been changed, False otherwise
        """

        # Get current content
        with self._writing(self.show()) as file_name:
            yield file_name

    @contextmanager
    def _writing(self, content) -> Generator[str, None, None]:
        with NamedTemporaryFile(mode="w+", suffix=".yml") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()

            yield tmp_file.name

            # Read back the content
            tmp_file.seek(0)
            new_content = tmp_file.read()

            # Parse and save if changed
            if new_content != content:
                new_config = yaml_load(new_content) or {}
                self.config = new_config

    @classmethod
    def generate_master_key(cls) -> str:
        """Generate a new master key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()

    def create_master_key_file(self, force: bool = False) -> str:
        """
        Create a new master key file.

        Args:
            force: Force overwriting an existing master key file

        Returns:
            The generated master key
        """
        if self.master_key_path.exists() and force is False:
            raise MasterKeyAlreadyExists(
                f"Master key file {self.master_key_path} already exists."
            )

        master_key = self.generate_master_key()
        self.master_key_path.write_text(master_key + "\n")
        self.master_key_path.chmod(0o600)  # Read/write for owner only

        return master_key
