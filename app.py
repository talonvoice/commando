from flask import Flask, render_template
from collections import OrderedDict, defaultdict
import json
import os
import socket
import string
import sys

py3 = sys.version_info[0] >= 3
if not py3:
    input = raw_input

app = Flask('voice')

def readall(s):
    text = []
    while True:
        j = json.loads(s.readline())
        if j['cmd'] == 'print':
            text.append(j['text'].rstrip('\n'))
        else:
            break
    return '\n'.join(text)

def repl_run(lines):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(os.path.expanduser('~/.talon/.sys/repl.sock'))
        if py3:
            sin = s.makefile('r', buffering=1, encoding='utf8')
        else:
            sin = s.makefile('r', bufsize=1)

        motd = readall(sin)

        responses = []
        for line in lines.split('\n'):
            m = {'cmd': 'input', 'text': line}
            s.send((json.dumps(m) + '\n').encode('utf8'))
            responses.append(readall(sin))
        s.shutdown(socket.SHUT_WR)
        s.shutdown(socket.SHUT_RD)
        return responses
    finally:
        try: s.close()
        except Exception: pass

FETCH_SCRIPT = r'''from collections import defaultdict
import json
try:
    from user import std
    alnum = std.alpha_alt
except Exception:
    alnum = []

response = {'contexts': {}}
response['alnum'] = alnum

for name, ctx in voice.talon.subs.items():
    d = response['contexts'][ctx.name] = {
        'active': ctx in voice.talon.active,
        'commands': [],
    }
    commands = d['commands']
    for trigger, rule in ctx.triggers.items():
        if trigger.split(' ')[-1] in alnum:
            continue
        actions = ctx.mapping[rule]
        if not isinstance(actions, (list, tuple)):
            actions = [actions]
        if len(actions) > 1 and all(isinstance(a, voice.Key) for a in actions):
            if len(set(a.data for a in actions)) == 1:
                commands.append((trigger, f'key({actions[0].data}) * {len(actions)}'))
                continue
        pretty = []
        for action in actions:
            if isinstance(action, voice.Key):
                keys = action.data.split(' ')
                if len(keys) > 1 and len(set(keys)) == 1:
                    pretty.append(f'key({keys[0]}) * {len(keys)}')
                else:
                    pretty.append(f'key({action.data})')
            elif isinstance(action, voice.Str):
                pretty.append(f'"{action.data}"')
            elif isinstance(action, voice.Rep):
                pretty.append(f'repeat({action.data})')
            elif isinstance(action, voice.RepPhrase):
                pretty.append(f'repeat_phrase({action.data})')
            elif isinstance(action, str):
                pretty.append(f'"{action}"')
            elif callable(action):
                pretty.append(f'{action.__name__}()')
            else:
                pretty.append(str(action))
        if len(pretty) == 1:
            pretty = pretty[0]
        commands.append((trigger, pretty))

print(json.dumps(response))
'''

def get_grammar():
    response = '\n'.join(repl_run(FETCH_SCRIPT))
    try:
        return json.loads(response)
    except ValueError:
        print(response)
        raise

replacements = {
    '(0 | 1 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 2 | 20 | 3 | 30 | 4 | 40 | 5 | 50 | 6 | 60 | 7 | 70 | 8 | 80 | 9 | 90 | oh)': '<number>',
}

def fixup(name, cmd):
    for a, b in replacements.items():
        name = name.replace(a, b)
    if isinstance(cmd, list):
        cmd = ', '.join(cmd)
    cmd = cmd.replace(a, b)
    return name, cmd

@app.route('/')
def slash():
    grammar = get_grammar()
    for name, ctx in grammar['contexts'].items():
        ctx['commands'] = [fixup(trigger, cmd)
                           for trigger, cmd in ctx['commands']]
    alpha = zip(grammar['alnum'], string.lowercase)
    return render_template('index.html', contexts=grammar['contexts'], alpha=alpha)

if __name__ == '__main__':
    app.run(port=6001, debug=True)
