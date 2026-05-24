# Repo intelligence

A semantic search layer over the workspace, so that `optron review` and the `/api/clawbridge/review` endpoint can pull *relevant* chunks for the user's question instead of cramming a fixed list of "key files" into the prompt.

## Stack

- **Chunker** — sliding window with overlap (`CHUNK_CHARS=1200`, `CHUNK_OVERLAP=200`) over indexable file extensions; reuses the same `IGNORED_DIRS` as the read-only scanner.
- **Embedder** — `fastembed` with the default `BAAI/bge-small-en-v1.5` model (384-dim, ONNX, ~130 MB, no torch). The model is a process-wide singleton (`lru_cache`).
- **Store** — numpy cosine search on disk:
  - `runs/repo_index/{index_id}/vectors.npy`
  - `runs/repo_index/{index_id}/chunks.jsonl`
  - `runs/repo_index/{index_id}/meta.json`
- **Catalog** — `repo_indexes` table in `sessions.db` (one row per build, latest one wins per `workspace_path`).

No FAISS dependency. For a few thousand chunks numpy is faster than FAISS's import cost; if a repo grows past ~50K chunks we'll revisit.

## Build

```bash
optron index --workspace .
```

Prints the `index_id`, file/chunk counts, and the model used. Re-running rebuilds; the old run stays on disk but `load_for_workspace` returns the newest one.

## Search

```bash
optron search -w . "where do we initialise the SQLite schema?" -k 5
```

Returns the top-K files with their best chunk excerpts. `--json` available.

## ClawBridge integration

`backend/app/clawbridge/wrapper.py` calls `repo_index.load_for_workspace()` on every `review`. If an index exists it computes the top-10 semantically relevant files for the user's prompt and prepends a `Semantic-search excerpts` block to the agent.exe prompt. The previous "Key file contents" block (README, pyproject.toml, package.json…) stays as a fallback so reviews still work *without* an index.

## API

```text
POST  /api/repo-index/build       { workspace_path, model? }  -> RepoIndexInfo
POST  /api/repo-index/search      { workspace_path, query, k_files?, chunks_per_file? }  -> SearchResponse
GET   /api/repo-index             ?workspace_path=...         -> RepoIndexInfo[]
GET   /api/repo-index/{index_id}                              -> RepoIndexInfo
```

## Bounds

| | value |
|---|---|
| max files indexed | 2000 |
| max bytes per file | 200 KB |
| chunk size | 1200 chars |
| chunk overlap | 200 chars |
| indexable extensions | python / js / ts / rs / go / java / md / toml / yaml / json / sh / sql / … |

These are deliberately conservative — first-run on a 500-file repo is < 30 s on CPU.
