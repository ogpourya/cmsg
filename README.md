# cmsg - Commit Message Editor

A command-line tool to easily edit any git commit message, including past commits.

## Installation

```bash
cd /tmp && git clone https://github.com/ogpourya/cmsg.git && uv tool install cmsg/
```

## Usage

### Edit the last commit message (Amend)
To edit the most recent commit message using your default editor:
```bash
cmsg
```
Equivalent to `git commit --amend`.

To set the message directly:
```bash
cmsg -m "New message"
```

### Edit a specific commit
To edit a past commit, provide its commit hash (short or full):
```bash
cmsg -c <commit_id>
```
This will open your editor to edit that commit's message.

To set the message directly:
```bash
cmsg -c <commit_id> -m "New message"
```

### Multiline Messages
You can use multiline messages:
```bash
cmsg -m "Title

Description paragraph."
```

## Warnings

**Rewriting History**: `cmsg` rewrites git history (changes commit hashes). If you have already pushed the commits you are editing, you will need to force push (`git push --force`) to update the remote repository. Be careful when rewriting history on shared branches.

**Clean Working Directory**: `cmsg` requires a clean working directory. Please commit or stash your changes before using it.
