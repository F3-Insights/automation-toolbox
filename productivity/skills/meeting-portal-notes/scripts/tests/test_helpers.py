"""Offline regression tests for evidence integrity and read-only API handling."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

from check_evidence import check  # noqa: E402
from portal_read import unwrap  # noqa: E402
from prepare_transcript import prepare  # noqa: E402

PORTAL_READ = SCRIPTS / 'portal_read.py'
TOKEN = 's3cret-portal-token'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = prepare('Mara: Could you send it Friday?\nOwen: I will send it Monday, September 14.\n')
        self.actions = [{'id': 'a1', 'actor': 'Owen', 'action': 'Send it', 'status': 'accepted',
                         'due_date': '2026-09-14', 'evidence': [{'turn': 'T0002', 'quote': 'I will send it Monday, September 14.'}]}]

    def test_full_evidence_and_correction_reference_pass(self):
        self.assertEqual([], check(self.source, self.actions))

    def test_real_quote_at_wrong_turn_fails(self):
        self.actions[0]['evidence'][0]['turn'] = 'T0001'
        self.assertTrue(check(self.source, self.actions))

    def test_spliced_or_paraphrased_quote_fails(self):
        self.actions[0]['evidence'][0]['quote'] = 'I will send it Friday.'
        self.assertTrue(check(self.source, self.actions))

    def test_tampered_turn_map_fails_even_if_quote_matches_it(self):
        self.source['turns'][1]['text'] = 'Owen: I will send it Friday.'
        self.actions[0]['evidence'][0]['quote'] = 'I will send it Friday.'
        self.assertTrue(check(self.source, self.actions))

    def test_long_source_retains_closing_commitment(self):
        text = 'Background. ' * 10000 + '\nOwen: I will send it Monday.'
        self.assertEqual(text, prepare(text)['transcript'])
        self.assertEqual(2, len(prepare(text)['turns']))

    def test_malformed_project_reference_fails_receipt_check(self):
        self.actions[0]['project_ref'] = 'portal://project/incorrect-id'
        self.assertTrue(check(self.source, self.actions, {'portal://project/correct-id'}))



class TransportTests(unittest.TestCase):
    def test_json_and_sse_keep_empty_and_full_results(self):
        for result in [{}, {'tasks': [], 'next_offset': None}, {'text': 'x' * 100000}]:
            raw = json.dumps({'result': {'structuredContent': result}})
            self.assertEqual(result, unwrap(raw))
            self.assertEqual(result, unwrap('event: message\ndata: '+raw+'\n\n'))

    def test_tool_error_is_not_an_empty_success(self):
        with self.assertRaises(ValueError):
            unwrap(json.dumps({'result': {'isError': True, 'content': []}}))

    def test_write_tool_rejected_before_config_or_network(self):
        run = subprocess.run([sys.executable, str(PORTAL_READ),
                              'create_task', '--args', '/missing', '--output', '/missing'],
                             capture_output=True, text=True)
        self.assertEqual(2, run.returncode)
        self.assertIn('invalid choice', run.stderr)


def serve(handler):
    httpd = HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class SettingsClientTests(unittest.TestCase):
    """The Portal is found from the owner settings, not from another repository."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / 'args.json').write_text('{"query": "x"}')

    def run_read(self, url, header='Bearer ${TEST_PORTAL_TOKEN}', extra=()):
        cfg = self.dir / 'mcp.json'
        cfg.write_text(json.dumps({'mcpServers': {'insights-portal': {
            'url': url, 'headers': {'Authorization': header}}}}))
        settings = self.dir / 'settings.toml'
        settings.write_text(f'portal_mcp_config = "{cfg}"\n')
        env = {k: v for k, v in os.environ.items() if k != 'INSIGHTS_PORTAL_ASSISTANT_TOKEN'}
        env.update(F3I_TOOLBOX_SETTINGS=str(settings), TEST_PORTAL_TOKEN=TOKEN)
        out = self.dir / 'receipt.json'
        if out.exists():
            out.unlink()
        run = subprocess.run([sys.executable, str(PORTAL_READ), 'search', '--args', str(self.dir / 'args.json'),
                              '--output', str(out), *extra], capture_output=True, text=True, env=env)
        return run, out

    def test_reads_through_the_settings_endpoint_with_the_config_bearer(self):
        seen = []

        class Portal(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.headers.get('Authorization'),
                             json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body = json.dumps({'result': {'structuredContent': {'items': [1]}}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        httpd = serve(Portal)
        try:
            run, out = self.run_read(f'http://127.0.0.1:{httpd.server_port}/mcp')
        finally:
            httpd.shutdown()
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual({'items': [1]}, json.loads(out.read_text())['result'])
        self.assertEqual('Bearer ' + TOKEN, seen[0][0])
        self.assertEqual('search', seen[0][1]['params']['name'])
        self.assertNotIn(TOKEN, run.stdout + run.stderr)

    def test_a_redirect_is_refused_and_the_token_goes_nowhere_else(self):
        hits = []

        class Elsewhere(BaseHTTPRequestHandler):
            def do_POST(self):
                hits.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        other = serve(Elsewhere)

        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307)
                self.send_header('Location', f'http://127.0.0.1:{other.server_port}/mcp')
                self.end_headers()

            def log_message(self, *a):
                pass

        httpd = serve(Redirect)
        try:
            run, out = self.run_read(f'http://127.0.0.1:{httpd.server_port}/mcp')
        finally:
            httpd.shutdown()
            other.shutdown()
        self.assertEqual(1, run.returncode)
        self.assertEqual([], hits)
        self.assertFalse(out.exists())
        self.assertNotIn(TOKEN, run.stdout + run.stderr)

    def test_plain_http_is_refused_except_to_localhost(self):
        run, out = self.run_read('http://portal.example.com/mcp')
        self.assertEqual(1, run.returncode)
        self.assertIn('HTTPS', run.stderr)
        self.assertNotIn(TOKEN, run.stdout + run.stderr)
        self.assertFalse(out.exists())

    def test_missing_variable_in_the_header_is_named_not_printed(self):
        run, _ = self.run_read('https://portal.example.com/mcp', header='Bearer ${NOT_SET_ANYWHERE}')
        self.assertEqual(1, run.returncode)
        self.assertIn('NOT_SET_ANYWHERE', run.stderr)

    def test_assistant_root_is_gone(self):
        run, _ = self.run_read('https://portal.example.com/mcp', extra=('--assistant-root', '/tmp'))
        self.assertEqual(2, run.returncode)
        self.assertIn('unrecognized arguments', run.stderr)


if __name__ == '__main__':
    unittest.main()
