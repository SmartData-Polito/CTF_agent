#!/usr/bin/env bash
set -euo pipefail

BENCHMARK_ROOT="./X-BOW/benchmarks"

usage() {
    cat <<EOF
Usage: ./run.sh <command> [options]

Commands:
  claude    Run Claude Code agent on a benchmark
  gpt       Run GPT agent on a benchmark
  recon     Run recon on a benchmark
  evaluate  Evaluate stored histories

claude options:
  -b BENCHMARK        Benchmark name (e.g. XBEN-001-24)  [required]
  -m MODEL            Model (default: claude-opus-4-5)
  -t MAX_TURNS        Max turns (default: 50)

gpt options:
  -b BENCHMARK        Benchmark name  [required]
  -m MODEL            Model (default: gpt-5)
  -e                  Enable evaluator (default: off)
  -p                  Enable planner (default: off)
  -r REPORT_TIMESTAMP Use specific recon report timestamp

recon options:
  -b BENCHMARK        Benchmark name  [required]
  -m MODEL            Model (default: gpt-5)

evaluate options:
  -s STRATEGY         Strategy folder (e.g. executor-gpt-5)
  -b BENCHMARK        Benchmark name
  -t TIMESTAMP        Specific run timestamp
  -m MODEL            Evaluator model (default: gpt-4o-mini)

Examples:
  ./run.sh claude -b XBEN-001-24
  ./run.sh claude -b XBEN-001-24 -m claude-opus-4-6 -t 100
  ./run.sh gpt -b XBEN-001-24 -e -p
  ./run.sh gpt -b XBEN-001-24 -m gpt-4o -e -r 2026-01-26_19-44-34
  ./run.sh recon -b XBEN-001-24
  ./run.sh evaluate -s executor-gpt-5 -b XBEN-001-24
  ./run.sh evaluate -s executor-gpt-5
EOF
    exit 1
}

start_benchmark() {
    local folder="$1"
    local full_path="$BENCHMARK_ROOT/$folder"
    echo "=== Building $folder ==="
    make -C "$full_path" build
    echo "=== Starting $folder ==="
    make -C "$full_path" run || true
}

stop_benchmark() {
    local folder="$1"
    local full_path="$BENCHMARK_ROOT/$folder"
    echo "=== Stopping $folder ==="
    docker compose -f "$full_path/docker-compose.yml" down --rmi local 2>/dev/null || true
}

cmd="${1:-}"
[ -z "$cmd" ] && usage
shift

case "$cmd" in

  claude)
    BENCHMARK=""
    MODEL="claude-opus-4-5"
    MAX_TURNS=50
    while getopts "b:m:t:" opt; do
      case $opt in
        b) BENCHMARK="$OPTARG" ;;
        m) MODEL="$OPTARG" ;;
        t) MAX_TURNS="$OPTARG" ;;
        *) usage ;;
      esac
    done
    [ -z "$BENCHMARK" ] && { echo "Error: -b BENCHMARK required"; usage; }
    start_benchmark "$BENCHMARK"
    python - <<PYEOF
from source.claudecode import claudecode_agent
success = claudecode_agent("$BENCHMARK", model="$MODEL", max_turns=$MAX_TURNS)
print("SUCCESS" if success else "FAILED")
PYEOF
    stop_benchmark "$BENCHMARK"
    ;;

  gpt)
    BENCHMARK=""
    MODEL="gpt-5"
    USE_EVALUATOR="False"
    USE_PLANNER="False"
    REPORT_TIMESTAMP="None"
    while getopts "b:m:epr:" opt; do
      case $opt in
        b) BENCHMARK="$OPTARG" ;;
        m) MODEL="$OPTARG" ;;
        e) USE_EVALUATOR="True" ;;
        p) USE_PLANNER="True" ;;
        r) REPORT_TIMESTAMP="\"$OPTARG\"" ;;
        *) usage ;;
      esac
    done
    [ -z "$BENCHMARK" ] && { echo "Error: -b BENCHMARK required"; usage; }
    start_benchmark "$BENCHMARK"
    python - <<PYEOF
from source.agent import execute
success = execute("$BENCHMARK", model="$MODEL", use_evaluator=$USE_EVALUATOR, use_planner=$USE_PLANNER, report_timestamp=$REPORT_TIMESTAMP)
print("SUCCESS" if success else "FAILED")
PYEOF
    stop_benchmark "$BENCHMARK"
    ;;

  recon)
    BENCHMARK=""
    MODEL="gpt-5"
    while getopts "b:m:" opt; do
      case $opt in
        b) BENCHMARK="$OPTARG" ;;
        m) MODEL="$OPTARG" ;;
        *) usage ;;
      esac
    done
    [ -z "$BENCHMARK" ] && { echo "Error: -b BENCHMARK required"; usage; }
    start_benchmark "$BENCHMARK"
    python - <<PYEOF
from source.recon_node import recon
recon("$BENCHMARK", model="$MODEL")
PYEOF
    stop_benchmark "$BENCHMARK"
    ;;

  evaluate)
    STRATEGY="None"
    BENCHMARK="None"
    TIMESTAMP="None"
    MODEL="gpt-4o-mini"
    while getopts "s:b:t:m:" opt; do
      case $opt in
        s) STRATEGY="\"$OPTARG\"" ;;
        b) BENCHMARK="\"$OPTARG\"" ;;
        t) TIMESTAMP="\"$OPTARG\"" ;;
        m) MODEL="$OPTARG" ;;
        *) usage ;;
      esac
    done
    python - <<PYEOF
from source.post_execution_evaluator import evaluate
evaluate(strategy=$STRATEGY, benchmark=$BENCHMARK, timestamp=$TIMESTAMP, model="$MODEL")
PYEOF
    ;;

  *)
    echo "Unknown command: $cmd"
    usage
    ;;
esac
