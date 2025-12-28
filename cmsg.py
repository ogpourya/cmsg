#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shlex

def run_command(command, check=True, capture_output=True, env=None):
    """Runs a shell command and returns the result."""
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env or os.environ
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running command: {e.cmd}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            sys.exit(1)
        else:
            raise

def is_working_directory_clean():
    """Checks if the git working directory is clean."""
    result = run_command(["git", "status", "--porcelain"])
    return not result.stdout.strip()

def get_full_hash(commit_id):
    """Resolves a commit ID (short or full) to a full hash."""
    try:
        result = run_command(["git", "rev-parse", commit_id])
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print(f"Error: Could not resolve commit ID '{commit_id}'")
        sys.exit(1)

def is_head(commit_hash):
    """Checks if the given hash is the current HEAD."""
    head_hash = get_full_hash("HEAD")
    return commit_hash == head_hash

def get_parent_hash(commit_hash):
    """Gets the parent hash of the given commit."""
    # Check if it's a root commit
    try:
        # If HEAD has no parent (root), verify logic.
        # rev-parse commit^ fails if it's root.
        result = run_command(["git", "rev-parse", f"{commit_hash}^"], check=False)
        if result.returncode != 0:
            return None # Root commit
        return result.stdout.strip()
    except Exception:
        return None

def internal_sequence_editor():
    """Logic for GIT_SEQUENCE_EDITOR."""
    # Arguments passed by git: <file>
    # We also expect env var CMSG_TARGET_HASH
    target_hash = os.environ.get("CMSG_TARGET_HASH")
    if not target_hash:
        print("Error: CMSG_TARGET_HASH not set in sequence editor")
        sys.exit(1)

    todo_file = sys.argv[1]
    
    with open(todo_file, "r") as f:
        lines = f.readlines()

    new_lines = []
    found = False
    for line in lines:
        parts = line.strip().split()
        if not parts or parts[0] == '#':
            new_lines.append(line)
            continue
        
        # parts[1] is the short hash usually
        current_short_hash = parts[1]
        
        # Resolve short hash to full hash to compare
        try:
            current_full_hash = subprocess.check_output(
                ["git", "rev-parse", current_short_hash], text=True
            ).strip()
        except subprocess.CalledProcessError:
            current_full_hash = "" # Should not happen if git is working right

        if current_full_hash == target_hash:
            # Replace 'pick' with 'reword'
            if parts[0] == "pick":
                new_line = line.replace("pick", "reword", 1)
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(todo_file, "w") as f:
        f.writelines(new_lines)
    
    if not found:
        # If we didn't find the commit in the todo list, it's unexpected but let git handle it.
        pass

def internal_message_editor():
    """Logic for GIT_EDITOR when -m is provided."""
    # Arguments passed by git: <file>
    # We expect env var CMSG_NEW_MESSAGE
    new_message = os.environ.get("CMSG_NEW_MESSAGE")
    if new_message is None:
        print("Error: CMSG_NEW_MESSAGE not set in message editor")
        sys.exit(1)
    
    msg_file = sys.argv[1]
    with open(msg_file, "w") as f:
        f.write(new_message)

def main():
    # Handle internal recursive calls
    if "--internal-sequence-editor" in sys.argv:
        # Remove the flag and run the internal function
        sys.argv.remove("--internal-sequence-editor")
        internal_sequence_editor()
        return
    
    if "--internal-message-editor" in sys.argv:
        sys.argv.remove("--internal-message-editor")
        internal_message_editor()
        return

    parser = argparse.ArgumentParser(description="Edit any git commit message.")
    parser.add_argument("-m", "--message", help="New commit message")
    parser.add_argument("-c", "--commit", help="Commit ID (default: HEAD)")
    
    args = parser.parse_args()

    # 1. Check clean working directory
    if not is_working_directory_clean():
        print("Error: Working directory is not clean. Please commit or stash changes.")
        sys.exit(1)

    # 2. Resolve target commit
    target_commit = args.commit if args.commit else "HEAD"
    target_full_hash = get_full_hash(target_commit)

    # 3. Handle message
    new_message = args.message

    # 4. Check if target is HEAD
    if is_head(target_full_hash):
        git_cmd = ["git", "commit", "--amend"]
        if new_message is not None:
            git_cmd.extend(["-m", new_message])
        
        # If no message, git will open editor automatically.
        # run_command will stream output/input if we don't capture?
        # We should let the user interact with the editor.
        if new_message is None:
             subprocess.run(git_cmd, check=True)
        else:
             run_command(git_cmd)
        
        print(f"Successfully edited commit {target_full_hash[:7]}")
        return

    # 5. Target is not HEAD (Rebase required)
    
    # Calculate parent for rebase
    parent_hash = get_parent_hash(target_full_hash)
    
    rebase_cmd = ["git", "rebase", "-i"]
    if parent_hash:
        rebase_cmd.append(parent_hash)
    else:
        rebase_cmd.append("--root")
    
    # Prepare environment for rebase
    env = os.environ.copy()
    
    # Set sequence editor to self
    # We need the absolute path to this script
    script_path = os.path.abspath(__file__)
    # We need to run it with the same python interpreter
    python_exe = sys.executable
    
    env["GIT_SEQUENCE_EDITOR"] = f"{shlex.quote(python_exe)} {shlex.quote(script_path)} --internal-sequence-editor"
    env["CMSG_TARGET_HASH"] = target_full_hash
    
    if new_message is not None:
        # Set editor to self to write the message
        env["GIT_EDITOR"] = f"{shlex.quote(python_exe)} {shlex.quote(script_path)} --internal-message-editor"
        env["CMSG_NEW_MESSAGE"] = new_message
    else:
        # Allow default editor
        pass
    
    # Run rebase
    # We must allow interaction for the rebase process (unless we control everything)
    # But wait, GIT_SEQUENCE_EDITOR will be run non-interactively by git.
    # GIT_EDITOR (if no -m) will be interactive.
    try:
        subprocess.run(rebase_cmd, env=env, check=True)
        print(f"Successfully edited commit {target_full_hash[:7]}")
    except subprocess.CalledProcessError:
        print("Error during rebase.")
        sys.exit(1)

if __name__ == "__main__":
    main()
