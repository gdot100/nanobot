# Agent Instructions

- Whenever I refer to "nanobot", I am referring to the Python agent app: https://github.com/HKUDS/nanobot

## Running nanobot gateway

The `nanobot gateway` command is a long-running process that will block and timeout in the bash tool. Always run it as a background process using:

```
python -c "import subprocess, sys; subprocess.Popen([sys.executable, '-m', 'nanobot', 'gateway'], creationflags=subprocess.CREATE_NO_WINDOW)"
```

To verify it's running:
```
Get-Process -Name "nanobot" -ErrorAction SilentlyContinue
```
