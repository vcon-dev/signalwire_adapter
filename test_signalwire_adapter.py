import os
import pytest
import json
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock, mock_open
import email.utils
import requests
from botocore.exceptions import ClientError
from vcon import Vcon
from pathlib import Path

# Import the module to test
import signalwire_adapter

# Test fixtures
@pytest.fixture
def mock_env_setup():
    """Set up environment variables for testing"""
    os.environ['SIGNALWIRE_PROJECT_ID'] = 'test_project_id'
    os.environ['SIGNALWIRE_AUTH_TOKEN'] = 'test_auth_token'
    os.environ['SIGNALWIRE_SPACE_URL'] = 'https://test.signalwire.com'
    os.environ['WEBHOOK_URL'] = 'https://test.webhook.com'
    os.environ['DEBUG_MODE'] = 'false'
    os.environ['POLL_INTERVAL'] = '300'

@pytest.fixture
def mock_recording():
    """Return a mock recording object"""
    return {
        'sid': 'RE123456789',
        'account_sid': 'AC123456789',
        'call_sid': 'CA123456789',
        'duration': '60',
        'channels': 2,
        'uri': '/api/laml/2010-04-01/Accounts/AC123456789/Recordings/RE123456789.json',
        'date_created': email.utils.formatdate(),
        'subresource_uris': {
            'transcriptions': '/api/laml/2010-04-01/Accounts/AC123456789/Recordings/RE123456789/Transcriptions.json'
        }
    }

@pytest.fixture
def mock_call_meta():
    """Return a mock call metadata"""
    return {
        'sid': 'CA123456789',
        'to_formatted': '+15551234567',
        'from_formatted': '+15557654321',
        'duration': '60',
        'status': 'completed'
    }

@pytest.fixture
def mock_transcription():
    """Return a mock transcription"""
    return {
        'transcriptions': [
            {
                'sid': 'TR123456789',
                'text': 'This is a sample transcription.'
            }
        ]
    }

# Tests
def test_fetch_call_meta(mock_env_setup):
    with patch('requests.request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'sid': 'CA123456789',
            'to_formatted': '+15551234567',
            'from_formatted': '+15557654321',
            'duration': '60'
        }
        mock_request.return_value = mock_response
        
        result = signalwire_adapter.fetch_call_meta('CA123456789')
        
        mock_request.assert_called_once()
        assert result['sid'] == 'CA123456789'
        assert result['to_formatted'] == '+15551234567'
        assert result['from_formatted'] == '+15557654321'

def test_fetch_new_recordings(mock_env_setup):
    with patch('requests.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'recordings': [
                {
                    'sid': 'RE123456789',
                    'call_sid': 'CA123456789'
                }
            ]
        }
        mock_request.return_value = mock_response
        
        last_check_time = datetime.now(UTC) - timedelta(minutes=5)
        result = signalwire_adapter.fetch_new_recordings(last_check_time)
        
        mock_request.assert_called_once()
        assert len(result) == 1
        assert result[0]['sid'] == 'RE123456789'

def test_fetch_new_recordings_failure(mock_env_setup):
    with patch('requests.request') as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response
        
        last_check_time = datetime.now(UTC) - timedelta(minutes=5)
        
        with pytest.raises(Exception) as excinfo:
            signalwire_adapter.fetch_new_recordings(last_check_time)
        
        assert "Failed to fetch recordings" in str(excinfo.value)

