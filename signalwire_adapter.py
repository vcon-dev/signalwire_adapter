import os
import time
import signal
from datetime import datetime, timedelta, UTC
from vcon import Vcon
from vcon.party import Party
from vcon.dialog import Dialog
import pathlib
import requests
import json
import logging
import dotenv
import requests
import email.utils


# Load environment variables from .env file
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SignalWire credentials
PROJECT_ID = os.getenv('SIGNALWIRE_PROJECT_ID')
AUTH_TOKEN = os.getenv('SIGNALWIRE_AUTH_TOKEN')
SPACE_URL = os.getenv('SIGNALWIRE_SPACE_URL')

# Webhook URL (not required in debug mode)
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Debug mode settings
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
DEBUG_DIR = os.getenv('DEBUG_DIR', 'vcon_debug')

# Poll interval in seconds (default to 5 minutes if not set)
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 300))

# File to store processed call SIDs
PROCESSED_CALLS_FILE = os.getenv('PROCESSED_CALLS_FILE', 'processed_calls.json')

# Retention period for processed calls in days (default to 30 days)
# After this period, call records will be removed from the processed_calls.json file
RETENTION_DAYS = int(os.getenv('RETENTION_DAYS', 30))

# Check if all required environment variables are set
required_vars = {
    'SIGNALWIRE_PROJECT_ID': PROJECT_ID,
    'SIGNALWIRE_SPACE_URL': SPACE_URL,
    'SIGNALWIRE_AUTH_TOKEN': AUTH_TOKEN,
    'POLL_INTERVAL': POLL_INTERVAL
}

# Webhook URL is only required if not in debug mode
if not DEBUG_MODE and not WEBHOOK_URL:
    required_vars['WEBHOOK_URL'] = WEBHOOK_URL

missing_vars = [var for var, value in required_vars.items() if value is None]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

# If in debug mode, ensure the debug directory exists
if DEBUG_MODE:
    debug_path = pathlib.Path(DEBUG_DIR)
    debug_path.mkdir(parents=True, exist_ok=True)
    logging.info(f"Running in DEBUG MODE - vCons will be written to: {debug_path.absolute()}")

recording_url = f"{SPACE_URL}/api/laml/2010-04-01/Accounts/{PROJECT_ID}/Recordings"
calls_url = f"{SPACE_URL}/api/laml/2010-04-01/Accounts/{PROJECT_ID}/Calls"

# Flag to control the main loop
running = True

def signal_handler(signum, frame):
    """Handle termination signals"""
    global running
    logging.info(f"Received signal {signum}. Shutting down gracefully...")
    running = False

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
last_check_time = datetime.now(UTC) - timedelta(seconds=POLL_INTERVAL)


def load_processed_calls():
    """
    Load the list of already processed call SIDs from the JSON file.
    
    :return: Dictionary of processed call SIDs with timestamps
    """
    try:
        with open(PROCESSED_CALLS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is empty/invalid, return empty dict
        return {}

def save_processed_calls(processed_calls):
    """
    Save the list of processed call SIDs to the JSON file.
    
    :param processed_calls: Dictionary of processed call SIDs with timestamps
    """
    with open(PROCESSED_CALLS_FILE, 'w') as f:
        json.dump(processed_calls, f)

def cleanup_old_call_records(processed_calls):
    """
    Remove call records that are older than the retention period.
    
    :param processed_calls: Dictionary of processed call SIDs with timestamps
    :return: Cleaned dictionary with only recent call records
    """
    now = datetime.now(UTC)
    retention_cutoff = now - timedelta(days=RETENTION_DAYS)
    
    # Count before cleanup
    original_count = len(processed_calls)
    
    # Filter out old records
    recent_calls = {}
    for call_sid, timestamp_str in processed_calls.items():
        try:
            # Parse the timestamp (handle both formats with/without timezone)
            if timestamp_str.endswith('Z'):
                # Already in UTC format
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Try to parse with timezone, fall back to assuming UTC
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    # If parsing fails, assume it's UTC without the timezone info
                    timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=UTC)
            
            # Keep only records newer than the cutoff
            if timestamp > retention_cutoff:
                recent_calls[call_sid] = timestamp_str
        except (ValueError, TypeError):
            # If we can't parse the timestamp, keep the record to be safe
            recent_calls[call_sid] = timestamp_str
            logging.warning(f"Could not parse timestamp for call_sid {call_sid}: {timestamp_str}")
    
    # Count after cleanup
    removed_count = original_count - len(recent_calls)
    if removed_count > 0:
        logging.info(f"Cleaned up {removed_count} call records older than {RETENTION_DAYS} days")
    
    return recent_calls

