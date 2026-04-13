"""
Tests for URL parsing and mirror replacement.
"""

import pytest
from hfm_download.config import extract_mirror_url, parse_hf_url, validate_hf_url


class TestValidateHfUrl:
    """Test HF URL validation."""
    
    def test_valid_huggingface_co(self):
        assert validate_hf_url('https://huggingface.co/bert-base/resolve/main/model.bin')
    
    def test_valid_hf_mirror(self):
        assert validate_hf_url('https://hf-mirror.com/bert-base/resolve/main/model.bin')
    
    def test_valid_http(self):
        assert validate_hf_url('http://huggingface.co/bert-base/resolve/main/model.bin')
    
    def test_invalid_random_url(self):
        assert not validate_hf_url('https://example.com/model.bin')
    
    def test_invalid_github(self):
        assert not validate_hf_url('https://github.com/bert-base/model.bin')
    
    def test_empty_string(self):
        assert not validate_hf_url('')
    
    def test_whitespace_stripped(self):
        assert validate_hf_url('  https://huggingface.co/bert-base/resolve/main/model.bin  ')


class TestExtractMirrorUrl:
    """Test mirror URL replacement."""
    
    def test_basic_replacement(self):
        url = 'https://huggingface.co/bert-base/resolve/main/model.bin'
        expected = 'https://hf-mirror.com/bert-base/resolve/main/model.bin'
        assert extract_mirror_url(url) == expected
    
    def test_google_bert_model(self):
        url = 'https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors'
        expected = 'https://hf-mirror.com/google-bert/bert-base-uncased/blob/main/model.safetensors'
        assert extract_mirror_url(url) == expected
    
    def test_already_mirror(self):
        url = 'https://hf-mirror.com/bert-base/resolve/main/model.bin'
        assert extract_mirror_url(url) == url  # no change
    
    def test_http_to_hf_mirror(self):
        url = 'http://huggingface.co/bert-base/resolve/main/model.bin'
        expected = 'https://hf-mirror.com/bert-base/resolve/main/model.bin'
        assert extract_mirror_url(url) == expected


class TestParseHfUrl:
    """Test HuggingFace URL parsing into (model_id, filename)."""
    
    def test_resolve_format(self):
        url = 'https://huggingface.co/bert-base/resolve/main/model.bin'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'bert-base'
        assert filename == 'model.bin'
    
    def test_blob_format(self):
        url = 'https://huggingface.co/google-bert/bert-base-uncased/blob/main/model.safetensors'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'google-bert'
        assert filename == 'model.safetensors'
    
    def test_blob_format_multi_level(self):
        url = 'https://huggingface.co/datasets/stanfordnlp/imdb/blob/main/plain_text/train-00000-of-00001.parquet'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'datasets'
        assert filename == 'train-00000-of-00001.parquet'
    
    def test_resolve_with_version(self):
        url = 'https://huggingface.co/meta-llama/Llama-2-7b/resolve/v1/model.bin'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'meta-llama'
        assert filename == 'model.bin'
    
    def test_mixed_hyphen_model_id(self):
        url = 'https://huggingface.co/openai-community/gpt2/resolve/main/model.bin'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'openai-community'
        assert filename == 'model.bin'
    
    def test_invalid_url_no_resolve_or_blob(self):
        from hfm_download.exceptions import ConfigValidationError
        url = 'https://huggingface.co/bert-base/model.bin'
        with pytest.raises(ConfigValidationError, match='Invalid HuggingFace URL format'):
            parse_hf_url(url)
    
    def test_invalid_url_no_model_id(self):
        from hfm_download.exceptions import ConfigValidationError
        url = 'https://huggingface.co/resolve/main/model.bin'
        with pytest.raises(ConfigValidationError, match='Model ID is missing'):
            parse_hf_url(url)
    
    def test_mirror_url_parsed_correctly(self):
        url = 'https://hf-mirror.com/google-bert/bert-base-uncased/blob/main/model.safetensors'
        model_id, filename = parse_hf_url(url)
        assert model_id == 'google-bert'
        assert filename == 'model.safetensors'
