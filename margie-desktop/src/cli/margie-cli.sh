#!/usr/bin/env bash
# margie-cli -- the MARGIE command line on this computer. __MARK__; the app writes it again at each start.
# margie-cli opens a prompt where dane_wf margie sb runs the app's local pipeline; margie-cli --help says how.
set -u

APP_EXE=__APP_EXE__
APP_PIPELINE=__APP_PIPELINE__
SETTINGS_ENV=__SETTINGS_ENV__
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/margie/margie.env"
HISTORY="${XDG_STATE_HOME:-$HOME/.local/state}/margie/cli-local-history"

usage() {
    cat <<'MARGIE_HELP'
MARGIE command line on this computer: runs the app's local pipeline (margie runs MARGIE on your HPC)

  margie-cli               opens the prompt, where the commands below run
  margie-cli <command>     runs one command and returns, for example
                             margie-cli dane_wf margie sb -i genomes/ -o results/
  margie-cli --help        shows this

Running MARGIE on a genome file or a folder of genomes (.fna, .fa, .fasta):
  dane_wf margie sb --input <genome file or folder> --output <folder> [--working-directory <folder>] [--config <file>]

  -i, --input              a genome file, or a folder of genome files
  -o, --output             the folder the results go in (left out: the app's results folder)
  -w, --working-directory  the folder relative paths are read from; without --output,
                           the results go in its margie-output folder
  -c, --config             a file of the pipeline's settings (KEY=value lines, as in
                           pipeline.conf.sh), read over the ones saved in the app
  --tool <name>, --genes-only, --prepare-only, --list
                           passed to the pipeline (annotate.sh)

At the prompt:
  setup ...      sets up the tools and databases (setup.sh)
  check ...      reports what is set up (check.sh)
  cd <folder>    changes folder              app        opens the MARGIE app
  help           shows this                  exit       leaves (or Ctrl-D)
  any other line runs in this computer's shell
MARGIE_HELP
}

# The pipeline the app runs: the folder chosen in margie.env, else the app's own copy.
pipeline_root() {
    local chosen=""
    [ -f "$CONFIG" ] && chosen="$(. "$CONFIG" >/dev/null 2>&1; printf '%s' "${MARGIE_PIPELINE_ROOT:-}")"
    chosen="${chosen/#\~/$HOME}"
    if [ -n "$chosen" ] && [ -f "$chosen/annotate.sh" ] && [ -f "$chosen/pipeline.conf.sh" ]; then
        printf '%s' "$chosen"
    else
        printf '%s' "$APP_PIPELINE"
    fi
}

# The app's defaults for a local run, then the settings saved in the app, as the app passes them.
app_settings() {
    __APP_DEFAULTS__
    local saved
    saved="$(ELECTRON_RUN_AS_NODE=1 "$APP_EXE" "$SETTINGS_ENV" "$1/gui/settings.local.json" 2>/dev/null)"
    [ -n "$saved" ] && eval "$saved"
    return 0
}

