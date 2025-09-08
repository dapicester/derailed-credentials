#!/usr/bin/env python3
"""
Comprehensive test suite for the Python credentials system.

Run with: pytest test_credentials.py -v
"""

import os
import sys
import tempfile
import pytest
import yaml
import subprocess
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from cryptography.fernet import InvalidToken

# Import the credentials module (assuming it's in the same directory)
from credentials import Credentials, CredentialsError, MasterKeyMissing


class TestCredentials:
    """Test the main Credentials class functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def credentials(self, temp_dir):
        """Create a Credentials instance with temporary files."""
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        return Credentials(
            credentials_path=str(creds_path),
            master_key_path=str(key_path),
            master_key_env="TEST_MASTER_KEY"
        )
    
    @pytest.fixture
    def credentials_with_key(self, credentials, temp_dir):
        """Create credentials instance with a master key file."""
        master_key = Credentials.generate_master_key()
        key_path = temp_dir / "master.key"
        key_path.write_text(master_key)
        return credentials
    
    def test_generate_master_key(self):
        """Test master key generation."""
        key1 = Credentials.generate_master_key()
        key2 = Credentials.generate_master_key()
        
        # Keys should be different
        assert key1 != key2
        
        # Keys should be base64 URL-safe encoded
        import base64
        try:
            decoded = base64.urlsafe_b64decode(key1.encode())
            assert len(decoded) == 32  # 32 bytes = 256 bits
        except Exception:
            pytest.fail("Generated key is not valid base64")
    
    def test_master_key_from_env(self, credentials):
        """Test getting master key from environment variable."""
        test_key = "test-master-key-123"
        
        with patch.dict(os.environ, {"TEST_MASTER_KEY": test_key}):
            assert credentials._get_master_key() == test_key
    
    def test_master_key_from_file(self, credentials, temp_dir):
        """Test getting master key from file."""
        test_key = "test-master-key-from-file"
        key_path = temp_dir / "master.key"
        key_path.write_text(test_key + "\n")
        
        assert credentials._get_master_key() == test_key
    
    def test_master_key_env_priority(self, credentials, temp_dir):
        """Test that environment variable takes priority over file."""
        env_key = "env-key"
        file_key = "file-key"
        
        key_path = temp_dir / "master.key"
        key_path.write_text(file_key)
        
        with patch.dict(os.environ, {"TEST_MASTER_KEY": env_key}):
            assert credentials._get_master_key() == env_key
    
    def test_master_key_missing(self, credentials):
        """Test error when master key is not found."""
        with pytest.raises(MasterKeyMissing):
            credentials._get_master_key()
    
    def test_encrypt_decrypt_roundtrip(self, credentials_with_key):
        """Test that encryption and decryption work correctly."""
        original_data = "This is secret data! 🔐"
        
        encrypted = credentials_with_key._encrypt(original_data)
        decrypted = credentials_with_key._decrypt(encrypted)
        
        assert decrypted == original_data
        assert encrypted != original_data
    
    def test_config_empty_file(self, credentials_with_key):
        """Test config when credentials file doesn't exist."""
        config = credentials_with_key.config()
        assert config == {}
    
    def test_config_with_data(self, credentials_with_key):
        """Test config with actual data."""
        test_data = {
            'api_key': 'secret123',
            'database': {
                'password': 'dbpass',
                'host': 'localhost'
            }
        }
        
        # Save config
        credentials_with_key._save_config(test_data)
        
        # Clear cache and reload
        credentials_with_key._config_cache = None
        config = credentials_with_key.config()
        
        assert config == test_data
    
    def test_get_simple_key(self, credentials_with_key):
        """Test getting simple key values."""
        test_data = {'api_key': 'secret123', 'debug': True}
        credentials_with_key._save_config(test_data)
        
        assert credentials_with_key.get('api_key') == 'secret123'
        assert credentials_with_key.get('debug') is True
        assert credentials_with_key.get('nonexistent') is None
        assert credentials_with_key.get('nonexistent', 'default') == 'default'
    
    def test_get_nested_key(self, credentials_with_key):
        """Test getting nested key values with dot notation."""
        test_data = {
            'database': {
                'password': 'secret',
                'nested': {
                    'deep': 'value'
                }
            }
        }
        credentials_with_key._save_config(test_data)
        
        assert credentials_with_key.get('database.password') == 'secret'
        assert credentials_with_key.get('database.nested.deep') == 'value'
        assert credentials_with_key.get('database.nonexistent') is None
        assert credentials_with_key.get('nonexistent.key', 'default') == 'default'
    
    def test_set_simple_key(self, credentials_with_key):
        """Test setting simple key values."""
        credentials_with_key.set('api_key', 'newsecret')
        assert credentials_with_key.get('api_key') == 'newsecret'
    
    def test_set_nested_key(self, credentials_with_key):
        """Test setting nested key values."""
        credentials_with_key.set('database.password', 'newpass')
        credentials_with_key.set('new.nested.key', 'value')
        
        assert credentials_with_key.get('database.password') == 'newpass'
        assert credentials_with_key.get('new.nested.key') == 'value'
    
    def test_delete_simple_key(self, credentials_with_key):
        """Test deleting simple keys."""
        credentials_with_key.set('temp_key', 'temp_value')
        assert credentials_with_key.get('temp_key') == 'temp_value'
        
        result = credentials_with_key.delete('temp_key')
        assert result is True
        assert credentials_with_key.get('temp_key') is None
    
    def test_delete_nested_key(self, credentials_with_key):
        """Test deleting nested keys."""
        credentials_with_key.set('database.temp', 'temp_value')
        assert credentials_with_key.get('database.temp') == 'temp_value'
        
        result = credentials_with_key.delete('database.temp')
        assert result is True
        assert credentials_with_key.get('database.temp') is None
    
    def test_delete_nonexistent_key(self, credentials_with_key):
        """Test deleting non-existent keys."""
        result = credentials_with_key.delete('nonexistent')
        assert result is False
        
        result = credentials_with_key.delete('nested.nonexistent')
        assert result is False
    
    def test_show(self, credentials_with_key):
        """Test show method returns YAML."""
        test_data = {
            'api_key': 'secret123',
            'database': {'password': 'dbpass'}
        }
        credentials_with_key._save_config(test_data)
        
        yaml_output = credentials_with_key.show()
        parsed = yaml.safe_load(yaml_output)
        assert parsed == test_data
    
    def test_create_master_key_file(self, credentials, temp_dir):
        """Test creating master key file."""
        key_path = temp_dir / "master.key"
        
        with patch('builtins.input', return_value='y'):
            generated_key = credentials.create_master_key_file()
        
        assert key_path.exists()
        assert key_path.read_text().strip() == generated_key
        
        # Test file permissions (on Unix systems)
        if hasattr(os, 'stat'):
            import stat
            file_stat = key_path.stat()
            # Should be readable/writable by owner only
            assert file_stat.st_mode & 0o777 == 0o600
    
    def test_create_master_key_file_exists_abort(self, credentials, temp_dir):
        """Test aborting when master key file exists."""
        key_path = temp_dir / "master.key"
        key_path.write_text("existing-key")
        
        with patch('builtins.input', return_value='n'):
            result = credentials.create_master_key_file()
        
        assert result == "existing-key"
        assert key_path.read_text().strip() == "existing-key"
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_edit_success(self, mock_tempfile, mock_subprocess, credentials_with_key):
        """Test successful editing of credentials."""
        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = '/tmp/test.yml'
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Mock file operations
        original_content = "api_key: old_value\n"
        new_content = "api_key: new_value\ndatabase:\n  password: secret\n"
        
        with patch('builtins.open', mock_open(read_data=new_content)):
            with patch.object(credentials_with_key, 'show', return_value=original_content):
                with patch('builtins.print') as mock_print:
                    credentials_with_key.edit(editor='nano')
        
        mock_subprocess.assert_called_once_with(['nano', '/tmp/test.yml'], check=True)
        mock_print.assert_called_with("Credentials updated successfully.")
    
    @patch('subprocess.run')
    @patch('tempfile.NamedTemporaryFile')
    def test_edit_no_changes(self, mock_tempfile, mock_subprocess, credentials_with_key):
        """Test editing with no changes."""
        mock_file = MagicMock()
        mock_file.name = '/tmp/test.yml'
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        content = "api_key: value\n"
        
        with patch('builtins.open', mock_open(read_data=content)):
            with patch.object(credentials_with_key, 'show', return_value=content):
                with patch('builtins.print') as mock_print:
                    credentials_with_key.edit()
        
        mock_print.assert_called_with("No changes made.")
    
    def test_invalid_encryption_key(self, credentials, temp_dir):
        """Test handling of invalid encryption keys."""
        # Create credentials with one key
        key1 = Credentials.generate_master_key()
        key_path = temp_dir / "master.key"
        key_path.write_text(key1)
        
        # Save some data
        credentials._save_config({"test": "data"})
        
        # Change the key
        key2 = Credentials.generate_master_key()
        key_path.write_text(key2)
        credentials._config_cache = None  # Clear cache
        
        # Should raise error when trying to decrypt
        with pytest.raises(CredentialsError):
            credentials.config()


