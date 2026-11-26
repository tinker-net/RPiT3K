"""Offline regression tests: fake credentials only; never contacts TONE3000."""
import json
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from io import BytesIO
from email.message import Message
from tonecloud import ToneCloud

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.controller=SimpleNamespace(data=Path(self.tmp.name))
    def new(self):
        c=ToneCloud(self.controller)
        c.fetch=Mock(side_effect=AssertionError("unexpected network call"))
        return c
    def saved(self,expires=3600,refresh="test-refresh"):
        c=self.new();c.client="test-publishable"
        c.store_tokens(dict(access_token="test-access",refresh_token=refresh,expires_in=expires))
        return c
    def test_restart_and_permissions(self):
        c=self.saved()
        self.assertEqual(stat.S_IMODE(c.tokenfile.stat().st_mode),0o600)
        self.assertNotIn("deadline",json.loads(c.tokenfile.read_text())["tokens"])
        d=self.new()
        self.assertEqual(d.client,c.client)
        self.assertEqual(d.action("status",{}),{"connected":True})
        self.assertEqual(d.token(),"test-access")
        d.fetch.assert_not_called()
    def test_refresh_rotation_persists(self):
        c=self.saved(0);d=self.new()
        d.fetch=Mock(return_value=dict(access_token="new-access",refresh_token="new-refresh",expires_in=3600))
        self.assertEqual(d.token(),"new-access")
        self.assertEqual(d.fetch.call_args.kwargs["form"]["refresh_token"],"test-refresh")
        e=self.new();self.assertEqual(e.token(),"new-access")
        self.assertEqual(e.tokens["refresh_token"],"new-refresh")
    def test_refresh_without_rotation(self):
        self.saved(0);d=self.new()
        d.fetch=Mock(return_value=dict(access_token="new-access",expires_in=3600))
        d.token();self.assertEqual(self.new().tokens["refresh_token"],"test-refresh")
    def test_disconnect(self):
        c=self.saved();c.action("disconnect",{})
        self.assertFalse(c.tokenfile.exists());self.assertFalse(self.new().action("status",{})["connected"])
    def test_invalid_grant(self):
        c=self.saved(0);c.fetch=Mock(return_value={"error":"invalid_grant"})
        with self.assertRaises(ValueError):c.token()
        self.assertFalse(c.tokenfile.exists())
    def test_network_failure_keeps_session(self):
        c=self.saved(0);c.fetch=Mock(side_effect=ValueError("network unavailable"))
        with self.assertRaises(ValueError):c.token()
        self.assertTrue(c.tokenfile.exists());self.assertTrue(self.new().action("status",{})["connected"])
    def test_corrupt_file(self):
        c=self.new();c.tokenfile.write_text("{bad")
        self.assertFalse(self.new().action("status",{})["connected"])
    def test_expired_without_refresh(self):
        c=self.saved(0,None)
        with self.assertRaises(ValueError):c.token()
        self.assertFalse(c.tokenfile.exists())

class DownloadTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.c=ToneCloud(SimpleNamespace(data=Path(tmp.name)))
        self.c.http=Mock()
        self.url="https://www.tone3000.com/api/v1/models/1/download"
    def redirect(self,location):
        headers=Message();headers["Location"]=location
        return HTTPError(self.url,302,"Found",headers,BytesIO())
    def response(self,content=b"model"):
        return BytesIO(content)
    def test_same_host(self):
        self.c.http.open.side_effect=[self.redirect("/download/file"),self.response()]
        self.assertEqual(self.c.fetch(self.url,token="fake",binary=True),b"model")
        self.assertEqual(self.c.http.open.call_args.args[0].get_header("Authorization"),"Bearer fake")
    @patch("tonecloud.socket.getaddrinfo",return_value=[(2,1,6,"",("8.8.8.8",443))])
    def test_external_no_bearer(self,_):
        self.c.http.open.side_effect=[self.redirect("https://cdn.example.com/signed"),self.response()]
        self.assertEqual(self.c.fetch(self.url,token="fake",binary=True),b"model")
        self.assertIsNone(self.c.http.open.call_args.args[0].get_header("Authorization"))
    def test_binary_download_headers_on_redirect(self):
        self.c.http.open.side_effect=[self.redirect("https://files.tone3000.com/model"),self.response()]
        self.assertEqual(self.c.fetch(self.url,token="fake",binary=True),b"model")
        for call in self.c.http.open.call_args_list:
            req=call.args[0]
            self.assertEqual(req.get_header("User-agent"),"Mozilla/5.0")
            self.assertEqual(req.get_header("Accept"),"*/*")
            self.assertEqual(req.get_header("Authorization"),"Bearer fake")
    def test_official_file_origin_keeps_bearer(self):
        self.c.http.open.side_effect=[self.redirect("https://files.tone3000.com/model"),self.response()]
        self.assertEqual(self.c.fetch(self.url,token="fake",binary=True),b"model")
        self.assertEqual(self.c.http.open.call_args.args[0].get_header("Authorization"),"Bearer fake")
    @patch("tonecloud.socket.getaddrinfo",return_value=[(2,1,6,"",("8.8.8.8",443))])
    def test_bearer_not_restored_after_external_hop(self,_):
        self.c.http.open.side_effect=[self.redirect("https://cdn.example.com/signed"),self.redirect("https://files.tone3000.com/model"),self.response()]
        self.assertEqual(self.c.fetch(self.url,token="fake",binary=True),b"model")
        self.assertIsNone(self.c.http.open.call_args.args[0].get_header("Authorization"))
    def test_http_blocked(self):
        self.c.http.open.side_effect=self.redirect("http://www.tone3000.com/file")
        with self.assertRaisesRegex(ValueError,"Unsafe"):self.c.fetch(self.url,token="fake",binary=True)
    @patch("tonecloud.socket.getaddrinfo",return_value=[(2,1,6,"",("127.0.0.1",443))])
    def test_private_host_blocked(self,_):
        self.c.http.open.side_effect=self.redirect("https://localhost/file")
        with self.assertRaisesRegex(ValueError,"Unsafe"):self.c.fetch(self.url,token="fake",binary=True)
    def test_api_redirect_rejected(self):
        self.c.http.open.side_effect=self.redirect("/other")
        with self.assertRaisesRegex(ValueError,"302"):self.c.fetch(self.url,token="fake")
    def test_redirect_limit(self):
        self.c.http.open.side_effect=[self.redirect("/loop") for _ in range(6)]
        with self.assertRaisesRegex(ValueError,"limit"):self.c.fetch(self.url,token="fake",binary=True)

if __name__=="__main__":unittest.main(verbosity=2)
