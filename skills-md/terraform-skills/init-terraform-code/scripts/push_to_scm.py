#!/usr/bin/env python3
"""
Copy generated Terraform code into the cloned workspace repository,
create a change request branch, commit, and push.

Usage:
    python3 push_to_scm.py \
        --repo-dir ./workspace-repo \
        --source-dir ./generated \
        --working-dir infra \
        --branch change-request/CR-123 \
        --commit-message "Init Terraform code for CR-123"

Exit codes:
    0 - Code pushed successfully
    1 - Push failed
"""

import argparse
import os
import shutil
import subprocess
import sys


def run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git {' '.join(args)} failed:\n{e.stderr.strip()}", file=sys.stderr)
        raise


def push_to_scm(repo_dir: str, source_dir: str, working_dir: str, branch: str, commit_message: str) -> bool:
    """Copy generated files into repo, create branch, commit, and push."""
    repo_dir = os.path.abspath(repo_dir)
    source_dir = os.path.abspath(source_dir)

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
        return True

    except subprocess.CalledProcessError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Push generated Terraform code to SCM")
    parser.add_argument("--repo-dir", required=True, help="Path to the cloned workspace repository")
    parser.add_argument("--source-dir", required=True, help="Path to the directory with generated Terraform files")
    parser.add_argument("--working-dir", default="", help="Subdirectory in the repo for Terraform code (default: root)")
    parser.add_argument("--branch", required=True, help="Branch name for the change request")
    parser.add_argument("--commit-message", default="Init Terraform code via DSO AI agent", help="Git commit message")
    args = parser.parse_args()

    if not push_to_scm(args.repo_dir, args.source_dir, args.working_dir, args.branch, args.commit_message):
        sys.exit(1)


if __name__ == "__main__":
    main()
