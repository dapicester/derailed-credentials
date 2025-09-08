# conftest.py
"""
Shared pytest fixtures and configuration.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from credentials import Credentials


@pytest.fixture(scope="session")
def sample_credentials_data():
    """Sample credentials data for testing."""
    return {
        'secret_key': 'django-secret-key-12345',
        'database': {
            'name': 'myapp_test',
            'user': 'testuser',
            'password': 'testpass123',
            'host': 'localhost',
            'port': 5432
        },
        'api_keys': {
            'stripe': {
                'publishable': 'pk_test_123',
                'secret': 'sk_test_456'
            },
            'openai': 'sk-test-789'
        },
        'email': {
            'username': 'test@example.com',
            'password': 'emailpass'
        },
        'aws': {
            'access_key_id': 'AKIA123',
            'secret_access_key': 'secret123',
            's3_bucket': 'test-bucket'
        },
        'debug': True,
        'allowed_hosts': ['localhost', '127.0.0.1'],
        'feature_flags': {
            'new_ui': False,
            'beta_feature': True
        }
    }


@pytest.fixture
def isolated_environment():
    """Create an isolated environment for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create config directory structure
        config_dir = temp_path / "config"
        config_dir.mkdir()
        
        # Patch environment variables
        original_env = os.environ.copy()
        
        # Clear any existing credentials environment variables
        for key in list(os.environ.keys()):
            if 'MASTER_KEY' in key or 'CREDENTIALS' in key:
                del os.environ[key]
        
        try:
            yield {
                'temp_dir': temp_path,
                'config_dir': config_dir,
                'credentials_path': config_dir / 'credentials.yml.enc',
                'master_key_path': config_dir / 'master.key'
            }
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)


@pytest.fixture
def credentials_with_data(isolated_environment, sample_credentials_data):
    """Create credentials instance with sample data."""
    env = isolated_environment
    
    # Create and set up credentials
    creds = Credentials(
        credentials_path=str(env['credentials_path']),
        master_key_path=str(env['master_key_path']),
        master_key_env="TEST_MASTER_KEY"
    )
    
    # Generate master key
    master_key = creds.create_master_key_file()
    
    # Load sample data
    creds._save_config(sample_credentials_data)
    
    return {
        'credentials': creds,
        'master_key': master_key,
        'data': sample_credentials_data,
        **env
    }


@pytest.fixture
def mock_editor():
    """Mock editor for testing edit functionality."""
    def _mock_editor(content_modifier=None):
        """
        Create a mock editor that optionally modifies content.
        
        Args:
            content_modifier: Function to modify the content
        """
        def mock_subprocess_run(cmd, **kwargs):
            # Simulate editor opening and modifying file
            if content_modifier:
                file_path = cmd[-1]  # Last argument should be file path
                with open(file_path, 'r') as f:
                    original_content = f.read()
                
                modified_content = content_modifier(original_content)
                
                with open(file_path, 'w') as f:
                    f.write(modified_content)
            
            # Return successful result
            class MockResult:
                returncode = 0
            return MockResult()
        
        return mock_subprocess_run
    
    return _mock_editor



