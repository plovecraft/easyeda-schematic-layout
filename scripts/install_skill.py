#!/usr/bin/env python3
"""Checksum-checked local skill installation; no network or overwrite."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys

NAME='schematic-layout-optimizer'


def verify(source):
    manifest=source/'CHECKSUMS.sha256'
    if not manifest.is_file():
        raise ValueError('CHECKSUMS.sha256 is missing; use a complete release package')
    files={}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest,relative=line.split('  ',1)
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Invalid checksum path: '+relative)
        file=(source/relative).resolve()
        if not file.is_relative_to(source.resolve()) or relative in files:
            raise ValueError('Invalid checksum path: '+relative)
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Checksum mismatch: '+relative)
        files[relative]=file
    if 'SKILL.md' not in files or 'scripts/layout.py' not in files:
        raise ValueError('Incomplete skill manifest')
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest',type=Path,help='Parent skills directory; defaults to CODEX_HOME/skills')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    files=verify(source)
    if args.check_only:
        print('Checksums OK:',len(files),'files');return 0
    codex_root=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
    parent=(args.dest or codex_root/'skills').expanduser().resolve()
    target=parent/NAME
    if target.exists():
        raise ValueError('Destination already exists; preserved unchanged: '+str(target))
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Source and destination may not contain one another')
    parent.mkdir(parents=True,exist_ok=True);target.mkdir()
    for relative,file in files.items():
        output=target/relative;output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(file,output)
    shutil.copy2(source/'CHECKSUMS.sha256',target/'CHECKSUMS.sha256')
    verify(target)
    print('Installed:',target)
    print('Invoke $'+NAME+' on your next turn; reload the client if discovery has not refreshed.')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(2)
