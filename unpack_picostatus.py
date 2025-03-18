import re
import json

with open("inc/PicoStatus.h") as f:
    lines = f.read().split('typedef uint32_t PICO_INFO;')[1]

error_list = re.findall('PICO.*0x.*', lines)

error_string = 'ERROR_STRING = {\n'

for i in error_list:
    status = re.findall('PICO\S*', i)[0].replace('_',' ').capitalize()
    code = int(re.findall('0x.*L', i)[0][:-2], 16)
    error_string += f'\t{code}: "{status}",\n'

error_string += '}'

with open('picosdk_error_list.py', 'w') as f:
    f.write(error_string)
