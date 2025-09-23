# AnyRouter Auto

> Minimal dependency CLI helper to automate the daily sign-in on [anyrouter.top](https://anyrouter.top/).

## Features

- Generates OAuth authorization URL for the GitHub login flow and captures the callback via a lightweight local HTTP server.
- Stores access and refresh tokens using a JSON file with optional passphrase-based obfuscation.
- Provides `authorize`, `signin`, `status`, `schedule`, and `clear` commands via a single CLI entry point.
- Persists sign-in history in CSV format for later inspection.
- Ships a simple daily scheduler implemented with the Python standard library only.

## Installation

The project targets Python 3.11+. Create a virtual environment and install the package locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Configuration

Set the GitHub OAuth client identifier through the `ANYROUTER_CLIENT_ID` environment variable, or pass `--client-id` to the `authorize` command. Adjust the daily schedule via the `ANYROUTER_SCHEDULE_HOUR` and `ANYROUTER_SCHEDULE_MINUTE` variables if needed.

## Usage

1. **Authorize**
   ```bash
   anyrouter-auto authorize --client-id <github_client_id>
   ```
   The command prints the authorization URL and attempts to open it in your default browser. After granting access, the CLI exchanges the authorization code and stores the resulting tokens in `~/.anyrouter_auto/credentials.json`.

2. **Manual sign-in**
   ```bash
   anyrouter-auto signin
   ```
   The CLI refreshes expired access tokens automatically (if a refresh token is available), performs the sign-in request, and logs the result to `history.csv`.

3. **Status overview**
   ```bash
   anyrouter-auto status
   ```
   Displays information about the stored credentials and prints the latest history entries.

4. **Daily scheduler**
   ```bash
   anyrouter-auto schedule
   ```
   Starts a background loop that executes the sign-in once per day. Stop the process with `Ctrl+C`.

5. **Clear credentials**
   ```bash
   anyrouter-auto clear
   ```
   Removes the stored credential file.

Pass `--passphrase` to `authorize`, `signin`, `status`, or `schedule` to protect the credential file with a user-provided secret.

## Development

- Code style follows standard library modules—only the Python standard library is required at runtime.
- Tests are not provided in this initial drop. You can verify import-time regressions with `python -m compileall anyrouter_auto`.

## Disclaimer

The HTTP endpoints used here are based on assumptions of the anyrouter.top API surface and may require adjustments to match the real service responses. Review and adapt the network calls (`anyrouter_auto/auth.py` and `anyrouter_auto/signin.py`) before using the tool in production.
