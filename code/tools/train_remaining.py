"""Run remaining knowledge domains through cortex training."""
import subprocess
import sys
import os

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
domains = ['engineering', 'gamedev', 'programming']

for d in domains:
    print(f'\n=== Starting {d} ===')
    subprocess.run([
        sys.executable, 'tools/train_system_knowledge.py',
        d, '--batch-size', '50', '--delay', '2.0', '--resume'
    ])
    print(f'=== {d} done ===')

print('\nALL DOMAINS COMPLETE')