def fetch_call_meta(call_sid):
    """
    Fetch the meta data of a call given the call SID.

    :param call_sid: The SID of the call to fetch the meta data for
    :return: A dictionary containing the call meta data
    """

    url = f"{calls_url}/{call_sid}"

    payload = {}
    headers = {
        'Accept': 'application/json'
    }

    # Send a GET request to the SignalWire API
    response = requests.request("GET", url, 
                                headers=headers, 
                                data=payload, 
                                auth=(PROJECT_ID, AUTH_TOKEN))

    # Return the meta data as a JSON object
    return response.json()
    
    
def fetch_new_recordings(last_check_time):
    """
    Fetch all the recordings created after the given date and time.

    :param last_check_time: The date and time to fetch recordings after
    :return: A list of recordings created after the given date and time
    """
    url = f"{recording_url}/?DateCreatedAfter={last_check_time.isoformat()}"
    payload = {}
    headers = {
        'Accept': 'application/json'
    }
    
    response = requests.request("GET",
                                url,
                                headers=headers,
                                data=payload,
                                auth=(PROJECT_ID, AUTH_TOKEN))
    
    # Check if the request was successful
    if response.status_code == 200:
        # Extract the recordings from the response
        recordings = response.json()['recordings']
        return recordings
    else:
        raise Exception(f"Failed to fetch recordings: {response.status_code}")
    
    
def fetch_transcription(url):
    """
    Fetch the transcription of a recording given the transcription URL.

    :param url: The URL of the transcription
    :return: The transcription as a JSON object
    :raises Exception: If the request is not successful
    """
    url = f"{SPACE_URL}{url}"
    
    response = requests.get(url, auth=(PROJECT_ID, AUTH_TOKEN))
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch transcription: {response.status_code}")
    
def format_to_e164(phone_number):
    """
    Ensure a phone number is formatted in E.164 format.
    
    :param phone_number: Phone number string to format
    :return: E.164 formatted phone number
    """
    # Remove any non-digit characters except the leading plus
    cleaned = ''.join(c for i, c in enumerate(phone_number) if c.isdigit() or (i == 0 and c == '+'))
    
    # Ensure there's a leading plus
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
        
    return cleaned
    
def create_vcon_from_recordings(recordings, call_meta) -> Vcon:
    """
    Create a vCon object from multiple SignalWire recording objects that belong to the same call.

    :param recordings: List of SignalWire recording objects for the same call
    :param call_meta: The call metadata
    :return: The created vCon object
    """
    vcon = Vcon.build_new()
    
    # Create Party objects with named parameters, ensuring phone numbers are in E.164 format
    party1 = Party(tel=format_to_e164(call_meta['to_formatted']))
    vcon.add_party(party1)
    party2 = Party(tel=format_to_e164(call_meta['from_formatted']))
    vcon.add_party(party2)
    
    # Add all recordings as dialogs
    for recording in recordings:
        # Try to convert recording['date_created'] from RFC 2822 to ISO format
        try:
            recording_date_created = email.utils.parsedate_to_datetime(recording['date_created'])
            recording_date_created_iso = recording_date_created.isoformat()
        except TypeError:
            logging.warning(f"Failed to parse recording['date_created'] for {recording['sid']}")
            recording_date_created_iso = None
            
        # Calculate the correct URL for the recording
        recording_url = f"{SPACE_URL}{recording['uri']}"
        # remove the trailing .json and add .mp3
        recording_url = recording_url[:-5] + '.mp3'
        
        # Create Dialog with named parameters
        dialog = Dialog(
            start=recording_date_created_iso, 
            parties=[0, 1], 
            type="recording", 
            duration=recording['duration'],
            url=recording_url,
            mimetype="audio/mpeg"
        )
        vcon.add_dialog(dialog)
        
        # Add attachment with recording metadata
        vcon.add_attachment(
            type="recording_metadata",
            body={
                "sid": recording['sid'],
                "account_sid": recording['account_sid'],
                "call_sid": recording['call_sid'],
                "channels": recording['channels'],
                "source": "SignalWire",
            }
        )
        
        # Add the transcription if it exists
        if 'transcriptions' in recording['subresource_uris']:
            response = fetch_transcription(recording['subresource_uris']['transcriptions'])
            
            for transcription in response['transcriptions']:
                if 'text' in transcription:
                    vcon.add_attachment(
                        type="transcription",
                        body=transcription
                    )
    
    return vcon