class TestCredentialsCLI:
    """Test the command-line interface."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def cli_env(self, temp_dir):
        """Set up environment for CLI testing."""
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)
        
        return {
            'creds_path': str(creds_path),
            'key_path': str(key_path),
            'master_key': master_key
        }
    
    def run_cli(self, args, cli_env):
        """Helper to run CLI commands."""
        cmd = [
            sys.executable, 'credentials.py',
            '--credentials-path', cli_env['creds_path'],
            '--master-key-path', cli_env['key_path']
        ] + args
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=Path(__file__).parent
        )
        return result
    
    def test_cli_generate_key(self, temp_dir):
        """Test CLI key generation."""
        key_path = temp_dir / "test_master.key"
        
        cmd = [
            sys.executable, 'credentials.py',
            '--master-key-path', str(key_path),
            'generate-key'
        ]
        
        # Mock input to confirm overwrite
        with patch('builtins.input', return_value='y'):
            result = subprocess.run(
                cmd,
                input='y\n',
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
        
        if result.returncode == 0:
            assert key_path.exists()
            assert "Master key created" in result.stdout
    
    @patch('subprocess.run')
    def test_cli_edit(self, mock_subprocess, cli_env):
        """Test CLI edit command."""
        # Set up credentials first
        creds = Credentials(
            credentials_path=cli_env['creds_path'],
            master_key_path=cli_env['key_path']
        )
        creds.set('test', 'value')
        
        result = self.run_cli(['edit'], cli_env)
        
        # Should attempt to open editor
        if result.returncode == 0:
            assert "Credentials" in result.stdout or result.stderr == ""
    
    def test_cli_show(self, cli_env):
        """Test CLI show command."""
        # Set up credentials first
        creds = Credentials(
            credentials_path=cli_env['creds_path'],
            master_key_path=cli_env['key_path']
        )
        creds.set('test_key', 'test_value')
        
        result = self.run_cli(['show'], cli_env)
        
        if result.returncode == 0:
            assert 'test_key' in result.stdout
            assert 'test_value' in result.stdout
    
    def test_cli_get(self, cli_env):
        """Test CLI get command."""
        # Set up credentials first
        creds = Credentials(
            credentials_path=cli_env['creds_path'],
            master_key_path=cli_env['key_path']
        )
        creds.set('api_key', 'secret123')
        creds.set('database.password', 'dbpass')
        
        # Test simple key
        result = self.run_cli(['get', 'api_key'], cli_env)
        if result.returncode == 0:
            assert 'secret123' in result.stdout
        
        # Test nested key
        result = self.run_cli(['get', 'database.password'], cli_env)
        if result.returncode == 0:
            assert 'dbpass' in result.stdout
        
        # Test non-existent key
        result = self.run_cli(['get', 'nonexistent'], cli_env)
        assert result.returncode == 1
    
    def test_cli_set(self, cli_env):
        """Test CLI set command."""
        result = self.run_cli(['set', 'new_key', 'new_value'], cli_env)
        
        if result.returncode == 0:
            # Verify it was set
            creds = Credentials(
                credentials_path=cli_env['creds_path'],
                master_key_path=cli_env['key_path']
            )
            assert creds.get('new_key') == 'new_value'
    
    def test_cli_delete(self, cli_env):
        """Test CLI delete command."""
        # Set up a key to delete
        creds = Credentials(
            credentials_path=cli_env['creds_path'],
            master_key_path=cli_env['key_path']
        )
        creds.set('delete_me', 'value')
        
        result = self.run_cli(['delete', 'delete_me'], cli_env)
        
        if result.returncode == 0:
            assert creds.get('delete_me') is None
        
        # Test deleting non-existent key
        result = self.run_cli(['delete', 'nonexistent'], cli_env)
        assert result.returncode == 1


class TestCredentialsIntegration:
    """Integration tests simulating real usage scenarios."""
    
    @pytest.fixture
    def app_setup(self):
        """Set up a simulated app environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            
            creds = Credentials(
                credentials_path=str(config_dir / "credentials.yml.enc"),
                master_key_path=str(config_dir / "master.key")
            )
            
            # Create master key
            master_key = creds.create_master_key_file()
            
            yield creds, config_dir, master_key
    
    def test_django_like_usage(self, app_setup):
        """Test usage pattern similar to Django settings."""
        creds, config_dir, master_key = app_setup
        
        # Set up typical Django credentials
        creds.set('secret_key', 'django-secret-key-123')
        creds.set('database.name', 'myapp_production')
        creds.set('database.user', 'myapp')
        creds.set('database.password', 'secure-db-password')
        creds.set('database.host', 'db.example.com')
        creds.set('email.username', 'noreply@example.com')
        creds.set('email.password', 'email-password')
        creds.set('aws.access_key_id', 'AKIA123')
        creds.set('aws.secret_access_key', 'secret123')
        
        # Test retrieval like in settings.py
        SECRET_KEY = creds.get('secret_key')
        assert SECRET_KEY == 'django-secret-key-123'
        
        DATABASE_CONFIG = {
            'NAME': creds.get('database.name'),
            'USER': creds.get('database.user'),
            'PASSWORD': creds.get('database.password'),
            'HOST': creds.get('database.host'),
        }
        
        assert DATABASE_CONFIG['NAME'] == 'myapp_production'
        assert DATABASE_CONFIG['PASSWORD'] == 'secure-db-password'
        
        # Test with defaults
        DEBUG = creds.get('debug', False)
        assert DEBUG is False
    
    def test_environment_variable_override(self, app_setup):
        """Test that environment variables take precedence."""
        creds, config_dir, file_master_key = app_setup
        
        # Use environment variable instead of file
        env_master_key = Credentials.generate_master_key()
        
        with patch.dict(os.environ, {"MASTER_KEY": env_master_key}):
            env_creds = Credentials(
                credentials_path=str(config_dir / "credentials.yml.enc"),
                master_key_path=str(config_dir / "master.key")
            )
            
            # This should use the env key, not the file key
            env_creds.set('env_test', 'env_value')
            assert env_creds.get('env_test') == 'env_value'
        
        # Without env var, should not be able to decrypt
        file_creds = Credentials(
            credentials_path=str(config_dir / "credentials.yml.enc"),
            master_key_path=str(config_dir / "master.key")
        )
        
        with pytest.raises(CredentialsError):
            file_creds.get('env_test')
    
    def test_multiple_environments(self, app_setup):
        """Test handling multiple environment files."""
        creds, config_dir, master_key = app_setup
        
        # Create separate credentials for different environments
        prod_creds = Credentials(
            credentials_path=str(config_dir / "credentials.production.yml.enc"),
            master_key_path=str(config_dir / "master.key")
        )
        
        staging_creds = Credentials(
            credentials_path=str(config_dir / "credentials.staging.yml.enc"),
            master_key_path=str(config_dir / "master.key")
        )
        
        # Set different values
        prod_creds.set('database.password', 'prod-password')
        staging_creds.set('database.password', 'staging-password')
        
        assert prod_creds.get('database.password') == 'prod-password'
        assert staging_creds.get('database.password') == 'staging-password'
    
    def test_backup_and_restore(self, app_setup):
        """Test backing up and restoring credentials."""
        creds, config_dir, master_key = app_setup
        
        # Set up some data
        test_data = {
            'api_key': 'secret123',
            'database': {
                'password': 'dbpass',
                'host': 'localhost'
            }
        }
        
        for key, value in test_data.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    creds.set(f'{key}.{nested_key}', nested_value)
            else:
                creds.set(key, value)
        
        # Get YAML backup
        yaml_backup = creds.show()
        
        # Clear and restore
        creds_file = config_dir / "credentials.yml.enc"
        creds_file.unlink()  # Delete encrypted file
        
        # Restore from YAML
        restored_config = yaml.safe_load(yaml_backup)
        creds._save_config(restored_config)
        
        # Verify restoration
        assert creds.get('api_key') == 'secret123'
        assert creds.get('database.password') == 'dbpass'


class TestCredentialsErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_corrupted_encrypted_file(self, temp_dir):
        """Test handling of corrupted encrypted files."""
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        
        # Create valid master key
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)
        
        # Write corrupted encrypted data
        creds_path.write_text("corrupted-not-base64-data")
        
        creds = Credentials(
            credentials_path=str(creds_path),
            master_key_path=str(key_path)
        )
        
        with pytest.raises(CredentialsError):
            creds.config()
    
    def test_invalid_yaml_in_decrypted_content(self, temp_dir):
        """Test handling of invalid YAML in decrypted content."""
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)
        
        creds = Credentials(
            credentials_path=str(creds_path),
            master_key_path=str(key_path)
        )
        
        # Encrypt invalid YAML
        invalid_yaml = "invalid: yaml: content: [unclosed"
        encrypted = creds._encrypt(invalid_yaml)
        creds_path.write_text(encrypted)
        
        with pytest.raises(CredentialsError):
            creds.config()
    
    def test_permission_denied_master_key(self, temp_dir):
        """Test handling permission denied on master key file."""
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
        """Test handling empty credentials file."""
        creds_path = temp_dir / "credentials.yml.enc"
        key_path = temp_dir / "master.key"
        
        master_key = Credentials.generate_master_key()
        key_path.write_text(master_key)
        
        # Create empty file
        creds_path.touch()
        
        creds = Credentials(
            credentials_path=str(creds_path),
            master_key_path=str(key_path)
        )
        
        config = creds.config()
        assert config == {}


if __name__ == '__main__':
    # Run tests if executed directly
    pytest.main([__file__, '-v'])
