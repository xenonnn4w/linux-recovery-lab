#!/usr/bin/env python3
"""Deploy, break, diagnose, recover, and remove an isolated Linux service."""
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'linux-recovery-lab-node'
IMAGE = 'linux-recovery-lab:local'
LABEL = 'io.xenonnn4w.lab=linux-recovery'


def run(*args, check=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=180)
    if check and result.returncode:
        raise RuntimeError(f'{args}: {result.stderr or result.stdout}')
    return {'code': result.returncode, 'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip()}


def execute(command, check=True):
    return run('docker', 'exec', '--user', '0', NAME, 'sh', '-c', command, check=check)


def owned():
    result = run('docker', 'inspect', '--format',
                 '{{index .Config.Labels "io.xenonnn4w.lab"}}', NAME, check=False)
    return result['code'] == 0 and result['stdout'] == 'linux-recovery'


def down():
    if owned():
        run('docker', 'rm', '-f', NAME)


def up():
    if run('docker', 'inspect', NAME, check=False)['code'] == 0:
        raise RuntimeError('Container already exists; run down first (only lab-owned resources removed).')
    run('docker', 'build', '-f', str(ROOT / 'Containerfile'), '-t', IMAGE, str(ROOT))
    run('docker', 'run', '-d', '--name', NAME, '--label', LABEL,
        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--memory', '96m', '--cpus', '0.5',
        '--pids-limit', '64', '--tmpfs', '/etc/lab:rw,size=1m,mode=777',
        '--tmpfs', '/var/lib/lab:rw,size=1m,mode=777', IMAGE)
    try:
        execute("printf '%s' '{\"message\":\"ready\"}' > /etc/lab/config.json; chmod 644 /etc/lab/config.json")
        wait_healthy()
    except BaseException:
        down()
        raise


def probe():
    return run('docker', 'exec', NAME, 'curl', '-sS', '--max-time', '2',
               '-w', '\n%{http_code}', 'http://127.0.0.1:8080/', check=False)


def healthy(result):
    return result['code'] == 0 and result['stdout'].endswith('\n200')


def wait_healthy():
    for _ in range(40):
        result = probe()
        if healthy(result):
            return result
        time.sleep(0.15)
    raise RuntimeError(f'Service did not recover: {result}')


FAULTS = {
    'configuration': ("printf '%s' '{\"message\":\"broken\"}' > /etc/lab/config.json",
                      "printf '%s' '{\"message\":\"ready\"}' > /etc/lab/config.json", 'invalid message'),
    'permissions': ('chmod 600 /etc/lab/config.json', 'chmod 644 /etc/lab/config.json', 'Permission denied'),
    'storage': ('rm -f /var/lib/lab/probe; dd if=/dev/zero of=/var/lib/lab/fill bs=4096 count=512',
                'rm -f /var/lib/lab/fill', 'No space left'),
    'service': (None, None, None),
}


def diagnose():
    return {
        'container': run('docker', 'inspect', '--format', '{{json .State}}', NAME, check=False),
        'logs': run('docker', 'logs', '--tail', '15', NAME, check=False),
        'filesystem': execute('df -h /var/lib/lab; ls -ln /etc/lab; cat /etc/lab/config.json', check=False),
    }


def scenario(name):
    before = wait_healthy()
    inject, repair, expected = FAULTS[name]
    started = time.monotonic()
    try:
        injection = (run('docker', 'stop', '-t', '1', NAME) if name == 'service'
                     else execute(inject, check=name != 'storage'))
        failed = probe()
        evidence = diagnose()
        if healthy(failed):
            raise AssertionError(f'{name}: injected fault was not detected')
        if expected and expected not in failed['stdout']:
            raise AssertionError(f'{name}: unexpected failure: {failed}')
    finally:
        if name == 'service':
            run('docker', 'start', NAME)
            execute("printf '%s' '{\"message\":\"ready\"}' > /etc/lab/config.json; chmod 644 /etc/lab/config.json")
        else:
            execute(repair)
    recovered = wait_healthy()
    return {'scenario': name, 'baseline': before, 'injection': injection,
            'failure': failed, 'diagnostics': evidence, 'recovered': recovered,
            'elapsed_seconds': round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['up', 'down', 'check', 'test'])
    args = parser.parse_args()
    if args.action == 'down':
        down()
    elif args.action == 'up':
        up()
    elif args.action == 'check':
        print(json.dumps({'probe': probe(), 'diagnostics': diagnose()}, indent=2))
    else:
        up()
        try:
            results = [scenario(name) for name in FAULTS]
            output = ROOT / 'evidence'
            output.mkdir(exist_ok=True)
            report = {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
                      'environment': 'Docker Linux containers; synthetic faults', 'scenarios': results}
            (output / 'latest.json').write_text(json.dumps(report, indent=2) + '\n')
            print(f'PASS: {len(results)} faults detected and recovered; evidence/latest.json')
        finally:
            down()


if __name__ == '__main__':
    main()
