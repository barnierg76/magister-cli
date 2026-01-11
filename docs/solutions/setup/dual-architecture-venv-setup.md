---
title: "Dual Architecture Virtual Environment Setup for Apple Silicon"
category: setup
severity: high
date: 2026-01-11
status: solved
tags:
  - python
  - virtual-environment
  - apple-silicon
  - arm64
  - x86_64
  - rosetta
  - claude-code
  - pydantic
  - architecture
components:
  - pydantic_core (native extension)
  - virtual environment
  - wrapper scripts
symptoms:
  - "ImportError: dlopen failed - incompatible architecture (have 'arm64', need 'x86_64')"
  - "mach-o file, but is an incompatible architecture"
  - CLI commands fail with architecture mismatch
  - MCP server fails to start
---

# Dual Architecture Virtual Environment Setup

## Problem Summary

Running `magister` or `magister-mcp` commands from the terminal resulted in ImportError due to architecture mismatch between the Python interpreter and compiled native extensions (pydantic_core).

### Error Message

```
ImportError: dlopen(/path/to/pydantic_core/_pydantic_core.cpython-312-darwin.so, 0x0002):
  tried: '...' (mach-o file, but is an incompatible architecture (have 'arm64', need 'x86_64'))
```

## Root Cause

On Apple Silicon Macs, there are two execution contexts with different architectures:

| Context | Architecture | How it runs |
|---------|--------------|-------------|
| Claude Code | x86_64 | Under Rosetta 2 emulation |
| Native Terminal | arm64 | Native Apple Silicon |

**The conflict:**
1. The project `.venv` was created from Claude Code (running x86_64 via Rosetta)
2. All compiled packages (like pydantic_core) were built for x86_64
3. When running from native arm64 terminal, these x86_64 binaries cannot load
4. Result: ImportError with architecture mismatch

### Verification Commands

```bash
# Check which architecture your shell is running
arch                    # Returns: arm64 (native) or i386 (Rosetta)

# Check if process is running under Rosetta
sysctl -n sysctl.proc_translated   # Returns: 1 (Rosetta) or 0 (native)

# Check pydantic_core binary architecture
file .venv/lib/python3.12/site-packages/pydantic_core/*.so
# Shows: Mach-O 64-bit ... arm64 OR x86_64
```

## Solution

Create separate virtual environments for each architecture and use smart wrapper scripts.

### Step 1: Create Architecture-Specific Virtual Environments

```bash
cd /Users/iamstudios/Desktop/Magister/magister-cli

# Rename original venv to mark it as x86_64
mv .venv .venv-x86_64

# Create arm64 venv using arch prefix
arch -arm64 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv .venv-arm64

# Install packages in arm64 venv
arch -arm64 .venv-arm64/bin/pip install --upgrade pip
arch -arm64 .venv-arm64/bin/pip install -e ".[dev]"

# Create symlink for uv/dev tool compatibility (from current context)
ln -sf .venv-x86_64 .venv
```

### Step 2: Create Smart Wrapper Scripts

**File: ~/.local/bin/magister**
```bash
#!/bin/bash
cd /Users/iamstudios/Desktop/Magister/magister-cli

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    VENV=".venv-arm64"
else
    VENV=".venv-x86_64"
fi

# Use the appropriate venv
exec "$VENV/bin/python" -m magister_cli.main "$@"
```

**File: ~/.local/bin/magister-mcp**
```bash
#!/bin/bash
cd /Users/iamstudios/Desktop/Magister/magister-cli

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    VENV=".venv-arm64"
else
    VENV=".venv-x86_64"
fi

# Use the appropriate venv
exec "$VENV/bin/python" -m magister_cli.mcp "$@"
```

Make scripts executable:
```bash
chmod +x ~/.local/bin/magister ~/.local/bin/magister-mcp
```

### Step 3: Verify Setup

```bash
# Final directory structure
ls -la | grep venv
# .venv -> .venv-x86_64   (symlink)
# .venv-arm64/            (native arm64)
# .venv-x86_64/           (Rosetta x86_64)

# Verify pydantic_core architectures
file .venv-arm64/lib/python3.12/site-packages/pydantic_core/*.so
# Output: ... arm64

file .venv-x86_64/lib/python3.12/site-packages/pydantic_core/*.so
# Output: ... x86_64

# Test command works
magister status
```

## How It Works

When you run `magister`:
1. Shell executes `~/.local/bin/magister`
2. Script detects architecture via `uname -m`
3. Script selects appropriate venv (`.venv-arm64` or `.venv-x86_64`)
4. Correct Python interpreter loads correct compiled binaries
5. Command succeeds

## Prevention Strategies

### For New Projects

1. **Document architecture strategy** in CONTRIBUTING.md
2. **Use separate venv directories** from the start
3. **Add to .gitignore**:
   ```
   .venv
   .venv-arm64
   .venv-x86_64
   ```
4. **Create auto-detect activation script**:
   ```bash
   # activate.sh
   source ".venv-$(uname -m)/bin/activate"
   ```

### Quick Architecture Check

Add this to your project's startup:

```python
import os
import platform

def validate_architecture():
    """Ensure venv matches execution context"""
    shell_arch = os.popen('uname -m').read().strip()
    python_arch = platform.machine()

    if shell_arch != python_arch:
        raise RuntimeError(
            f"Architecture mismatch: shell={shell_arch}, python={python_arch}\n"
            f"Activate correct venv: source .venv-{shell_arch}/bin/activate"
        )
```

### CI/CD Testing

Test both architectures in your pipeline:

```yaml
jobs:
  test-arm64:
    runs-on: macos-13
    steps:
      - run: arch -arm64 python3 -m venv .venv-arm64
      - run: source .venv-arm64/bin/activate && pytest

  test-x86_64:
    runs-on: macos-13
    steps:
      - run: arch -x86_64 python3 -m venv .venv-x86_64
      - run: source .venv-x86_64/bin/activate && pytest
```

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `.venv-arm64/` | Created | Native arm64 virtual environment |
| `.venv-x86_64/` | Renamed from `.venv` | Rosetta x86_64 virtual environment |
| `.venv` | Symlink | Points to `.venv-x86_64` for dev tools |
| `~/.local/bin/magister` | Created | Smart wrapper with arch detection |
| `~/.local/bin/magister-mcp` | Created | Smart wrapper for MCP server |

## Related Documentation

- [Wave 2 Enhancements](../features/wave2-enhancements-20260108.md) - First mention of arch prefix requirement
- [Parent Accounts Fix](../api-issues/parent-accounts-and-attachments.md) - Similar multi-environment issue

## Key Learnings

1. **Claude Code runs under Rosetta** - This is not obvious and causes venv issues
2. **Native extensions are architecture-specific** - pydantic_core, cryptography, etc.
3. **Universal binaries help** - Python itself is universal, but pip packages aren't
4. **Wrapper scripts work well** - Auto-detection at runtime is reliable
5. **Document early** - Include Apple Silicon notes in setup documentation

## Compounding Value

- **First occurrence**: 30+ minutes debugging architecture mismatch
- **With this doc**: 2 minutes to recognize and fix
- **Future prevention**: Architecture-aware setup scripts from project start
