"""
Tests for CLI entry points.
"""

import os
import pytest
from hfm_download.cli import main, create_parser, EXAMPLE_CONFIG


class TestCliHelp:
    """Test --help output."""
    
    def test_help_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            create_parser().parse_args(['--help'])
        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert 'hfm-download' in output
    
    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            create_parser().parse_args(['--version'])
        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert 'hfm-download' in output
    
    def test_example_config_flag(self, capsys):
        exit_code = main(['--example-config'])
        assert exit_code == 0
        output = capsys.readouterr().out
        assert 'downloads:' in output
        assert 'mkdir -p' in output


class TestCliDefaults:
    """Test CLI default behavior."""
    
    def test_missing_config_file(self, tmpdir, capsys):
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            exit_code = main(['--config', 'nonexistent.yaml'])
            assert exit_code == 3
            output = capsys.readouterr().err
            assert 'not found' in output.lower()
        finally:
            os.chdir(old_cwd)


class TestExampleConfigContent:
    """Test that EXAMPLE_CONFIG contains expected elements."""
    
    def test_has_downloads_key(self):
        assert 'downloads:' in EXAMPLE_CONFIG
    
    def test_has_dot_case(self):
        assert '"."' in EXAMPLE_CONFIG or "'.'" in EXAMPLE_CONFIG
    
    def test_has_multi_level_case(self):
        assert 'models/bert' in EXAMPLE_CONFIG
    
    def test_has_nested_dict_rejection_comment(self):
        assert 'NO NESTED DICTS' in EXAMPLE_CONFIG
    
    def test_has_mkdir_hint(self):
        assert 'mkdir -p' in EXAMPLE_CONFIG
    
    def test_example_has_bert_url(self):
        assert 'google-bert' in EXAMPLE_CONFIG
