"""Build a private unpacked extension; never print the capture credential."""
import json
import shutil
from pathlib import Path
from config import BASE_DIR, OBSERVER_TOKEN
from observer_capture import capture_token


def main():
    if not OBSERVER_TOKEN:
        raise SystemExit('OBSERVER_TOKEN ausente: configure antes de instalar.')
    destination = BASE_DIR / 'data' / 'observer-extension'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'background.js', 'capture.js'):
        shutil.copyfile(BASE_DIR / 'observer' / 'extension' / name, destination / name)
    config = {'base': 'http://127.0.0.1:8766', 'token': capture_token(OBSERVER_TOKEN)}
    (destination / 'local-config.js').write_text(
        'const BLITZ_CAPTURE = Object.freeze(' + json.dumps(config) + ');\n', encoding='utf-8')
    print('Extensão privada preparada em: ' + str(destination))
    print('Não compartilhe essa pasta: contém credencial limitada à coleta.')


if __name__ == '__main__':
    main()
