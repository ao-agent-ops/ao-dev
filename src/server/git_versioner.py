"""
Git-based code versioning for AO.

Uses a separate git repository at ~/.cache/ao/git to track code versions
without interfering with the user's git repository.
"""

import os
import subprocess
import shutil
from datetime import datetime
from typing import Optional

from ao.common.logger import create_file_logger
from ao.common.constants import AO_PROJECT_ROOT, GIT_DIR, GIT_VERSIONER_LOG

logger = create_file_logger(GIT_VERSIONER_LOG)


class GitVersioner:
    """
    Manages a separate git repository for tracking code versions.

    Uses GIT_DIR + GIT_WORK_TREE environment variables to maintain
    a separate repository that tracks only .py files in the project.
    """

    def __init__(self):
        """Initialize the GitVersioner using AO_PROJECT_ROOT and GIT_DIR."""
        self.project_root = os.path.abspath(AO_PROJECT_ROOT)
        self.git_dir = os.path.abspath(GIT_DIR)
        self._git_available: Optional[bool] = None
        self._initialized = False

    def is_git_available(self) -> bool:
        """Check if git is installed on the system."""
        if self._git_available is None:
            self._git_available = shutil.which("git") is not None
            if not self._git_available:
                logger.warning("git not found in PATH, code versioning disabled")
        return self._git_available

    def _run_git(
        self, *args, check: bool = True, capture_output: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run git command with GIT_DIR and GIT_WORK_TREE set.

        Args:
            *args: Git command arguments (e.g., "add", ".", "-A")
            check: Whether to raise on non-zero exit
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess instance
        """
        env = os.environ.copy()
        env["GIT_DIR"] = self.git_dir
        env["GIT_WORK_TREE"] = self.project_root

        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            env=env,
            cwd=self.project_root,
            check=check,
            capture_output=capture_output,
            text=True,
            timeout=30,
        )

    def _format_version(self, dt: datetime) -> str:
        """Format datetime as 'Version Dec 12, 8:45' (24h format)."""
        return f"Version {dt.strftime('%b')} {dt.day}, {dt.hour}:{dt.strftime('%M')}"

    def _ensure_initialized(self) -> bool:
        """Ensure the git repository is initialized. Returns True on success."""
        if self._initialized:
            return True

        if not self.is_git_available():
            return False

        try:
            # Check if already initialized
            if os.path.exists(os.path.join(self.git_dir, "HEAD")):
                self._initialized = True
                return True

            # Create git directory
            os.makedirs(self.git_dir, exist_ok=True)

            # Initialize repository
            self._run_git("init")

            # Configure user for commits (required by git)
            self._run_git("config", "user.name", "AO Code Versioner")
            self._run_git("config", "user.email", "ao@localhost")

            logger.info(f"Initialized repository at {self.git_dir}")
            self._initialized = True
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to initialize repository: {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to create git directory: {e}")
            return False

    def commit_and_get_version(self) -> Optional[str]:
        """
        Commit current .py files and return the version timestamp.

        Only commits if there are actual changes to .py files.
        Returns a human-readable timestamp string, or None if git is unavailable.
        """
        if not self._ensure_initialized():
            return None

        try:
            # Stage all .py files (only .py files using pathspec)
            self._run_git("add", "--all", "--", "*.py", "**/*.py")

            # Check if there are staged changes
            result = self._run_git("diff", "--cached", "--quiet", check=False)

            if result.returncode == 0:
                # No changes - return timestamp of current HEAD if it exists
                try:
                    result = self._run_git("log", "-1", "--format=%cI", "HEAD")
                    timestamp_str = result.stdout.strip()
                    dt = datetime.fromisoformat(timestamp_str)
                    return self._format_version(dt)
                except subprocess.SubprocessError:
                    # No commits yet and no changes
                    return None

            # There are changes - commit them
            now = datetime.now()
            commit_message = now.isoformat(timespec="seconds")
            self._run_git("commit", "-m", commit_message)

            version_str = self._format_version(now)
            logger.debug(f"Created commit with version {version_str}")
            return version_str

        except subprocess.SubprocessError as e:
            stderr = getattr(e, "stderr", None)
            logger.error(f"Git operation failed: {e}, stderr: {stderr}")
            return None
        except subprocess.TimeoutExpired:
            logger.error("Git operation timed out")
            return None

    def get_commit_timestamp(self, commit_hash: str) -> Optional[datetime]:
        """
        Get the timestamp of a commit.

        Args:
            commit_hash: The commit hash (can be short or full)

        Returns:
            datetime of the commit, or None if not found
        """
        if not self.is_git_available():
            return None

        try:
            result = self._run_git("log", "-1", "--format=%cI", commit_hash, check=True)
            timestamp_str = result.stdout.strip()
            return datetime.fromisoformat(timestamp_str)
        except (subprocess.SubprocessError, ValueError) as e:
            logger.debug(f"Could not get timestamp for {commit_hash}: {e}")
            return None