def test_fetch_transcription(mock_env_setup):
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'transcriptions': [
                {
                    'sid': 'TR123456789',
                    'text': 'This is a sample transcription.'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        result = signalwire_adapter.fetch_transcription('/api/path/to/transcription')
        
        mock_get.assert_called_once()
        assert 'transcriptions' in result
        assert result['transcriptions'][0]['text'] == 'This is a sample transcription.'

def test_fetch_transcription_failure(mock_env_setup):
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception) as excinfo:
            signalwire_adapter.fetch_transcription('/api/path/to/transcription')
        
        assert "Failed to fetch transcription" in str(excinfo.value)

def test_format_to_e164():
    """Test the E.164 phone number formatting function"""
    # Test with various phone number formats
    assert signalwire_adapter.format_to_e164('+15551234567') == '+15551234567'
    assert signalwire_adapter.format_to_e164('15551234567') == '+15551234567'
    assert signalwire_adapter.format_to_e164('(555) 123-4567') == '+5551234567'
    assert signalwire_adapter.format_to_e164('555.123.4567') == '+5551234567'
    assert signalwire_adapter.format_to_e164('+1 (555) 123-4567') == '+15551234567'
    assert signalwire_adapter.format_to_e164('1-555-123-4567') == '+15551234567'

def test_create_vcon_from_recordings(mock_env_setup, mock_recording, mock_call_meta, mock_transcription):
    with patch('signalwire_adapter.fetch_transcription') as mock_fetch_transcription:
        # Set up mocks
        mock_fetch_transcription.return_value = mock_transcription
        
        # Call function with a list of recordings
        recordings = [mock_recording]
        result = signalwire_adapter.create_vcon_from_recordings(recordings, mock_call_meta)
        
        # Validate result
        assert isinstance(result, Vcon)
        assert len(result.parties) == 2
        
        # Check if the parties have the correct phone numbers in E.164 format
        assert result.parties[0].tel == '+15551234567'
        assert result.parties[1].tel == '+15557654321'

def test_create_vcon_from_recording(mock_env_setup, mock_recording, mock_call_meta, mock_transcription):
    with patch('signalwire_adapter.fetch_call_meta') as mock_fetch_call_meta, \
         patch('signalwire_adapter.fetch_transcription') as mock_fetch_transcription:
        
        # Set up mocks
        mock_fetch_call_meta.return_value = mock_call_meta
        mock_fetch_transcription.return_value = mock_transcription
        
        # Call function
        recordings = [mock_recording]
        result = signalwire_adapter.create_vcon_from_recordings(recordings, mock_call_meta)
        
        # Validate result
        assert isinstance(result, Vcon)
        assert len(result.parties) == 2
        assert len(result.dialog) == 1  # Because we're passing a single recording
        assert len(result.attachments) >= 1  # At least one for metadata
        
        # Check if the parties have the correct phone numbers
        assert result.parties[0].tel == '+15551234567'
        assert result.parties[1].tel == '+15557654321'
        
        # If there's a transcription attachment, check its text
        transcription_attachments = [a for a in result.attachments if a['type'] == 'transcription']
        if transcription_attachments:
            assert transcription_attachments[0]['body']['text'] == 'This is a sample transcription.'

def test_write_vcon_to_file(mock_env_setup):
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('pathlib.Path.mkdir'):
        
        # Create a mock vCon
        vcon = MagicMock()
        vcon.uuid = 'test-uuid'
        vcon.to_json.return_value = '{"uuid": "test-uuid"}'
        
        # Call function with call_sid
        call_sid = 'CA123456789'
        signalwire_adapter.DEBUG_DIR = 'test_debug_dir'
        signalwire_adapter.write_vcon_to_file(vcon, call_sid)
        
        # Verify file was written to
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with('{"uuid": "test-uuid"}')

def test_send_vcon_to_webhook_debug_mode(mock_env_setup):
    with patch('signalwire_adapter.DEBUG_MODE', True), \
         patch('signalwire_adapter.write_vcon_to_file') as mock_write:
        
        vcon = MagicMock()
        call_sid = 'CA123456789'
        signalwire_adapter.send_vcon_to_webhook(vcon, call_sid)
        
        # Verify write_vcon_to_file was called with both parameters
        mock_write.assert_called_once_with(vcon, call_sid)

def test_send_vcon_to_webhook_normal_mode(mock_env_setup):
    with patch('signalwire_adapter.DEBUG_MODE', False), \
         patch('requests.post') as mock_post:
        
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        vcon = MagicMock()
        vcon.to_json.return_value = '{"uuid": "test-uuid"}'
        vcon.uuid = 'test-uuid'
        call_sid = 'CA123456789'
        
        signalwire_adapter.WEBHOOK_URL = 'https://test.webhook.com'
        signalwire_adapter.send_vcon_to_webhook(vcon, call_sid)
        
        # Verify post was called with correct parameters
        mock_post.assert_called_once_with(
            'https://test.webhook.com',
            headers={'Content-Type': 'application/json'},
            data='{"uuid": "test-uuid"}',
            timeout=10
        )

def test_send_vcon_to_webhook_failure(mock_env_setup):
    with patch('signalwire_adapter.DEBUG_MODE', False), \
         patch('requests.post') as mock_post, \
         patch('logging.error') as mock_log_error:
        
        # Make post request fail
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")
        
        vcon = MagicMock()
        vcon.to_json.return_value = '{"uuid": "test-uuid"}'
        vcon.uuid = 'test-uuid'
        call_sid = 'CA123456789'
        
        signalwire_adapter.WEBHOOK_URL = 'https://test.webhook.com'
        signalwire_adapter.send_vcon_to_webhook(vcon, call_sid)
        
        # Verify error was logged
        mock_log_error.assert_called_once()
        assert "Failed to send vCon to webhook" in mock_log_error.call_args[0][0]

def test_process_recordings(mock_env_setup, mock_recording, mock_call_meta):
    with patch('signalwire_adapter.fetch_new_recordings') as mock_fetch, \
         patch('signalwire_adapter.fetch_call_meta') as mock_fetch_call_meta, \
         patch('signalwire_adapter.create_vcon_from_recordings') as mock_create, \
         patch('signalwire_adapter.send_vcon_to_webhook') as mock_send, \
         patch('signalwire_adapter.load_processed_calls') as mock_load, \
         patch('signalwire_adapter.save_processed_calls') as mock_save, \
         patch('signalwire_adapter.cleanup_old_call_records', return_value={}):
        
        # Set up mocks
        mock_fetch.return_value = [mock_recording]
        mock_fetch_call_meta.return_value = mock_call_meta
        mock_vcon = MagicMock()
        mock_create.return_value = mock_vcon
        mock_load.return_value = {}  # No processed calls
        
        last_check_time = datetime.now(UTC) - timedelta(minutes=5)
        signalwire_adapter.process_recordings(last_check_time)
        
        mock_fetch.assert_called_once_with(last_check_time)
        mock_create.assert_called_once()
        mock_send.assert_called_once_with(mock_vcon, mock_recording['call_sid'])

def test_process_recordings_with_error(mock_env_setup, mock_recording, mock_call_meta):
    with patch('signalwire_adapter.fetch_new_recordings') as mock_fetch, \
         patch('signalwire_adapter.fetch_call_meta') as mock_fetch_call_meta, \
         patch('signalwire_adapter.create_vcon_from_recordings') as mock_create, \
         patch('logging.error') as mock_log, \
         patch('signalwire_adapter.load_processed_calls', return_value={}), \
         patch('signalwire_adapter.save_processed_calls'), \
         patch('signalwire_adapter.cleanup_old_call_records', return_value={}):
        
        # Set up mocks
        mock_fetch.return_value = [mock_recording]
        mock_fetch_call_meta.return_value = mock_call_meta
        mock_create.side_effect = Exception("Test error")
        
        last_check_time = datetime.now(UTC) - timedelta(minutes=5)
        signalwire_adapter.process_recordings(last_check_time)
        
        mock_fetch.assert_called_once_with(last_check_time)
        mock_create.assert_called_once()
        mock_log.assert_called_once()

def test_main_function_normal_exit(mock_env_setup):
    with patch('signalwire_adapter.process_recordings') as mock_process, \
         patch('time.sleep', side_effect=lambda x: None), \
         patch('logging.info') as mock_log_info:
        
        # Set up the running flag to stop after one iteration
        signalwire_adapter.running = True
        
        def stop_after_one_loop(*args, **kwargs):
            signalwire_adapter.running = False
            
        mock_process.side_effect = stop_after_one_loop
        
        # Call main function
        signalwire_adapter.main()
        
        # Verify process_recordings was called once and app shut down gracefully
        mock_process.assert_called_once()
        shutdown_message_logged = False
        for call in mock_log_info.call_args_list:
            if "SignalWire vCon processing script has shut down" in call[0][0]:
                shutdown_message_logged = True
                break
        assert shutdown_message_logged

def test_main_function_with_process_error(mock_env_setup):
    with patch('signalwire_adapter.process_recordings') as mock_process, \
         patch('time.sleep', side_effect=lambda x: None), \
         patch('logging.error') as mock_log_error:
        
        # Set up the running flag to stop after one iteration
        signalwire_adapter.running = True
        
        def stop_with_error(*args, **kwargs):
            signalwire_adapter.running = False
            raise Exception("Test process error")
            
        mock_process.side_effect = stop_with_error
        
        # Call main function
        signalwire_adapter.main()
        
        # Verify error was logged
        mock_log_error.assert_called_once()
        assert "Error in main loop" in mock_log_error.call_args[0][0]

def test_upload_recording_to_s3_presigned_url():
    """upload_recording_to_s3 uploads privately and returns a presigned URL"""
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = 'https://presigned-url.example.com/rec'

    with patch('signalwire_adapter.boto3') as mock_boto3, \
         patch('signalwire_adapter.S3_BUCKET', 'my-bucket'), \
         patch('signalwire_adapter.S3_KEY_PREFIX', 'recordings/'), \
         patch('signalwire_adapter.S3_PRESIGN_EXPIRY', 604800):
        mock_boto3.client.return_value = mock_s3

        url = signalwire_adapter.upload_recording_to_s3(b'audio-data', 'RE456')

        mock_s3.put_object.assert_called_once_with(
            Bucket='my-bucket',
            Key='recordings/RE456.mp3',
            Body=b'audio-data',
            ContentType='audio/mpeg',
        )
        mock_s3.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': 'my-bucket', 'Key': 'recordings/RE456.mp3'},
            ExpiresIn=604800,
        )
        assert url == 'https://presigned-url.example.com/rec'


