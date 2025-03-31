# SignalWire to vCon Processor

This Python script continuously polls the SignalWire API for new call recordings, creates vCon (virtual conversation) objects from these recordings, and sends them to a specified webhook. It's designed to run as a long-running process, making it suitable for production environments where continuous monitoring of new recordings is required.

## Features

- Polls SignalWire API at configurable intervals
- Creates vCon objects from SignalWire recordings
- Includes audio content in the vCon
- Sends vCons to a configured webhook
- Handles graceful shutdown on termination signals
- Provides detailed logging
- Supports debug mode for local testing and diagnostics

## Prerequisites

- Python 3.12
- SignalWire account and API credentials
- Webhook endpoint to receive vCon data

## Installation

1. Clone this repository or download the script.

2. Install dependencies using Poetry (recommended):

   ```bash
   # Install Poetry
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install dependencies
   poetry install
   ```

   Alternatively, you can use pip:

   ```bash
   pip install signalwire vcon requests python-dotenv
   ```

## Development Setup

This project uses Poetry for dependency management. To set up a development environment:

1. Install Poetry if you haven't already:

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install project dependencies:

   ```bash
   poetry install
   ```

   This will create a virtual environment and install both main and development dependencies.

3. Activate the virtual environment:

   ```bash
   poetry shell
   ```

4. You can now run the script, tests, or other development tasks within this environment.

## Configuration

The script uses environment variables for configuration. Set the following variables before running the script:

- `SIGNALWIRE_PROJECT_ID`: Your SignalWire Project ID
- `SIGNALWIRE_AUTH_TOKEN`: Your SignalWire Auth Token
- `SIGNALWIRE_SPACE_URL`: Your SignalWire Space URL
- `WEBHOOK_URL`: The URL of the webhook to receive vCon data (not required in debug mode)
- `POLL_INTERVAL`: The interval (in seconds) between API polls (default: 300)
- `DEBUG_MODE`: Set to "true" to enable debug mode (default: "false")
- `DEBUG_DIR`: Directory where vCon files will be saved in debug mode (default: "vcon_debug")

Example:

```bash
export SIGNALWIRE_PROJECT_ID=your_project_id
export SIGNALWIRE_AUTH_TOKEN=your_auth_token
export SIGNALWIRE_SPACE_URL=your_space_url
export WEBHOOK_URL=https://your-webhook-endpoint.com/vcon
export POLL_INTERVAL=300
export DEBUG_MODE=false
export DEBUG_DIR=vcon_debug
```

### Debug Mode

When `DEBUG_MODE` is set to "true", the script will:

1. Not require a webhook URL
2. Save vCon objects as JSON files to the directory specified by `DEBUG_DIR` instead of sending them to a webhook
3. Log additional information to assist with debugging

This is useful for testing and development without needing a webhook endpoint.

## Usage

Run the script using Poetry:

```bash
poetry run python signalwire_vcon_script.py
```

Or activate the Poetry environment first:

```bash
poetry shell
python signalwire_vcon_script.py
```

The script will start polling the SignalWire API for new recordings at the specified interval. For each new recording, it will:

1. Create a vCon object
2. Download the audio content
3. Add the audio content to the vCon
4. Send the vCon to the configured webhook (or save to file in debug mode)

## Logging

The script logs its operations to the console. You can redirect this output to a file for persistent logging:

```
python signalwire_vcon_script.py > signalwire_vcon_processor.log 2>&1
```

## Termination

The script can be terminated gracefully in the following ways:

- Press Ctrl+C in the terminal where it's running
- Send a SIGTERM signal (e.g., `kill <pid>`)
- Use process management tools like supervisord or systemd

When terminated, the script will complete processing the current batch of recordings before shutting down.

## Error Handling

The script includes error handling to manage issues with the SignalWire API, webhook communication, or other unexpected errors. All errors are logged for later review.

## Testing

This project uses pytest for testing and Poetry for dependency management. The test suite verifies the functionality of the SignalWire adapter, including API interactions and vCon creation.

### Running Tests

To run the tests:

```bash
./run_tests.sh
```

This script will:
1. Install all dependencies using Poetry
2. Run the test suite with code coverage reporting
3. Generate HTML coverage reports in the `htmlcov/` directory

### Test Configuration

Tests are configured in `pyproject.toml` with the following settings:
- Full test coverage reporting for the `signalwire_adapter` module
- Both terminal and HTML coverage reports
- Verbose test output

### Adding New Tests

When adding new functionality, please ensure test coverage by adding test cases to `test_signalwire_adapter.py`.

## Production Deployment

For production deployment, consider using a process manager like supervisord or systemd to ensure the script keeps running and to manage automatic restarts if needed.

## Python 3.12 Compatibility

This project has been updated to use Python 3.12, which offers:

- Improved performance
- Better error messages with more precise information
- Enhanced type hinting and static analysis
- More efficient memory management

If you're upgrading from a previous version:

1. Make sure you have Python 3.12 installed
2. Update your virtual environment if you're using one
3. Install dependencies using Poetry: `poetry install`
   
Docker users: The Dockerfile has been updated to use the Python 3.12 base image.

## Contributing

Contributions to improve the script are welcome. Please submit a pull request or create an issue to discuss proposed changes.

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.

## Support

For questions or issues, please open an issue in this repository. We'll do our best to address your concerns promptly.