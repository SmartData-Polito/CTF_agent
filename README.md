# CTF Agent

A multi-strategy CTF solving framework. Benchmarks are sourced from `X-BOW/benchmarks/`.

## Setup

1. Copy `.env` to the project root and set your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...
   ```

2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

3. Make the runner executable (first time only):
   ```bash
   chmod +x run.sh
   ```

---

## Usage

```bash
./run.sh <command> [options]
```

Each command (except `evaluate`) automatically builds and starts the benchmark Docker service before running, and tears it down after.

---

## Commands

### `claude` — Claude Code agent

Runs the Claude CLI as an autonomous CTF solver.

| Flag | Description | Default |
|------|-------------|---------|
| `-b BENCHMARK` | Benchmark name (**required**) | — |
| `-m MODEL` | Claude model to use | `claude-opus-4-5` |
| `-t MAX_TURNS` | Max agent turns | `50` |

```bash
./run.sh claude -b XBEN-001-24
./run.sh claude -b XBEN-001-24 -m claude-opus-4-6 -t 100
```

Results are saved to `experiment/results/claude-code/<benchmark>/<timestamp>/`.

---

### `gpt` — GPT agent

Runs the LangGraph-based executor agent.

| Flag | Description | Default |
|------|-------------|---------|
| `-b BENCHMARK` | Benchmark name (**required**) | — |
| `-m MODEL` | OpenAI model to use | `gpt-5` |
| `-e` | Enable evaluator (pre-filters tool calls) | off |
| `-p` | Enable planner (generates attack strategy from recon) | off |
| `-r TIMESTAMP` | Use a specific recon report timestamp | latest |

```bash
./run.sh gpt -b XBEN-001-24
./run.sh gpt -b XBEN-001-24 -e -p
./run.sh gpt -b XBEN-001-24 -m gpt-4o -e -p -r 2026-01-26_19-44-34
```

Results are saved to `experiment/results/executor-<model>/<benchmark>/<timestamp>/`.

> When `-p` is enabled and no recon report exists for the benchmark, recon runs automatically.

---

### `recon` — Reconnaissance

Runs the recon agent to fingerprint the target and produce a vulnerability report.

| Flag | Description | Default |
|------|-------------|---------|
| `-b BENCHMARK` | Benchmark name (**required**) | — |
| `-m MODEL` | OpenAI model to use | `gpt-5` |

```bash
./run.sh recon -b XBEN-001-24
./run.sh recon -b XBEN-001-24 -m gpt-4o
```

Reports are saved to `experiment/reports/<benchmark>/<timestamp>/`.

---

### `evaluate` — Post-execution evaluation

Evaluates stored run histories using an LLM judge. Does **not** start/stop Docker services.

| Flag | Description | Default |
|------|-------------|---------|
| `-s STRATEGY` | Strategy folder (e.g. `executor-gpt-5`, `claude-code`) | all |
| `-b BENCHMARK` | Benchmark name | all |
| `-t TIMESTAMP` | Specific run timestamp | all |
| `-m MODEL` | Evaluator model | `gpt-4o-mini` |

```bash
# Evaluate all runs across all strategies
./run.sh evaluate

# Evaluate all runs for a specific strategy
./run.sh evaluate -s executor-gpt-5

# Evaluate a specific benchmark across all its runs
./run.sh evaluate -s executor-gpt-5 -b XBEN-001-24

# Evaluate one specific run
./run.sh evaluate -s executor-gpt-5 -b XBEN-001-24 -t 2026-01-26_19-44-34
```

Evaluation reports are saved to `experiment/evaluations/<strategy>/<benchmark>/<timestamp>/evaluation.txt`.

---

## Output Structure

```
experiment/
├── results/
│   ├── executor-gpt-5/<benchmark>/<timestamp>/
│   │   ├── history.json
│   │   └── tracker.json
│   └── claude-code/<benchmark>/<timestamp>/
│       ├── history.json
│       └── tracker.json
├── reports/
│   └── <benchmark>/<timestamp>/
│       ├── history.json
│       ├── report.json
│       ├── report.txt
│       └── tracker.json
└── evaluations/
    └── <strategy>/<benchmark>/<timestamp>/
        └── evaluation.txt
```
