import os
import json
import unittest
import requests

BASE_URL = os.getenv('PAPERLESS_AI_URL', 'http://127.0.0.1:5001')

class DashboardTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Skip tests if service is not running
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code != 200:
                raise unittest.SkipTest("Service not healthy")
        except Exception:
            raise unittest.SkipTest("Service not running")

    def test_pages(self):
        for path in ("/dashboard", "/dashboard/review", "/dashboard/history", "/dashboard/suggestions"):
            r = requests.get(f"{BASE_URL}{path}", timeout=5)
            self.assertEqual(r.status_code, 200)

    def test_action_ignorer(self):
        payload = {
            'document_id': '999999',
            'action': 'ignorer',
            'doc_type': 'test'
        }
        r = requests.post(f"{BASE_URL}/dashboard/action", data=payload, timeout=5, allow_redirects=False)
        self.assertIn(r.status_code, (302, 303))

    def test_api_history(self):
        r = requests.get(f"{BASE_URL}/api/history", timeout=5)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('actions', data)
        self.assertIsInstance(data['actions'], list)

if __name__ == '__main__':
    unittest.main()
