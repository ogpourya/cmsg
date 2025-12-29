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
            print(f"💥 Error running command: {e.cmd}")
            if e.stdout:
                print(f"📤 Stdout:\n{e.stdout}")
            if e.stderr:
                print(f"📥 Stderr:\n{e.stderr}")
            print("❌ Exiting with failure.")
            sys.exit(1)
        else:
            raise

def is_working_directory_clean():
    """Checks if the git working directory is clean."""
    result = run_command(["git", "status", "--porcelain"])
    clean = not result.stdout.strip()
    if not clean:
        print("⚠️  Working directory not clean. Please commit or stash changes before continuing.")
    else:
        print("✨ Working directory is clean. Good to go.")
    return clean

def get_full_hash(commit_id):
    """Resolves a commit ID (short or full) to a full hash."""
    try:
        result = run_command(["git", "rev-parse", commit_id])
        full = result.stdout.strip()
        print(f"🔎 Resolved '{commit_id}' to {full[:7]}")
        return full
    except subprocess.CalledProcessError:
        print(f"🚫 Could not resolve commit ID '{commit_id}'. Please check the id and try again.")
        sys.exit(1)

def is_head(commit_hash):
    """Checks if the given hash is the current HEAD."""
    head_hash = get_full_hash("HEAD")
    match = commit_hash == head_hash
    if match:
        print(f"📍 Target {commit_hash[:7]} is HEAD.")
    else:
        print(f"📍 Target {commit_hash[:7]} is not HEAD.")
    return match

def get_parent_hash(commit_hash):
    """Gets the parent hash of the given commit."""
    try:
        result = run_command(["git", "rev-parse", f"{commit_hash}^"], check=False)
        if result.returncode != 0:
            print("🌱 This is a root commit - no parent found.")
            return None
        parent = result.stdout.strip()
        print(f"↩️  Parent commit is {parent[:7]}")
        return parent
    except Exception:
        print("⚠️  Could not determine parent commit.")
        return None

def internal_sequence_editor():
    """Logic for GIT_SEQUENCE_EDITOR."""
    target_hash = os.environ.get("CMSG_TARGET_HASH")
    if not target_hash:
        print("🚫 Environment error: CMSG_TARGET_HASH not set in sequence editor.")
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
        
        current_short_hash = parts[1]
        
        try:
            current_full_hash = subprocess.check_output(
                ["git", "rev-parse", current_short_hash], text=True
            ).strip()
        except subprocess.CalledProcessError:
            current_full_hash = ""

        if current_full_hash == target_hash:
            if parts[0] == "pick":
                new_line = line.replace("pick", "reword", 1)
                new_lines.append(new_line)
                found = True
                print(f"✏️  Marked {current_short_hash} for reword (target matched).")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(todo_file, "w") as f:
        f.writelines(new_lines)
    
    if not found:
        print("ℹ️  Commit not found in todo list. Letting git handle the sequence file.")

def internal_message_editor():
    """Logic for GIT_EDITOR when -m is provided."""
    new_message = os.environ.get("CMSG_NEW_MESSAGE")
    if new_message is None:
        print("🚫 Environment error: CMSG_NEW_MESSAGE not set in message editor.")
        sys.exit(1)
    
    msg_file = sys.argv[1]
    with open(msg_file, "w") as f:
        f.write(new_message)
    print("✍️  Wrote new commit message into the temporary editor file.")

def main():
    # Handle internal recursive calls
    if "--internal-sequence-editor" in sys.argv:
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
        print("🚫 Please commit or stash changes and try again. Progress 0%.")
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
        
        if new_message is None:
             subprocess.run(git_cmd, check=True)
        else:
             run_command(git_cmd)
        
        print(f"✅ Successfully edited commit {target_full_hash[:7]}. Done 100%.")
        return

    # 5. Target is not HEAD (Rebase required)
    
    parent_hash = get_parent_hash(target_full_hash)
    
    rebase_cmd = ["git", "rebase", "-i"]
    if parent_hash:
        rebase_cmd.append(parent_hash)
        print(f"🔧 Preparing interactive rebase onto parent {parent_hash[:7]}")
    else:
        rebase_cmd.append("--root")
        print("🔧 Preparing interactive rebase from root commit")

    env = os.environ.copy()
    
    script_path = os.path.abspath(__file__)
    python_exe = sys.executable
    
    env["GIT_SEQUENCE_EDITOR"] = f"{shlex.quote(python_exe)} {shlex.quote(script_path)} --internal-sequence-editor"
    env["CMSG_TARGET_HASH"] = target_full_hash
    
    if new_message is not None:
        env["GIT_EDITOR"] = f"{shlex.quote(python_exe)} {shlex.quote(script_path)} --internal-message-editor"
        env["CMSG_NEW_MESSAGE"] = new_message
        print("📝 Will set the new commit message non interactively.")
    else:
        print("📝 No -m provided. Git will open your default editor to edit the commit message.")

    try:
        subprocess.run(rebase_cmd, env=env, check=True)
        print(f"✅ Successfully edited commit {target_full_hash[:7]}. Rebase finished 100%.")
    except subprocess.CalledProcessError:
        print("❌ Error during rebase. Please resolve conflicts or run 'git rebase --abort' and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
