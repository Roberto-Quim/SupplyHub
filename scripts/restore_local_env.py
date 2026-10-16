"""Restore the encrypted local environment with a separately transferred key."""
import argparse
from pathlib import Path
from cryptography.fernet import Fernet

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--key-file', type=Path, required=True)
parser.add_argument('--output', type=Path, default=Path('.env'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
plaintext = Fernet(args.key_file.read_bytes().strip()).decrypt(
    (root / 'config' / 'local-test.env.fernet').read_bytes()
)
# Exclusive creation prevents accidentally overwriting an existing environment.
with args.output.open('xb') as target:
    target.write(plaintext)
print(f'Configuracion restaurada en {args.output}. No publiques la llave ni el archivo restaurado.')
