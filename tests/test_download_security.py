"""Regression tests for public source URL and destination restrictions."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'repro/m3'))
from fetch_public import public_target,validate_download_url,SeoulRedirectHandler


class DownloadSecurityTests(unittest.TestCase):
    def test_only_official_https_downloads_are_accepted(self):
        self.assertEqual(validate_download_url('https://datafile.seoul.go.kr/file'),
                         'https://datafile.seoul.go.kr/file')
        for url in ['file:///etc/passwd','http://datafile.seoul.go.kr/file',
                    'https://datafile.seoul.go.kr.evil.example/file',
                    'https://user:password@datafile.seoul.go.kr/file',
                    'https://datafile.seoul.go.kr:8443/file']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                validate_download_url(url)

    def test_relative_paths_cannot_escape_the_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(public_target(root,{'path':'public/source.xlsx'}),root/'public/source.xlsx')
            for path in ['../outside.xlsx',str(root.parent/'outside.xlsx'),'.']:
                with self.subTest(path=path),self.assertRaises(ValueError):
                    public_target(root,{'path':path})

    def test_redirects_cannot_leave_the_official_host(self):
        with self.assertRaises(ValueError):
            SeoulRedirectHandler().redirect_request(None,None,302,'',{},'https://example.com/file')
