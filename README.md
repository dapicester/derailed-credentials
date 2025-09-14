# Derailed Credentials

[![codecov](https://codecov.io/gh/dapicester/derailed-credentials/graph/badge.svg?token=SL8S6G7S4N)](https://codecov.io/gh/dapicester/derailed-credentials)

Missing a tool like `rails credentials:edit` for your Python projects?

**Derailed Credentials** brings encrypted secret management to Python,
inspired by [Rails Credentials](https://guides.rubyonrails.org/security.html#custom-credentials).
Securely manage encrypted secrets and configuration files for your projects.

## Description

The `derailed` commands provide access to encrypted credentials,
so you can safely store access tokens, database passwords, and the like
safely inside the app without relying on a mess of ENVs.

This also allows for atomic deploys: no need to coordinate key changes
to get everything working as the keys are shipped with the code.

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
    api_key = creds.api_key
    db_password = creds.database.password

They master key can be read from a file, default to `config/master.key`, or
can be set using the `MASTER_KEY` environment variable.

Don't lose this master key! Put it in a password manager your team can access.
Should you lose it no one, including you, will be able to access any encrypted
credentials.
