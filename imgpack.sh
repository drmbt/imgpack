#!/bin/bash
python3 "$(dirname "$(readlink -f "$0")")/imgpack.py" "$@" 