def test_upload_recording_to_s3_raises_on_client_error():
    """upload_recording_to_s3 raises Exception when S3 returns a ClientError"""
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError(
        {'Error': {'Code': 'NoSuchBucket', 'Message': 'The bucket does not exist'}},
        'PutObject',
    )

    with patch('signalwire_adapter.boto3') as mock_boto3, \
         patch('signalwire_adapter.S3_BUCKET', 'missing-bucket'), \
         patch('signalwire_adapter.S3_KEY_PREFIX', 'recordings/'), \
         patch('signalwire_adapter.S3_PRESIGN_EXPIRY', 604800):
        mock_boto3.client.return_value = mock_s3

        with pytest.raises(Exception, match="Failed to upload recording"):
            signalwire_adapter.upload_recording_to_s3(b'audio-data', 'RE789')


def test_create_vcon_from_recordings_uses_s3_when_enabled(
    mock_env_setup, mock_recording, mock_call_meta, mock_transcription
):
    """When S3_ENABLED=True, create_vcon_from_recordings downloads and re-hosts the recording"""
    with patch('signalwire_adapter.fetch_transcription', return_value=mock_transcription), \
         patch('signalwire_adapter.S3_ENABLED', True), \
         patch('signalwire_adapter.download_recording', return_value=b'mp3-bytes') as mock_dl, \
         patch('signalwire_adapter.upload_recording_to_s3', return_value='https://s3.example.com/rec.mp3') as mock_ul:

        result = signalwire_adapter.create_vcon_from_recordings([mock_recording], mock_call_meta)

        mock_dl.assert_called_once()
        mock_ul.assert_called_once_with(b'mp3-bytes', mock_recording['sid'])
        assert result.dialog[0]['url'] == 'https://s3.example.com/rec.mp3'


def test_create_vcon_from_recordings_skips_s3_when_disabled(
    mock_env_setup, mock_recording, mock_call_meta, mock_transcription
):
    """When S3_ENABLED=False, the original SignalWire URL is used unchanged"""
    with patch('signalwire_adapter.fetch_transcription', return_value=mock_transcription), \
         patch('signalwire_adapter.S3_ENABLED', False), \
         patch('signalwire_adapter.download_recording') as mock_dl, \
         patch('signalwire_adapter.upload_recording_to_s3') as mock_ul:

        result = signalwire_adapter.create_vcon_from_recordings([mock_recording], mock_call_meta)

        mock_dl.assert_not_called()
        mock_ul.assert_not_called()
        assert 'signalwire.com' in result.dialog[0]['url']


if __name__ == "__main__":
    pytest.main()