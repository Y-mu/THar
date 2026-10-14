from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from langHar.bootstrap import create_http_app


class StudioConnectionTests(unittest.TestCase):
    def make_app(self, *, local_dev=True):
        environment = {
            "LANGGRAPH_HTTP": json.dumps({"cors": {
                "allow_origins": ["https://smith.langchain.com"],
                "allow_methods": ["GET", "POST"],
                "allow_headers": ["Content-Type", "X-Api-Key", "X-Auth-Scheme", "X-Mda-Channel", "X-Tenant-Id"],
            }}),
            "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev" if local_dev else "self-hosted",
            "ALLOW_PRIVATE_NETWORK": "true",
        }
        with patch.dict("os.environ", environment, clear=True):
            app = create_http_app()
        return app

    def preflight(self, app, **changes):
        return TestClient(app).options("/assistants/search", headers={
            "Origin": "https://smith.langchain.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key,x-auth-scheme,x-mda-channel,x-tenant-id",
            "Access-Control-Request-Private-Network": "true",
            **changes,
        })

    def test_local_studio_private_network_preflight_succeeds(self):
        response = self.preflight(self.make_app())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://smith.langchain.com")
        self.assertEqual(response.headers["access-control-allow-private-network"], "true")

    def test_untrusted_origin_or_header_is_rejected(self):
        app = self.make_app()
        for changes in (
            {"Origin": "https://untrusted.example"},
            {"Access-Control-Request-Headers": "x-unregistered"},
        ):
            response = self.preflight(app, **changes)
            self.assertEqual(response.status_code, 400)

    def test_production_does_not_enable_private_network_access(self):
        response = self.preflight(self.make_app(local_dev=False))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-private-network", response.headers)


