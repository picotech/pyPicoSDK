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