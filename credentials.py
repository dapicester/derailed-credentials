#!/usr/bin/env python3

import os
import sys
import yaml
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CredentialsError(Exception):
    """Base exception for credentials-related errors."""
    pass


class MasterKeyMissing(CredentialsError):
    """Raised when master key is not found."""
    pass


class Credentials:
    """
    Encrypted configuration management system inspired by Rails credentials.
    
    Stores configuration data in an encrypted YAML file and provides methods
    to read, write, and edit the configuration securely.
    """
    
    DEFAULT_CREDENTIALS_PATH = "config/credentials.yml.enc"
    DEFAULT_MASTER_KEY_PATH = "config/master.key"
    MASTER_KEY_ENV = "MASTER_KEY"
    SALT = b"credentials_salt"  # In production, you might want this configurable
    
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
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.SALT,
            iterations=100000,
        )
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
            return "{}"  # Return empty YAML object if file doesn't exist
        
        encrypted_content = self.credentials_path.read_text()
        if not encrypted_content.strip():
            return "{}"
        
        return self._decrypt(encrypted_content)
    
    def _write_encrypted_file(self, content: str) -> None:
        """Encrypt and write content to credentials file."""
        encrypted_content = self._encrypt(content)
        self.credentials_path.write_text(encrypted_content)
    
    def config(self) -> Dict[str, Any]:
        """
        Get the configuration dictionary.
        
        Returns:
            Dictionary containing all credentials
        """
        if self._config_cache is None:
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
        config = self.config()
        
        # Handle dot notation
        keys = key.split('.')
        value = config
        
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
        
        # Handle dot notation
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
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to encrypted file."""
        yaml_content = yaml.dump(config, default_flow_style=False, allow_unicode=True)
        self._write_encrypted_file(yaml_content)
        self._config_cache = config
    
    def show(self) -> str:
        """Return decrypted credentials as YAML string."""
        config = self.config()
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)
    
    def edit(self, editor: str | None = None) -> None:
        """
        Edit credentials in an external editor.
        
        Args:
            editor: Editor command to use (defaults to $EDITOR or 'nano')
        """
        editor = editor or os.environ.get('EDITOR', 'nano')
        
        # Get current content
        current_content = self.show()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.yml', delete=False) as tmp_file:
            tmp_file.write(current_content)
            tmp_file.flush()
            
            try:
                # Open editor
                subprocess.run([editor, tmp_file.name], check=True)
                
                # Read back the content
                with open(tmp_file.name, 'r') as f:
                    new_content = f.read()
                
                # Parse and save if changed
                if new_content != current_content:
                    try:
                        new_config = yaml.safe_load(new_content) or {}
                        self._save_config(new_config)
                        print("Credentials updated successfully.")
                    except yaml.YAMLError as e:
                        print(f"YAML parsing error: {e}")
                        print("Credentials not updated.")
                else:
                    print("No changes made.")
                    
            finally:
                # Clean up temp file
                os.unlink(tmp_file.name)
    
    @classmethod
    def generate_master_key(cls) -> str:
        """Generate a new master key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def create_master_key_file(self) -> str:
        """
        Create a new master key file.
        
        Returns:
            The generated master key
        """
        if self.master_key_path.exists():
            response = input(f"Master key file {self.master_key_path} already exists. Overwrite? [y/N]: ")
            if response.lower() != 'y':
                print("Aborted.")
                return self.master_key_path.read_text().strip()
        
        master_key = self.generate_master_key()
        self.master_key_path.write_text(master_key + '\n')
        self.master_key_path.chmod(0o600)  # Read/write for owner only
        
        print(f"Master key created at {self.master_key_path}")
        print(f"Keep this key secure! You can also set it as {self.MASTER_KEY_ENV} environment variable.")
        
        return master_key


def main():
    """Command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Manage encrypted credentials')
    parser.add_argument('--credentials-path', help='Path to credentials file')
    parser.add_argument('--master-key-path', help='Path to master key file')
    parser.add_argument('--master-key-env', help='Environment variable for master key')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit credentials')
    edit_parser.add_argument('--editor', help='Editor to use')
    
    # Show command
    subparsers.add_parser('show', help='Show decrypted credentials')
    
    # Generate key command
    subparsers.add_parser('generate-key', help='Generate master key')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get a credential value')
    get_parser.add_argument('key', help='Key to retrieve')
    get_parser.add_argument('--default', help='Default value if key not found')
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set a credential value')
    set_parser.add_argument('key', help='Key to set')
    set_parser.add_argument('value', help='Value to set')
    
    # Delete command
    del_parser = subparsers.add_parser('delete', help='Delete a credential')
    del_parser.add_argument('key', help='Key to delete')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        credentials = Credentials(
            credentials_path=args.credentials_path,
            master_key_path=args.master_key_path,
            master_key_env=args.master_key_env
        )
        
        if args.command == 'edit':
            credentials.edit(editor=getattr(args, 'editor', None))
        elif args.command == 'show':
            print(credentials.show())
        elif args.command == 'generate-key':
            credentials.create_master_key_file()
        elif args.command == 'get':
            value = credentials.get(args.key, args.default)
            if value is not None:
                print(value)
            else:
                print(f"Key '{args.key}' not found")
                sys.exit(1)
        elif args.command == 'set':
            credentials.set(args.key, args.value)
            print(f"Set {args.key}")
        elif args.command == 'delete':
            if credentials.delete(args.key):
                print(f"Deleted {args.key}")
            else:
                print(f"Key '{args.key}' not found")
                sys.exit(1)
                
    except CredentialsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)


if __name__ == '__main__':
    main()
