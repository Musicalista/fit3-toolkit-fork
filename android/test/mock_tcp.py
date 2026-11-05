# SPDX-License-Identifier: Apache-2.0
"""mock_tcp.py: serves src/device/mock_watch.py's in-memory watch on a TCP port, one connection after another, for android/test/LinkTest.java."""
import os, socket, sys, threading
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(ROOT, "src", "device"))
import mock_watch
w = mock_watch.Watch(sys.argv[2] if len(sys.argv) > 2 else None); srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", int(sys.argv[1]))); srv.listen(4)
while True:
    c, _ = srv.accept(); threading.Thread(target=w.serve, args=(c,), daemon=True).start()
