#!/bin/bash

source .venv/bin/activate

# Because this would listen on port 500 (<1024) and open a socket for ESP, either run this as root, or give capabilities
# to the python binary in the venv (done in install_deps.sh)
python3 swu_emulator.py --config swu.yaml
