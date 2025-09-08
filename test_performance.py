"""
Performance tests for the credentials system.
"""

import pytest
import time
from pathlib import Path

from credentials import Credentials


class TestPerformance:
    """Test performance characteristics of the credentials system."""
    
    @pytest.mark.slow
    def test_large_config_performance(self, isolated_environment):
        """Test performance with large configuration files."""
        env = isolated_environment
        creds = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        # Create master key
        creds.create_master_key_file()
        
        # Create large configuration
        large_config = {}
        for i in range(1000):
            large_config[f'key_{i}'] = {
                'value': f'secret_value_{i}',
                'nested': {
                    'deep_value': f'deep_secret_{i}',
                    'list': [f'item_{j}' for j in range(10)]
                }
            }
        
        # Time saving
        start_time = time.time()
        creds._save_config(large_config)
        save_time = time.time() - start_time
        
        # Time loading
        creds._config_cache = None  # Clear cache
        start_time = time.time()
        loaded_config = creds.config()
        load_time = time.time() - start_time
        
        # Verify correctness
        assert loaded_config == large_config
        
        # Performance assertions (adjust based on your requirements)
        assert save_time < 5.0, f"Saving took too long: {save_time}s"
        assert load_time < 2.0, f"Loading took too long: {load_time}s"
    
    @pytest.mark.slow
    def test_many_operations_performance(self, isolated_environment):
        """Test performance of many get/set operations."""
        env = isolated_environment
        creds = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        creds.create_master_key_file()
        
        # Time many set operations
        start_time = time.time()
        for i in range(100):
            creds.set(f'key_{i}', f'value_{i}')
            creds.set(f'nested.key_{i}', f'nested_value_{i}')
        set_time = time.time() - start_time
        
        # Time many get operations
        start_time = time.time()
        for i in range(100):
            assert creds.get(f'key_{i}') == f'value_{i}'
            assert creds.get(f'nested.key_{i}') == f'nested_value_{i}'
        get_time = time.time() - start_time
        
        # Performance assertions
        assert set_time < 10.0, f"Set operations took too long: {set_time}s"
        assert get_time < 1.0, f"Get operations took too long: {get_time}s"
    
    def test_caching_effectiveness(self, isolated_environment):
        """Test that caching improves performance."""
        env = isolated_environment
        creds = Credentials(
            credentials_path=str(env['credentials_path']),
            master_key_path=str(env['master_key_path'])
        )
        
        creds.create_master_key_file()
        
        # Set up some data
        test_data = {'api_key': 'secret', 'database': {'password': 'dbpass'}}
        creds._save_config(test_data)
        
        # First load (should decrypt file)
        start_time = time.time()
        config1 = creds.config()
        first_load_time = time.time() - start_time
        
        # Second load (should use cache)
        start_time = time.time()
        config2 = creds.config()
        cached_load_time = time.time() - start_time
        
        assert config1 == config2
        # Cached load should be significantly faster
        assert cached_load_time < first_load_time / 2



