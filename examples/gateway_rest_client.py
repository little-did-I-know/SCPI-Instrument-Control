"""Drive the web gateway's REST API from Python — no browser needed.

Start the gateway first (in another terminal):

    pip install "SCPI-Instrument-Control[web]"
    scpi-web            # prints the gateway's URL on every start

Every gateway request needs a bearer token. People sign in with an invitation
(`scpi-web invite <name>`), but a script wants a credential it can keep, so
mint one by hand and export it before running this:

    scpi-web token add rest-demo     # prints the token once
    export SCPI_WEB_TOKEN=scpi_...   # the token it printed

Then run this script. It creates a hardware-free mock session, configures a
channel, fetches full-resolution waveform data as JSON, and downloads a
screenshot PNG — the same API the browser UI uses.

Requirements:
    - SCPI-Instrument-Control[web] (for the gateway itself)
    - Python standard library only for this client (urllib)

Not executed in CI: needs a running `scpi-web` gateway, not merely an
instrument. It is compile-checked only -- start the gateway and run it by
hand after changes.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional, Union

BASE = "http://127.0.0.1:8765/api"

# The gateway authenticates every /api/* request with a bearer token. Read it
# from the environment rather than hard-coding a credential in the script.
TOKEN = os.environ.get("SCPI_WEB_TOKEN")

Body = Optional[Union[dict, list]]  # examples run on the package floor, Python 3.9


def call(method: str, path: str, body: Body = None) -> bytes:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if TOKEN:
        request.add_header("Authorization", "Bearer {0}".format(TOKEN))
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        return response.read()


def call_json(method: str, path: str, body: Body = None):
    return json.loads(call(method, path, body))


def main() -> None:
    if not TOKEN:
        sys.exit("Set SCPI_WEB_TOKEN first — run 'scpi-web token add rest-demo' and export the token it prints.")

    # 1. Create a mock oscilloscope session (no hardware required)
    session = call_json("POST", "/sessions", {"mock": True, "label": "REST demo"})
    session_id = session["id"]
    print(f"Session {session_id}: {session['model']} ({session['dialect']} dialect)")

    scope = f"/sessions/{session_id}/scope"
    try:
        # 2. Configure channel 1 and read the full state snapshot back
        state = call_json("PATCH", f"{scope}/channels/1", {"enabled": True, "voltage_scale": 0.5})
        print(f"Timebase: {state['timebase']} s/div, C1 scale: {state['channels']['1']['voltage_scale']} V/div")

        # 3. Fetch full-resolution waveform data as JSON
        waveform = call_json("GET", f"{scope}/waveform?channels=1&max_points=16")
        channel = waveform["channels"][0]
        print(f"Waveform C{channel['channel']}: {len(channel['points'])} points, dt={channel['dt']:.2e} s")

        # 4. Download the instrument screenshot
        png = call("GET", f"{scope}/screenshot.png")
        with open("gateway_screenshot.png", "wb") as f:
            f.write(png)
        print(f"Saved gateway_screenshot.png ({len(png)} bytes)")

        # 5. Send a raw SCPI query through the terminal endpoint
        reply = call_json("POST", f"{scope}/command", {"command": "*IDN?"})
        print(f"*IDN? -> {reply['response']}")
    finally:
        call("DELETE", f"/sessions/{session_id}")
        print("Session closed.")


if __name__ == "__main__":
    main()
