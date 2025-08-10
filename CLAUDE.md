# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python module for SSH/VM connection management. The main functionality should be implemented as an `SSHConnection` class that handles connecting to remote Linux VMs, executing commands, and managing various failure scenarios.

## Development Environment

- **Python Version**: 3.12 (specified in .python-version)
- **Project Management**: Uses pyproject.toml for dependency management
- **Package Name**: vm-connection

## Expected Architecture

The core functionality should be implemented as a class-based module:

```python
# Expected usage pattern
conn = SSHConnection(host='192.168.1.10', user='tester', key_path='/path/to/id_rsa')
conn.connect()
```

Key components to implement:
- SSH connection management with private key authentication
- Command execution with proper error handling
- Connection state management and cleanup
- Comprehensive failure scenario handling

## Development Commands

**Run the main module:**
```bash
python main.py
```

**Install dependencies (when added):**
```bash
pip install -e .
```

**Package management:**
- Dependencies should be added to the `dependencies` array in pyproject.toml
- The project requires Python >=3.12
- use uv for all