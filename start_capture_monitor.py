"""Launch the local telemetry worker without exposing its credential in argv."""
import os
import subprocess
from config import BASE_DIR, OBSERVER_TOKEN
from observer_capture import capture_token


def main():
    if not OBSERVER_TOKEN:
        raise SystemExit('OBSERVER_TOKEN required')
    environment = os.environ.copy()
    environment['BLITZ_CAPTURE_TOKEN'] = capture_token(OBSERVER_TOKEN)
    directory = BASE_DIR / 'data'
    directory.mkdir(exist_ok=True)
    with (directory / 'capture-monitor-process.log').open('ab') as output:
        child = subprocess.Popen(['node', str(BASE_DIR / 'observer' / 'monitor.mjs')],
            cwd=BASE_DIR, env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt')
    print('Monitor PID:', child.pid)


if __name__ == '__main__':
    main()
