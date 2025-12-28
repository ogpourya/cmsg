import os
import subprocess
import pytest
import shutil
import tempfile
import sys

# Path to cmsg.py
CMSG_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cmsg.py"))

@pytest.fixture
def repo_dir():
    # Create a temporary directory for the repo
    temp_dir = tempfile.mkdtemp()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "you@example.com"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Your Name"], cwd=temp_dir, check=True)
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)

def run_cmsg(cwd, args, env=None):
    # Run cmsg.py as a subprocess
    cmd = [sys.executable, CMSG_PY] + args
    return subprocess.run(cmd, cwd=cwd, env=env or os.environ.copy(), capture_output=True, text=True)

def create_commit(cwd, filename, message):
    with open(os.path.join(cwd, filename), "w") as f:
        f.write(f"content for {filename}")
    subprocess.run(["git", "add", filename], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=cwd, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()

def get_commit_message(cwd, commit_ref="HEAD"):
    return subprocess.check_output(
        ["git", "log", "-1", "--pretty=%B", commit_ref], cwd=cwd, text=True
    ).strip()

def test_amend_head_message(repo_dir):
    create_commit(repo_dir, "file1.txt", "initial")
    create_commit(repo_dir, "file2.txt", "second")
    
    # Amend HEAD
    result = run_cmsg(repo_dir, ["-m", "amended second"])
    assert result.returncode == 0
    
    msg = get_commit_message(repo_dir)
    assert msg == "amended second"

def test_amend_head_editor(repo_dir):
    create_commit(repo_dir, "file1.txt", "initial")
    
    # Mock editor that changes message
    env = os.environ.copy()
    env["GIT_EDITOR"] = "sed -i 's/initial/edited/'"
    
    result = run_cmsg(repo_dir, [], env=env)
    assert result.returncode == 0
    
    msg = get_commit_message(repo_dir)
    assert msg == "edited"

def test_rebase_message(repo_dir):
    c1 = create_commit(repo_dir, "file1.txt", "first")
    c2 = create_commit(repo_dir, "file2.txt", "second")
    c3 = create_commit(repo_dir, "file3.txt", "third")
    
    # Edit c2
    result = run_cmsg(repo_dir, ["-c", c2, "-m", "new second"])
    assert result.returncode == 0, f"Stderr: {result.stderr}"
    
    # Verify c2 message changed
    # c2 hash will have changed. We need to find the commit that touches file2.txt?
    # Or just check history.
    log = subprocess.check_output(["git", "log", "--pretty=%s"], cwd=repo_dir, text=True).strip().splitlines()
    assert log[0] == "third"
    assert log[1] == "new second"
    assert log[2] == "first"

def test_rebase_short_hash(repo_dir):
    c1 = create_commit(repo_dir, "file1.txt", "first")
    c2 = create_commit(repo_dir, "file2.txt", "second")
    c3 = create_commit(repo_dir, "file3.txt", "third")
    
    short_c2 = c2[:7]
    result = run_cmsg(repo_dir, ["-c", short_c2, "-m", "new second short"])
    assert result.returncode == 0
    
    log = subprocess.check_output(["git", "log", "--pretty=%s"], cwd=repo_dir, text=True).strip().splitlines()
    assert log[1] == "new second short"

def test_rebase_root(repo_dir):
    c1 = create_commit(repo_dir, "file1.txt", "first")
    c2 = create_commit(repo_dir, "file2.txt", "second")
    
    result = run_cmsg(repo_dir, ["-c", c1, "-m", "new first"])
    assert result.returncode == 0
    
    log = subprocess.check_output(["git", "log", "--pretty=%s"], cwd=repo_dir, text=True).strip().splitlines()
    assert log[1] == "new first"

def test_multiline_message(repo_dir):
    create_commit(repo_dir, "file1.txt", "initial")
    
    multiline_msg = "Line 1\n\nLine 3"
    result = run_cmsg(repo_dir, ["-m", multiline_msg])
    assert result.returncode == 0
    
    msg = get_commit_message(repo_dir)
    assert msg == multiline_msg

def test_dirty_workdir(repo_dir):
    create_commit(repo_dir, "file1.txt", "initial")
    
    # Make dirty
    with open(os.path.join(repo_dir, "file1.txt"), "a") as f:
        f.write("dirty")
        
    result = run_cmsg(repo_dir, ["-m", "should fail"])
    assert result.returncode != 0
    assert "Working directory is not clean" in result.stdout

def test_rebase_editor(repo_dir):
    # This is tricky because we need to mock the editor that git opens during rebase 'reword'
    # But git opens GIT_EDITOR for reword.
    # Our cmsg script does NOT set GIT_EDITOR if -m is not provided.
    # So we can set GIT_EDITOR in our env to a mock editor.
    
    c1 = create_commit(repo_dir, "file1.txt", "first")
    c2 = create_commit(repo_dir, "file2.txt", "second")
    
    env = os.environ.copy()
    # The editor should replace the content of the file
    env["GIT_EDITOR"] = "sed -i 's/first/edited first/'"
    
    result = run_cmsg(repo_dir, ["-c", c1], env=env)
    assert result.returncode == 0
    
    log = subprocess.check_output(["git", "log", "--pretty=%s"], cwd=repo_dir, text=True).strip().splitlines()
    assert log[1] == "edited first"

