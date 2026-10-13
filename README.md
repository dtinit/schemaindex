# schemaindex

A schema registry. [Schemas.Pub](https://schemas.pub)
is the official instance hosted by the [Data Transfer Initiative](https://github.com/dtinit).

How to use:

1. Publish and discover schemas with an account at https://schemas.pub, assign
   permanent URLs as schema ids.
2. Get AI agent access at https://schemas.pub/mcp (using your account and OAuth)
   to allow it to discover and work with public schemas
3. Run a private instance for local MCP access if you have personal/private schemas

## Local setup

To run locally, you'll first need to install Python (3.11) and pip.

To install pip dependencies, run `pip install -r requirements-dev.txt`.

This project uses PostgreSQL in every environment, including local development.

The settings default to `postgres://postgres:postgres@localhost:5432/schemaindex`. If your local PostgreSQL uses different credentials, host, port, or database name, override the connection string by creating a git-ignored `.env` file in the project root:

```sh
# .env
DJ_DATABASE_CONN_STRING=postgres://<user>:<password>@localhost:5432/<database>
```

To create the database, run `createdb -U postgres schemaindex` (or use the user and database name from your `.env`).

To create the database tables, run `python3 manage.py migrate`. Run it again whenever you pull changes that include new migrations.

To start the project, run:

```sh
python3 manage.py runserver
```

During local development, emails will output to the console instead of actually sending.

## Configuration

To change settings for your instance, create `schemaindex/settings/personal.py`, import the development settings, and override the values you want:

```python
# schemaindex/settings/personal.py

from .development import *

SITE_NAME = "Acme Schemas"
ENABLE_ACCOUNTS = True
```

This file is excluded from source control, so your settings stay local and won't conflict with updates you pull.

## User Accounts

By default, the project runs without user accounts and allows all requests without authentication.
Set `ENABLE_ACCOUNTS` to `True` to support individual user accounts with required authorization for managing schemas, using the API, and using MCP.

With accounts off, you already have access to the database management portal at http://localhost:8000/admin. With accounts on, create a superuser for yourself with `python3 manage.py createsuperuser` to use it.

Without accounts, every request has full admin access, so the server refuses to start if `ALLOWED_HOSTS` includes anything other than local addresses like `localhost`. To share an instance with other people, turn accounts on and add your server's hostname to `ALLOWED_HOSTS`.

## Site name

Set `SITE_NAME` to change the name shown throughout the site, in emails, and by the MCP server.

## Contributing

For code utilities, linting, formatting, and precommit checks, see [contribute.md](contribute.md).
