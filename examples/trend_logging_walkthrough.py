"""Record measurement trends in-process and export them as CSV.

Uses the gateway's session layer directly (no server or browser needed):
a mock oscilloscope session polls measurements ~1x/second while a
subscriber is attached, records them into the session's trend recorder,
and the rows are exported to CSV at the end.

The same recorder powers the browser UI's Log tab and the
/api/sessions/{id}/scope/log.csv endpoint when running scpi-web.

Requirements: SCPI-Instrument-Control (core install; the session layer is
FastAPI-free)
"""

import csv
import time
from datetime import datetime

from scpi_control.server.sessions import InstrumentSession

RECORD_SECONDS = 5


def main() -> None:
    session = InstrumentSession.open("trend demo", mock=True)
    try:
        # The poll loop only runs while someone is listening (a browser tab,
        # or here: a trivial subscriber).
        unsubscribe = session.subscribe(lambda message: None)

        session.set_measurements([(1, "PKPK"), (1, "FREQ")])
        session.start_recording()
        print(f"Recording C1 PKPK + FREQ for {RECORD_SECONDS} s...")
        time.sleep(RECORD_SECONDS)
        status = session.stop_recording()
        unsubscribe()
        print(f"Recorded {status['row_count']} rows")

        rows = session.recorder.rows_since()
        columns = [f"C{c['channel']} {c['mtype']}" for c in status["columns"]]
        with open("trend_log.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", *columns])
            for row in rows:
                writer.writerow([datetime.fromtimestamp(row[0]).isoformat(), *row[1:]])
        print(f"Saved trend_log.csv ({len(rows)} rows x {len(columns)} measurements)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
