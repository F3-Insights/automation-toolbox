#!/bin/sh
# Build the merged agents and skills folder from this checkout. See setup/link.py --help.
exec python3 "$(dirname "$0")/link.py" "$@"
