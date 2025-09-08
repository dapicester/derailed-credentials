# Python equivalent of Rails credentials system

This module provides encrypted configuration management similar to Rails credentials,
allowing you to store sensitive configuration data encrypted at rest.

Usage:

    # Command line interface
    python credentials.py edit                    # Edit credentials file
    python credentials.py show                    # Show decrypted credentials
    python credentials.py generate-key            # Generate new master key

    # Programmatic usage
    from credentials import Credentials

    creds = Credentials()
    api_key = creds.get('api_key')
    db_password = creds.get('database', {}).get('password')
