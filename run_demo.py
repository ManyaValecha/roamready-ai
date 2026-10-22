"""Start the RoamReady AI MCP server (:8765) and the Alexa+ simulator (:8770) together. Ctrl+C stops both."""
import os
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
procs = [subprocess.Popen([sys.executable, "-m", "trip_scout.server"], cwd=HERE),
         subprocess.Popen([sys.executable, "-m", "web.app"], cwd=HERE)]
time.sleep(3)
print("\nRoamReady MCP server  : http://127.0.0.1:8765/mcp\nAlexa+ simulator      : http://127.0.0.1:8770\n")
if "--no-browser" not in sys.argv:
    webbrowser.open("http://127.0.0.1:8770")
try:
    while all(p.poll() is None for p in procs):
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        p.terminate()