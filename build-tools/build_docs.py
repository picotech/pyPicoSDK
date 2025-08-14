"""
This file copies duplicate .md files in docs from one scope to multiple scopes, 
    replacing the mkdocstrings reference to the new scope.

i.e. copy_dir is psospa, paste_dir_list includes ps6000a, 
    ref/psospa/run.md will be copied to ref/ps6000a/run.md automatically replacing
    :::pypicosdk.pypicosdk.psospa to :::pypicosdk.pypicosdk.ps6000a
"""

import os

if not os.path.exists('docs'):
    raise FileNotFoundError('docs/ does not exist in this directory')

ref_dir = 'docs/docs/ref/'
copy_dir = 'psospa'
paste_dir_list = [
    'ps6000a'
]

file_list = [
    'buffers.md',
    'captures.md', 
    'channel.md',
    'conversions.md',
    'digital.md',
    'firmware.md',
    'retrieval.md',
    'run.md',
    'setup.md',
    'siggen.md',
    'trigger.md',
]

for paste_dir in paste_dir_list:
    for f in file_list:
        copy_fp = os.path.join(ref_dir, copy_dir, f)
        paste_fp = os.path.join(ref_dir, paste_dir, f)
        with open(copy_fp) as f: text = f.read()
        with open(paste_fp, 'w') as f: f.write(text.replace(copy_dir, paste_dir))