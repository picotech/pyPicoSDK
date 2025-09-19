"""
Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms.

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
copy_dir = 'psospa' # Main copy dir (truth source)

# Paste directory list with an exclude for certain files
paste_dir_list = [
    {'name': 'ps6000a', 'exclude': ['led.md',]}
]

# List of files to copy from copy_dir to paste_dir
file_list = [
    # 'init.md', Do not include init.md
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
    'led.md',
]

# Report any files that aren't included for info
all_files = os.listdir(os.path.join(ref_dir, copy_dir))
missing_files = [f for f in all_files if f not in file_list]
print('Files not included in copy:', missing_files)

# Copy each file to each paste_dir 
for paste_dir_dict in paste_dir_list:
    paste_dir = paste_dir_dict['name']
    exclude_list = paste_dir_dict['exclude']
    for f in file_list:
        if f in exclude_list:
            continue
        copy_fp = os.path.join(ref_dir, copy_dir, f)
        paste_fp = os.path.join(ref_dir, paste_dir, f)
        print(f'Copying {f} to {paste_fp}')
        with open(copy_fp) as f: text = f.read()
        with open(paste_fp, 'w') as f: f.write(text.replace(copy_dir, paste_dir))