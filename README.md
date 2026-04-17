# hymn-planner

Plan LDS hymns for sacrament meeting, adjusting for things like recency and popularity.

Local single-user tool. See `SPEC.md` for design and `MILESTONES.md` for build progress.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Run

```sh
uv run flask --app app run
```

The server listens on `http://localhost:5000`. `Ctrl+C` to stop.
