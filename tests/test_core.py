import base64
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml

from derailed.core import (
    Credentials,
    CredentialsError,
    MasterKeyAlreadyExists,
    MasterKeyMissing,
)


class TestCredentials:
    def test_generate_master_key(self):
        key1 = Credentials.generate_master_key()
        key2 = Credentials.generate_master_key()

        # Keys should be different
        assert key1 != key2

        # Keys should be base64 URL-safe encoded
        decoded = base64.urlsafe_b64decode(key1.encode())
        assert len(decoded) == 32  # 32 bytes = 256 bits

    def test_master_key_from_env(self, credentials):
        test_key = "test-master-key-123"

        with patch.dict(os.environ, {"TEST_MASTER_KEY": test_key}):
            assert credentials._get_master_key() == test_key

    def test_master_key_from_file(self, credentials, temp_dir):
        test_key = "test-master-key-from-file"

        key_path = temp_dir / "master.key"
        key_path.write_text(test_key + "\n")

        # Strips the newline character from the file
        assert credentials._get_master_key() == test_key

    def test_master_key_env_priority(self, credentials, temp_dir):
        env_key = "env-key"
        file_key = "file-key"

        key_path = temp_dir / "master.key"
        key_path.write_text(file_key)

        with patch.dict(os.environ, {"TEST_MASTER_KEY": env_key}):
            assert credentials._get_master_key() == env_key

    def test_master_key_missing(self, credentials):
        with pytest.raises(MasterKeyMissing):
            credentials._get_master_key()

    def test_encrypt_decrypt_roundtrip(self, credentials_with_key):
        original_data = "This is secret data! 🔐"

        encrypted = credentials_with_key._encrypt(original_data)
        decrypted = credentials_with_key._decrypt(encrypted)

        assert decrypted == original_data
        assert encrypted != original_data

    def test_config_empty_file(self, credentials_with_key):
        config = credentials_with_key.config()
        assert config == {}

        yaml_output = credentials_with_key.show()
        assert yaml_output == ""

    @pytest.fixture
    def credentials_with_data(self, credentials_with_key, sample_data):
        credentials_with_key._save_config(sample_data)
        return credentials_with_key

    def test_config_with_data(self, credentials_with_data, sample_data):
        config = credentials_with_data.config(reload=True)
        assert config == sample_data

    def test_get_simple_key(self, credentials_with_data):
        assert credentials_with_data.api_key == "secret123"
        assert credentials_with_data.debug is True
        with pytest.raises(KeyError):
            credentials_with_data.nonexistent

    def test_get_nested_key(self, credentials_with_data):
        assert credentials_with_data.database.password == "dbpass"
        assert credentials_with_data.database.nested.deep == "value"
        with pytest.raises(KeyError):
            credentials_with_data.database.nonexistent

    def test_show(self, credentials_with_data, sample_data):
        yaml_output = credentials_with_data.show()
        parsed = yaml.safe_load(yaml_output)
        assert parsed == sample_data

    def test_create_master_key_file(self, credentials, temp_dir):
        key_path = temp_dir / "master.key"
        assert not key_path.exists()

        with patch("builtins.input", return_value="y"):
            generated_key = credentials.create_master_key_file()

        assert key_path.exists()
        assert key_path.read_text().strip() == generated_key

        # Should be readable/writable by owner only
        file_stat = key_path.stat()
        assert file_stat.st_mode & 0o777 == 0o600

    def test_create_master_key_file_exists_abort(self, credentials, temp_dir):
        key_path = temp_dir / "master.key"
        key_path.write_text("existing-key")

        with pytest.raises(MasterKeyAlreadyExists):
            credentials.create_master_key_file()

    @patch("tempfile.NamedTemporaryFile")
    def test_edit_success(self, mock_tempfile, fp, credentials_with_key, temp_dir):
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.yml"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        # Mock file operations
        original_content = "api_key: old_value\n"
        new_content = "api_key: new_value\ndatabase:\n  password: secret\n"

        with patch.dict(os.environ, {}, clear=True):
            # No EDITOR set, defaults to nano
            fp.register(["nano", mock_file.name])

            with patch("builtins.open", mock_open(read_data=new_content)):
                with patch.object(
                    credentials_with_key, "show", return_value=original_content
                ):
                    changed = credentials_with_key.edit(editor="nano")
                    assert changed is True

    @patch("tempfile.NamedTemporaryFile")
    def test_edit_no_changes(self, mock_tempfile, fp, credentials_with_key):
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.yml"
        mock_tempfile.return_value.__enter__.return_value = mock_file

        content = "api_key: value\n"

        with patch.dict(os.environ, {"EDITOR": "/usr/bin/nvim"}):
            # Use EDITOR
            fp.register(["/usr/bin/nvim", mock_file.name])

            with patch("builtins.open", mock_open(read_data=content)):
                with patch.object(credentials_with_key, "show", return_value=content):
                    changed = credentials_with_key.edit()
                    assert changed is False

    def test_invalid_encryption_key(self, credentials, temp_dir):
        # Create credentials with one key
        key1 = Credentials.generate_master_key()
        key_path = temp_dir / "master.key"
        key_path.write_text(key1)

        # Save some data
        credentials._save_config({"test": "data"})

        # Change the key
        key2 = Credentials.generate_master_key()
        key_path.write_text(key2)

        # Should raise error when trying to decrypt
        with pytest.raises(CredentialsError):
            credentials.config(reload=True)

    def test_corrupted_encrypted_file(self, temp_dir):
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"

        # Create valid master key
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)

        # Write corrupted encrypted data
        creds_path.write_text("corrupted-not-base64-data")

        creds = Credentials(
            credentials_path=str(creds_path), master_key_path=str(key_path)
        )

        with pytest.raises(CredentialsError):
            creds.config()

    def test_invalid_yaml_in_decrypted_content(self, temp_dir):
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"

        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)

        creds = Credentials(
            credentials_path=str(creds_path), master_key_path=str(key_path)
        )

        # Encrypt invalid YAML
        invalid_yaml = "invalid: yaml: content: [unclosed"
        encrypted = creds._encrypt(invalid_yaml)
        creds_path.write_text(encrypted)

        with pytest.raises(CredentialsError):
            creds.config()

    def test_permission_denied_master_key(self, temp_dir):
        key_path = temp_dir / "master.key"
        key_path.write_text("test-key")
        key_path.chmod(0o000)  # No permissions

        creds = Credentials(master_key_path=str(key_path))

        try:
            with pytest.raises((PermissionError, OSError)):
                creds._get_master_key()
        finally:
            # Restore permissions for cleanup
            key_path.chmod(0o600)

    def test_empty_credentials_file(self, temp_dir):
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"

        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)

        # Create empty file
        creds_path.touch()

        creds = Credentials(
            credentials_path=str(creds_path), master_key_path=str(key_path)
        )

        config = creds.config()
        assert config == {}

    def test_dynamic_attributes(self, credentials_with_data):
        credentials = credentials_with_data

        assert credentials.api_key == "secret123"
        assert credentials.database.password == "dbpass"
        assert credentials.database.nested.deep == "value"

        with pytest.raises(KeyError):
            credentials.nonexistent

        with pytest.raises(KeyError):
            credentials.database.nonexistent
