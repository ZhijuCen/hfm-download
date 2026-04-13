"""
Tests for path safety validation.
"""

import os
import pytest
from pathlib import Path
from hfm_download.path_utils import validate_safe_path, validate_subdir_exists, build_dest_path
from hfm_download.exceptions import PathTraversalError


class TestValidateSafePath:
    """Test path safety validation."""
    
    def test_relative_path_within_cwd(self, tmpdir):
        result = validate_safe_path('subdir/file.txt', str(tmpdir))
        assert result == tmpdir / 'subdir' / 'file.txt'
    
    def test_dot_current_dir(self, tmpdir):
        result = validate_safe_path('.', str(tmpdir))
        assert result == tmpdir.resolve()
    
    def test_absolute_path_within_cwd(self, tmpdir):
        abs_path = tmpdir / 'models' / 'file.bin'
        result = validate_safe_path(str(abs_path), str(tmpdir))
        assert result == abs_path.resolve()
    
    def test_absolute_path_outside_cwd_blocked(self, tmpdir):
        with pytest.raises(PathTraversalError):
            validate_safe_path('/etc/passwd', str(tmpdir))
    
    def test_path_traversal_blocked_single_level(self, tmpdir):
        with pytest.raises(PathTraversalError):
            validate_safe_path('../etc/passwd', str(tmpdir))
    
    def test_path_traversal_blocked_multi_level(self, tmpdir):
        with pytest.raises(PathTraversalError):
            validate_safe_path('models/../../../etc/passwd', str(tmpdir))
    
    def test_path_traversal_blocked_deep(self, tmpdir):
        # /tmp/xxx/a/b/c/../../../etc -> /tmp/xxx/etc -> within tmpdir
        # Actually resolves to within tmpdir, so it passes. Need path that truly escapes.
        # Use a path that normalizes to parent of tmpdir
        with pytest.raises(PathTraversalError):
            validate_safe_path('..', str(tmpdir))
    
    def test_symlink_traversal_blocked(self, tmpdir):
        """Symlinks that escape cwd should be blocked after resolve."""
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside)
            link = tmpdir / 'link_to_outside'
            link.symlink_to(target)
            
            with pytest.raises(PathTraversalError):
                validate_safe_path('link_to_outside', str(tmpdir))
    
    def test_normalized_path_blocked(self, tmpdir):
        """Path that normalizes to outside should be blocked."""
        # models/.. normalizes to '.' -> stays in cwd, so this passes validation.
        # Use a path that truly escapes: go up one level via subdir then ..
        # e.g. subdir/.. where subdir is at root of cwd - but that also normalizes within.
        # True escape: '../outside' from within a subdirectory of cwd.
        (tmpdir / 'subdir').mkdir()
        old_cwd = os.getcwd()
        os.chdir(tmpdir / 'subdir')
        try:
            with pytest.raises(PathTraversalError):
                validate_safe_path('../outside', str(tmpdir))
        finally:
            os.chdir(old_cwd)


class TestValidateSubdirExists:
    """Test subdirectory existence validation."""
    
    def test_dot_returns_cwd(self, tmpdir):
        result = validate_subdir_exists('.', str(tmpdir))
        assert result == tmpdir.resolve()
    
    def test_existing_single_level_subdir(self, tmpdir):
        (tmpdir / 'models').mkdir()
        result = validate_subdir_exists('models', str(tmpdir))
        assert result == tmpdir / 'models'
    
    def test_existing_multi_level_subdir(self, tmpdir):
        (tmpdir / 'models' / 'bert').mkdir(parents=True)
        result = validate_subdir_exists('models/bert', str(tmpdir))
        assert result == tmpdir / 'models' / 'bert'
    
    def test_nonexistent_subdir_blocked(self, tmpdir):
        with pytest.raises(PathTraversalError, match='does not exist'):
            validate_subdir_exists('nonexistent', str(tmpdir))
    
    def test_missing_intermediate_dir_blocked(self, tmpdir):
        """models/bert where models/ doesn't exist should be blocked."""
        (tmpdir / 'models').mkdir()  # only models exists, not models/bert
        with pytest.raises(PathTraversalError, match='Intermediate directory'):
            validate_subdir_exists('models/bert', str(tmpdir))
    
    def test_traversal_in_subdir_key_blocked(self, tmpdir):
        with pytest.raises(PathTraversalError):
            validate_subdir_exists('../etc', str(tmpdir))
    
    def test_absolute_subdir_blocked(self, tmpdir):
        with pytest.raises(PathTraversalError):
            validate_subdir_exists('/tmp', str(tmpdir))
    
    def test_empty_key_blocked(self, tmpdir):
        # Empty string path resolves to cwd itself - should be handled
        with pytest.raises(PathTraversalError):
            validate_subdir_exists('', str(tmpdir))


class TestBuildDestPath:
    """Test destination path building."""
    
    def test_build_with_cwd_subdir(self, tmpdir):
        (tmpdir / 'models').mkdir()
        subdir = tmpdir / 'models'
        result = build_dest_path(subdir, 'model.bin', str(tmpdir))
        assert result == tmpdir / 'models' / 'model.bin'
    
    def test_build_with_dot_subdir(self, tmpdir):
        subdir = tmpdir.resolve()
        result = build_dest_path(subdir, 'model.bin', str(tmpdir))
        assert result == tmpdir / 'model.bin'
    
    def test_filename_with_path_traversal_blocked(self, tmpdir):
        (tmpdir / 'models').mkdir()
        subdir = tmpdir / 'models'
        with pytest.raises(PathTraversalError):
            build_dest_path(subdir, '../../etc/passwd', str(tmpdir))
