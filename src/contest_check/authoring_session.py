# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Thread-safe ownership and cleanup of one browser session's temporary draft."""

import logging
import secrets
import threading

import httpx

LOGGER = logging.getLogger(__name__)


class AuthoringSession:
    def __init__(self, api_url, request, release_files=lambda: None):
        self.api_url = api_url
        self.request = request
        self.release_files = release_files
        self.lock = threading.RLock()
        self.closed = False
        self.workflow_id = None
        self.private_values = {}

    def create_id(self):
        with self.lock:
            if self.closed:
                raise ValueError("The browser session has ended.")
            self.workflow_id = secrets.token_hex(16)
            return self.workflow_id

    def remember(self, name, value):
        with self.lock:
            if self.closed:
                value.clear()
                raise ValueError("The browser session has ended.")
            self.private_values[name] = value
        return value

    def forget(self):
        with self.lock:
            self.workflow_id = None
            for value in self.private_values.values():
                value.clear()
            self.private_values.clear()
        self.release_files()

    def close(self):
        # Streamlit calls this without a script context, including during an HTTP request.
        with self.lock:
            self.closed = True
            workflow_id = self.workflow_id
            for value in self.private_values.values():
                value.clear()
            self.private_values.clear()
        self.release_files()
        if workflow_id is None:
            return True
        for _ in range(2):
            try:
                response = self.request(
                    self.api_url, "DELETE", f"/api/authoring/workflows/{workflow_id}"
                )
                if response.status_code in (204, 404):
                    with self.lock:
                        self.workflow_id = None
                    return True
            except (httpx.HTTPError, ValueError):
                pass
        LOGGER.warning("Temporary draft cleanup could not be confirmed by the local API.")
        return False
