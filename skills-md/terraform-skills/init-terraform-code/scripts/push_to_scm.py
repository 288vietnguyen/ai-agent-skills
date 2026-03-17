#!/usr/bin/env python3
"""
Copy generated Terraform code into the cloned workspace repository,
create a feature branch, commit, push, and auto-create a merge request.

Branch naming:
    All branches MUST start with 'feature/'. The script enforces this prefix.

Usage:
    python3 push_to_scm.py \
        --repo-dir ./workspace-repo \
        --source-dir ./generated \
        --working-dir infra \
        --branch feature/CR-123 \
        --target-branch main \
        --commit-message "Init Terraform code for CR-123"

Exit codes:
    0 - Code pushed and merge request created successfully
    1 - Push or merge request creation failed
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error


def run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git {' '.join(args)} failed:\n{e.stderr.strip()}", file=sys.stderr)
        raise


def push_to_scm(repo_dir: str, source_dir: str, working_dir: str, branch: str,
                target_branch: str, commit_message: str) -> bool:
    """Copy generated files into repo, create branch, commit, push, and create merge request."""
    repo_dir = os.path.abspath(repo_dir)
    source_dir = os.path.abspath(source_dir)

    # Enforce feature/ prefix
    if not branch.startswith("feature/"):
        print(f"ERROR: Branch name must start with 'feature/'. Got: '{branch}'", file=sys.stderr)
        return False

    if not os.path.isdir(repo_dir):
        print(f"ERROR: Repository directory '{repo_dir}' does not exist.", file=sys.stderr)
        return False

    if not os.path.isdir(source_dir):
        print(f"ERROR: Source directory '{source_dir}' does not exist.", file=sys.stderr)
        return False

    try:
        # Check if branch already exists on remote
        result = run_git(["ls-remote", "--heads", "origin", branch], cwd=repo_dir)
        if branch in result.stdout:
            print(f"ERROR: Branch '{branch}' already exists on remote.", file=sys.stderr)
            return False

        # Create new branch
        print(f"Creating branch: {branch}")
        run_git(["checkout", "-b", branch], cwd=repo_dir)

        # Determine target directory in the repo
        target_dir = os.path.join(repo_dir, working_dir) if working_dir else repo_dir
        os.makedirs(target_dir, exist_ok=True)

        # Copy generated files to target directory
        print(f"Copying generated files to: {target_dir}")
        for item in os.listdir(source_dir):
            src = os.path.join(source_dir, item)
            dst = os.path.join(target_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                print(f"  Copied: {item}")
            elif os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"  Copied directory: {item}")

        # Stage all changes
        run_git(["add", "."], cwd=repo_dir)

        # Check if there are changes to commit
        result = run_git(["status", "--porcelain"], cwd=repo_dir)
        if not result.stdout.strip():
            print("WARNING: No changes to commit.", file=sys.stderr)
            return False

        # Commit
        print(f"Committing: {commit_message}")
        run_git(["commit", "-m", commit_message], cwd=repo_dir)

        # Push
        print(f"Pushing branch '{branch}' to origin...")
        run_git(["push", "-u", "origin", branch], cwd=repo_dir)

        print(f"\nSUCCESS: Code pushed to branch '{branch}'.")

        # Auto-create merge request
        if target_branch:
            print(f"\nCreating merge request: {branch} → {target_branch}")
            mr_url = create_merge_request(repo_dir, branch, target_branch, commit_message)
            if mr_url:
                print(f"  Merge request created: {mr_url}")
            else:
                print("  WARNING: Could not auto-create merge request.", file=sys.stderr)

        return True

    except subprocess.CalledProcessError:
        return False


def _get_remote_url(repo_dir: str) -> str:
    """Get the remote origin URL."""
    result = run_git(["remote", "get-url", "origin"], cwd=repo_dir)
    return result.stdout.strip()


def _extract_repo_path(remote_url: str) -> str:
    """Extract 'owner/repo' from remote URL."""
    # Handle HTTPS: https://gitlab.com/owner/repo.git
    # Handle SSH: git@gitlab.com:owner/repo.git
    url = remote_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if "://" in url:
        # HTTPS
        parts = url.split("://", 1)[1].split("/", 1)
        return parts[1] if len(parts) > 1 else ""
    elif ":" in url and "@" in url:
        # SSH
        return url.split(":", 1)[1]
    return ""


def _get_gitlab_base_url(remote_url: str) -> str:
    """Extract GitLab base URL from remote URL."""
    if "://" in remote_url:
        parts = remote_url.split("://")
        host = parts[1].split("/")[0]
        return f"{parts[0]}://{host}"
    elif "@" in remote_url:
        host = remote_url.split("@")[1].split(":")[0]
        return f"https://{host}"
    return ""


def create_merge_request(repo_dir: str, source_branch: str, target_branch: str,
                         title: str) -> str | None:
    """Create a GitLab merge request.

    Returns the merge request URL on success, None on failure.
    """
    remote_url = _get_remote_url(repo_dir)
    repo_path = _extract_repo_path(remote_url)

    if not repo_path:
        print(f"  Could not extract repo path from: {remote_url}", file=sys.stderr)
        return None

    token = os.environ.get("GITLAB_TOKEN", "")
    if not token:
        print("  GITLAB_TOKEN not set, cannot create merge request.", file=sys.stderr)
        return None

    base_url = _get_gitlab_base_url(remote_url)
    encoded_path = repo_path.replace("/", "%2F")
    api_url = f"{base_url}/api/v4/projects/{encoded_path}/merge_requests"

    data = json.dumps({
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "remove_source_branch": True,
    }).encode()

    req = urllib.request.Request(
        api_url,
        data=data,
        headers={
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("web_url", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  GitLab API error {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  GitLab merge request failed: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Push generated Terraform code to SCM and create merge request")
    parser.add_argument("--repo-dir", required=True, help="Path to the cloned workspace repository")
    parser.add_argument("--source-dir", required=True, help="Path to the directory with generated Terraform files")
    parser.add_argument("--working-dir", default="", help="Subdirectory in the repo for Terraform code (default: root)")
    parser.add_argument("--branch", required=True, help="Branch name (must start with 'feature/')")
    parser.add_argument("--target-branch", required=True, help="Target branch for merge request (e.g., main)")
    parser.add_argument("--commit-message", default="Init Terraform code via DSO AI agent", help="Git commit message")
    args = parser.parse_args()

    if not push_to_scm(args.repo_dir, args.source_dir, args.working_dir,
                       args.branch, args.target_branch, args.commit_message):
        sys.exit(1)


if __name__ == "__main__":
    main()