absolute() {  # <path> <folder it is read from>
    case "$1" in
        "~"|"~/"*) printf '%s' "$HOME${1#\~}" ;;
        /*) printf '%s' "$1" ;;
        *) printf '%s/%s' "${2%/}" "$1" ;;
    esac
}

# Runs one of the pipeline's scripts with the app's settings, then *config* and *input* / *output*.
in_pipeline() {  # <script> [args]
    local script="$1" pipe
    shift
    pipe="$(pipeline_root)"
    if [ ! -f "$pipe/$script" ]; then
        echo "margie-cli: the local pipeline is not at $pipe yet. Open the app once (margie-cli app): it puts it there." >&2
        return 1
    fi
    (
        cd "$pipe" || exit 1
        app_settings "$pipe"
        if [ -n "${RUN_CONFIG:-}" ]; then set -a; . "$RUN_CONFIG"; set +a; fi
        [ -n "${RUN_INPUT:-}" ] && export USER_INPUT_DIR="$RUN_INPUT"
        if [ -n "${RUN_OUTPUT:-}" ]; then mkdir -p "$RUN_OUTPUT" && export OUTPUT_ROOT="$RUN_OUTPUT"; fi
        exec bash "./$script" "$@"
    )
}

run_dane_wf() {
    case "${1:-}" in
        -h|--help) usage; return 0 ;;
    esac
    if [ "${1:-}" != margie ] || [ "${2:-}" != sb ]; then
        echo "margie-cli: on this computer dane_wf runs MARGIE: dane_wf margie sb -i <genomes> -o <folder>" >&2
        return 2
    fi
    shift 2
    local input="" output="" work="" config="" name value
    local -a rest=()
    while [ $# -gt 0 ]; do
        name="${1%%=*}"
        value=""
        [ "$name" != "$1" ] && value="${1#*=}"
        case "$name" in
            -i|--input|-o|--output|-w|--working-directory|-c|--config|--tool)
                if [ "$name" = "$1" ]; then
                    if [ $# -lt 2 ] || [ "${2#-}" != "$2" ]; then echo "margie-cli: $name needs a value" >&2; return 2; fi
                    value="$2"
                    shift
                fi
                if [ -z "$value" ]; then echo "margie-cli: $name needs a value" >&2; return 2; fi
                case "$name" in
                    -i|--input) input="$value" ;;
                    -o|--output) output="$value" ;;
                    -w|--working-directory) work="$value" ;;
                    -c|--config) config="$value" ;;
                    --tool) rest+=(--tool "$value") ;;
                esac ;;
            -h|--help) usage; return 0 ;;
            --genes-only|--prepare-only|--list) rest+=("$1") ;;
            *:) echo "margie-cli: '$1' is a setting of MARGIE on the HPC; here the pipeline's settings are the app's (Settings) or a -c file" >&2; return 2 ;;
            *) echo "margie-cli: unknown option $1 (dane_wf margie sb here takes -i, -o, -w, -c and the pipeline's --tool, --genes-only, --prepare-only and --list)" >&2; return 2 ;;
        esac
        shift
    done

    local base staged="" rc
    base="$(pwd)"
    [ -n "$work" ] && base="$(absolute "$work" "$base")"
    if [ -n "$input" ]; then
        input="$(absolute "$input" "$base")"
        if [ ! -e "$input" ]; then echo "Input not found: $input" >&2; return 1; fi
        if [ -f "$input" ]; then
            # One genome: the pipeline reads a folder, so it gets one holding just this file.
            staged="$(mktemp -d "${TMPDIR:-/tmp}/margie-cli-input.XXXXXX")" || return 1
            ln -s "$input" "$staged/" 2>/dev/null || cp "$input" "$staged/"
        fi
    fi
    if [ -n "$output" ]; then
        output="$(absolute "$output" "$base")"
    elif [ -n "$work" ]; then
        output="$base/margie-output"
    fi
    if [ -n "$config" ]; then
        config="$(absolute "$config" "$base")"
        if [ ! -f "$config" ]; then echo "Config not found: $config" >&2; [ -n "$staged" ] && rm -rf "$staged"; return 1; fi
    fi
    RUN_INPUT="${staged:-$input}" RUN_OUTPUT="$output" RUN_CONFIG="$config" in_pipeline annotate.sh ${rest[@]+"${rest[@]}"}
    rc=$?
    [ -n "$staged" ] && rm -rf "$staged"
    return $rc
}

open_app() {
    __OPEN_APP__
}

# One command: MARGIE's own, else this computer's shell. 255 leaves the prompt.
dispatch() {
    case "${1:-}" in
        "") return 0 ;;
        exit|quit) return 255 ;;
        help|--help|-h) usage ;;
        cd) cd "${2:-$HOME}" ;;
        app) open_app ;;
        dane_wf) shift; run_dane_wf "$@" ;;
        setup) shift; in_pipeline setup.sh "$@" ;;
        check) shift; in_pipeline check.sh "$@" ;;
        *) "$@" ;;
    esac
}

if [ $# -gt 0 ]; then
    dispatch "$@"
    rc=$?
    [ $rc -eq 255 ] && rc=0
    exit $rc
fi

mkdir -p "$(dirname "$HISTORY")" 2>/dev/null
HISTFILE="$HISTORY"
set -o history
history -r "$HISTORY" 2>/dev/null
trap 'echo' INT
echo "MARGIE command line on this computer | help shows how to run MARGIE | exit leaves"
while true; do
    if ! read -e -r -p "margie-cli $(basename "$PWD")> " line; then
        [ $? -gt 128 ] && continue  # Ctrl-C
        echo
        break
    fi
    [ -n "$line" ] && history -s -- "$line"
    eval "dispatch $line"
    [ $? -eq 255 ] && break
done
history -w "$HISTORY" 2>/dev/null
exit 0
