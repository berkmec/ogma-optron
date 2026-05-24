# ogma-optron (backend)

Backend package for **ogma-optron** — open-source visual task understanding and agent runtime.

This directory is the installable Python package (`pip install -e .` from here). For the full project README — including the React frontend, agent.exe (claw) setup, the synthetic benchmark, and the 4-milestone roadmap — see the top-level [README.md](https://github.com/berkmec/ogma-optron#readme) on GitHub.

## Quick start (CLI only)

```bash
pip install -e .
optron --version
optron health
optron analyze path/to/screenshot.png --prompt "What is this?"
optron review --workspace .
```

See `app/cli.py` for all subcommands.

## License

MIT.