def download_recording(url):
    """Download the recording file"""
    response = requests.get(url, auth=(PROJECT_ID, AUTH_TOKEN))
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download recording: {response.status_code}")

def write_vcon_to_file(vcon, call_sid):
    """
    Write the vCon to a local file in the debug directory
    
    :param vcon: The vCon object to write
    :param call_sid: The call SID for this vCon
    """
    # Create a filename based on the call SID, vCon UUID and timestamp
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{call_sid}_{vcon.uuid}.json"
    file_path = pathlib.Path(DEBUG_DIR) / filename
    
    try:
        with open(file_path, 'w') as f:
            f.write(vcon.to_json())
        logging.info(f"Successfully wrote vCon for call {call_sid} to file: {file_path}")
    except Exception as e:
        logging.error(f"Failed to write vCon to file: {str(e)}")

def send_vcon_to_webhook(vcon, call_sid):
    """Send the vCon to the configured webhook or write to file in debug mode"""
    # In debug mode, write to file instead of sending to webhook
    if DEBUG_MODE:
        write_vcon_to_file(vcon, call_sid)
        return

    # Normal webhook operation
    headers = {'Content-Type': 'application/json'}
    payload = vcon.to_json()

    try:
        response = requests.post(WEBHOOK_URL, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"Successfully sent vCon for call {call_sid} to webhook: {vcon.uuid}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send vCon to webhook: {str(e)}")

def process_recordings(last_check_time):
    new_recordings = fetch_new_recordings(last_check_time)
    processed_calls = load_processed_calls()
    
    # Clean up old call records to prevent excessive growth of the processed_calls.json file
    processed_calls = cleanup_old_call_records(processed_calls)
    
    # Group recordings by call_sid
    recordings_by_call = {}
    for recording in new_recordings:
        call_sid = recording['call_sid']
        if call_sid not in recordings_by_call:
            recordings_by_call[call_sid] = []
        recordings_by_call[call_sid].append(recording)
    
    # Process each call_sid only once
    for call_sid, recordings in recordings_by_call.items():
        # Skip if we've already processed this call_sid
        if call_sid in processed_calls:
            logging.info(f"Skipping already processed call: {call_sid}")
            continue
            
        logging.info(f"Processing conversation with call_sid: {call_sid} ({len(recordings)} recordings)")

        try:
            # Fetch call metadata once per call
            call_meta = fetch_call_meta(call_sid)
            
            # Create a single vCon for all recordings in this call
            vcon = create_vcon_from_recordings(recordings, call_meta)
            
            # Send the vCon to the configured webhook
            send_vcon_to_webhook(vcon, call_sid)
            
            # Mark this call as processed
            processed_calls[call_sid] = datetime.now(UTC).isoformat()
            
            logging.info(f"Processed vCon for call: {call_sid}")
        except Exception as e:
            logging.error(f"Error processing call {call_sid}: {str(e)}")
    
    # Save the updated processed calls list with any new entries and after cleanup
    save_processed_calls(processed_calls)

def main():
    global running
    last_check_time = datetime.now(UTC) - timedelta(seconds=POLL_INTERVAL)

    if DEBUG_MODE:
        logging.info("Starting SignalWire vCon processing script in DEBUG MODE")
    else:
        logging.info("Starting SignalWire vCon processing script")

    while running:
        current_time = datetime.now(UTC)
        logging.info(f"Checking for new recordings since {last_check_time}")

        try:
            process_recordings(last_check_time)
        except Exception as e:
            logging.error(f"Error in main loop: {str(e)}")

        last_check_time = current_time

        # Check if we should continue running before sleeping
        if running:
            logging.info(f"Sleeping for {POLL_INTERVAL} seconds")
            # Sleep in small intervals to allow for quicker shutdown
            for _ in range(POLL_INTERVAL):
                if not running:
                    break
                time.sleep(1)

    logging.info("SignalWire vCon processing script has shut down")

if __name__ == "__main__":
    main()