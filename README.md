# Derailed Credentials

Missing a tool like `rails credentials:edit` for your Python projects?

**Derailed Credentials** brings encrypted secret management to Python,
inspired by [Rails Credentials](https://guides.rubyonrails.org/security.html#custom-credentials).
Securely manage encrypted secrets and configuration files for your projects.

## Installation

    pipx install derailed-credentials

## Usage

As a standalone command-line tool:

    derailed generate-key            # Generate new master key
    derailed edit                    # Edit credentials file
    derailed show                    # Show decrypted credentials

Programmatic usage:

    from derailed import Credentials

    creds = Credentials()
    api_key = creds.get('api_key')
    db_password = creds.get('database.password')
