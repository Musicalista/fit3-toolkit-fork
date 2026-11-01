# SPDX-License-Identifier: Apache-2.0
# source this: points at the local Ghidra and JDK 21 under local/tools (see src/re/README.md)
RE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export JAVA_HOME="$(ls -d "$RE_ROOT"/local/tools/jdk-25* | head -1)"
export GHIDRA_INSTALL_DIR="$(ls -d "$RE_ROOT"/local/tools/ghidra_* | head -1)"
export PATH="$JAVA_HOME/bin:$PATH"
export RE_OUT="$RE_ROOT/local/re"
