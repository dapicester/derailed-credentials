"""
Security-focused tests for the credentials system.
"""

import pytest
import os
import stat
from pathlib import Path

from credentials import Credentials


class TestSecurity:
    """Test security aspects of the credentials system."""
    
    def test_master_key_file_permissions(self, isolated_environment):
        """Test that master key file has correct permissions."""
        env = isolated_environment
        creds = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        # Create master key file
        creds.create_master_key_file()
        
        # Check file permissions
        key_file = env['master_key_path']
        file_stat = key_file.stat()
        
        # Should be readable/writable by owner only (600)
        expected_permissions = stat.S_IRUSR | stat.S_IWUSR
        actual_permissions = file_stat.st_mode & 0o777
        
        assert actual_permissions == 0o600, f"Wrong permissions: {oct(actual_permissions)}"
    
    def test_different_keys_produce_different_encryption(self, isolated_environment):
        """Test that different keys produce different encrypted output."""
        env = isolated_environment
        
        # Create two different credentials instances with different keys
        creds1 = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        creds2_key_path = env['config_dir'] / 'master2.key'
        creds2 = Credentials(
            credentials_path=str(env['config_dir'] / 'credentials2.yml.enc'),
            master_key_path=str(creds2_key_path)
        )
        
        # Generate different keys
        key1 = creds1.create_master_key_file()
        creds2.master_key_path.write_text(Credentials.generate_master_key())
        
        # Encrypt same data with both
        test_data = "sensitive information"
        encrypted1 = creds1._encrypt(test_data)
        encrypted2 = creds2._encrypt(test_data)
        
        # Should produce different encrypted output
        assert encrypted1 != encrypted2
        
        # But both should decrypt correctly with their respective keys
        assert creds1._decrypt(encrypted1) == test_data
        assert creds2._decrypt(encrypted2) == test_data
    
    def test_key_derivation_consistency(self, isolated_environment):
        """Test that key derivation is consistent."""
        master_key = "test-master-key"
        
        creds = Credentials()
        
        # Same master key should produce same derived key
        key1 = creds._derive_key(master_key)
        key2 = creds._derive_key(master_key)
        
        assert key1 == key2
        
        # Different master keys should produce different derived keys
        key3 = creds._derive_key("different-master-key")
        assert key1 != key3
    
    def test_encrypted_file_contains_no_plaintext(self, credentials_with_data):
        """Test that encrypted file doesn't contain plaintext secrets."""
        setup = credentials_with_data
        creds = setup['credentials']
        data = setup['data']
        
        # Read the encrypted file
        encrypted_content = setup['credentials_path'].read_text()
        
        # Check that sensitive data is not in plaintext
        sensitive_values = [
            'django-secret-key-12345',
            'testpass123',
            'sk_test_456',
            'emailpass',
            'secret123'
        ]
        
        for value in sensitive_values:
            assert value not in encrypted_content, f"Found plaintext secret: {value}"
    
    def test_memory_cleanup(self, isolated_environment):
        """Test that sensitive data is not left in memory longer than necessary."""
        env = isolated_environment
        creds = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        creds.create_master_key_file()
        
        # Set sensitive data
        creds.set('secret', 'very-sensitive-data')
        
        # Access the data
        secret = creds.get('secret')
        assert secret == 'very-sensitive-data'
        
        # Clear cache
        creds._config_cache = None
        
        # The cache should be cleared
        assert creds._config_cache is None



