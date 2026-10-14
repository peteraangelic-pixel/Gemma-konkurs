Third run of the V6.4 raw-call diagnosis: verify what happened in the four locator-trap sessions.

fastapi_15588, fastapi_15745, rich_3043 and httpx_3672 each call write_file with
filepath=/tmp/locate.py. V6.6 documents them as sessions that wrote the script and then treated it
as the work, but the harness refuses writes outside the workspace root, so the real sequence is
probably a refused write followed by an early end. This run prints the observation of every write
outside the repository root, adds a counter for them, and extends FOCUS to those four tasks plus
the remaining N-bucket sessions.
