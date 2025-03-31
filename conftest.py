import pytest
import os
from unittest.mock import patch

@pytest.fixture(autouse=True)
def reset_global_state():
    """
    Reset the global state of the signalwire_adapter module before each test.
    This prevents tests from interfering with each other.
    """
    # This fixture will automatically run before each test
    yield
    # After the test completes, we reset the global running flag
    # to ensure it doesn't affect subsequent tests
    import signalwire_adapter
    signalwire_adapter.running = True 