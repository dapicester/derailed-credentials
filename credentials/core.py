import base64
import os
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CredentialsError(Exception):
    """Base exception for credentials-related errors."""


class MasterKeyMissing(CredentialsError):
    """Raised when master key is not found."""


class MasterKeyAlreadyExists(CredentialsError):
    """Raised when generating a master key and a master key is found."""


class YAMLError(CredentialsError):
    """Raised when failed to parse YAML credentials."""


class Credentials:
    """
    Encrypted configuration management system inspired by Rails credentials.

    Stores configuration data in an encrypted YAML file and provides methods
    to read, write, and edit the configuration securely.
    """

    DEFAULT_CREDENTIALS_PATH = "config/credentials.yml.enc"
    DEFAULT_MASTER_KEY_PATH = "config/master.key"
    MASTER_KEY_ENV = "MASTER_KEY"
    SALT = b"credentials_salt"  # TODO: make this configurable

    def __init__(self,
                 credentials_path: str | None = None,
                 master_key_path: str | None = None,
                 master_key_env: str | None = None):
        """
        Initialize credentials manager.

        Args:
            credentials_path: Path to encrypted credentials file
            master_key_path: Path to master key file
            master_key_env: Environment variable name for master key
        """

        self.credentials_path = Path(credentials_path or self.DEFAULT_CREDENTIALS_PATH)
        self.master_key_path = Path(master_key_path or self.DEFAULT_MASTER_KEY_PATH)
        self.master_key_env = master_key_env or self.MASTER_KEY_ENV

        self._config_cache: Dict[str, Any] | None = None

        # Ensure config directory exists
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_master_key(self) -> str:
        """Get master key from environment variable or file."""

        # Try environment variable first
        key = os.environ.get(self.master_key_env)
        if key:
            return key.strip()

        # Try master key file
        if self.master_key_path.exists():
            return self.master_key_path.read_text().strip()

        raise MasterKeyMissing(
            f"Master key not found. Set {self.master_key_env} environment variable "
            f"or create {self.master_key_path}"
        )

    def _derive_key(self, master_key: str) -> bytes:
        """Derive encryption key from master key using PBKDF2."""

        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                         length=32,
                         salt=self.SALT,
                         iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key

    def _get_cipher(self) -> Fernet:
        """Get Fernet cipher instance."""

        master_key = self._get_master_key()
        derived_key = self._derive_key(master_key)
        return Fernet(derived_key)

    def _encrypt(self, data: str) -> str:
        """Encrypt data and return base64 encoded string."""

        cipher = self._get_cipher()
        encrypted = cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted data."""

        cipher = self._get_cipher()
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        return cipher.decrypt(encrypted_bytes).decode()

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

    def config(self, reload: bool = False) -> Dict[str, Any]:
        """
        Get the configuration dictionary.

        Args:
            reload: Force reading the credentials file.

        Returns:
            Dictionary containing all credentials
        """

        if self._config_cache is None or reload is True:
            try:
                content = self._read_encrypted_file()
                self._config_cache = yaml.safe_load(content) or {}
            except Exception as e:
                raise CredentialsError(f"Failed to load credentials: {e}")

        return self._config_cache

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a credential value by key.

        Args:
            key: Key to look up (supports dot notation like 'database.password')
            default: Default value if key not found

        Returns:
            The credential value or default
        """

        keys = key.split('.')

        value = self.config()
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a credential value.

        Args:
            key: Key to set (supports dot notation)
            value: Value to set
        """

        config = self.config()
        keys = key.split('.')

        current = config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
        self._save_config(config)

    def delete(self, key: str) -> bool:
        """
        Delete a credential.

        Args:
            key: Key to delete (supports dot notation)

        Returns:
            True if key was deleted, False if not found
        """

        config = self.config()
        keys = key.split('.')

        current = config

        # Navigate to parent
        for k in keys[:-1]:
            if not isinstance(current, dict) or k not in current:
                return False
            current = current[k]

        # Delete the key
        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]
            self._save_config(config)
            return True

        return False

    @classmethod
    def yaml_dump(cls, config: Dict[str, Any]) -> str:
        """Dump the configuration dictionary to a YAML string."""
        if not config:
            return ""
        return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to encrypted file."""

        yaml_content = self.yaml_dump(config)
        self._write_encrypted_file(yaml_content)
        self._config_cache = config

    def show(self) -> str:
        """Return decrypted credentials as YAML string."""
        return self.yaml_dump(self.config())

    @classmethod
    def open_external_editor(cls, file_name):
        import subprocess
        editor = os.environ.get('EDITOR', 'nano')
        subprocess.run([editor, file_name], check=True)

    def edit(self, editor: str | None = None, fake: bool = False) -> bool:
        """
        Edit credentials in an external editor.

        Args:
            editor: Editor command to use (defaults to $EDITOR or 'nano')

        Returns:
            True if the credentials have been changed, False otherwise
        """

        # Get current content
        current_content = self.show()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.yml') as tmp_file:
            tmp_file.write(current_content)
            tmp_file.flush()

            # Open editor, unless we are running tests
            if not fake:
                self.open_external_editor(tmp_file.name)

            # Read back the content
            with open(tmp_file.name, 'r') as f:
                new_content = f.read()

            # Parse and save if changed
            if new_content == current_content:
                return False

            try:
                new_config = yaml.safe_load(new_content) or {}
                self._save_config(new_config)
                return True
            except yaml.YAMLError as e:
                raise YAMLError(f"YAML parsing error: {e}") from e

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
            raise MasterKeyAlreadyExists(f"Master key file {self.master_key_path} already exists.")

        master_key = self.generate_master_key()
        self.master_key_path.write_text(master_key + '\n')
        self.master_key_path.chmod(0o600)  # Read/write for owner only

        return master_key
