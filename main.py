import os
import re
import json
import ctypes
import webview
import subprocess
from functools import cache
from urllib.parse import unquote
from threading import Thread as _Thread

import psutil
from WebLamp import Lamp
from WebLamp import Domain
from WebLamp import Connection

class Thread(_Thread):
    def kill(self):
        """This kills the Thread with an Exception"""
        thread_id = self.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')

PORT = 5000
html_header = ['Content-type: text/html']
domain = Domain(f'127.0.0.1:{PORT}')

if not os.path.exists('./config.json'):
    first_time = True
    config = {
        'osu_location': '',
        'last_server': ''
    }
else:
    first_time = False
    with open('./config.json', 'r') as f:
        config = json.loads(f.read())

@cache
def load_file(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()

# This renders all the css files for 
# the page
csspath = re.compile(r'^\/(?P<name>[a-zA-Z]*)\.css$')
@domain.add_route(path = csspath, method = ['GET'])
async def css_handler(con: Connection):
    name = con.args['name']
    return (200, load_file(f'./templates/{name}.css'))

# Method is `GET` because somewhere in WebLamp 0.3.0
# the parser breaks when you do a post request with html
# TODO: look into that
@domain.add_route(path = '/switch', method = ['GET'])
async def switch(con: Connection):
    # Check if osu is opened
    for process in psutil.process_iter():
        if 'osu!.exe' == process.name:
            # if osu is opened, we will close it
            process.kill()
    
    domain: str = unquote(con.params['domain'])
    if '.' not in domain:
        msg = 'Invaild domain!'
        return (301, b'', [f'Location: http://127.0.0.1:{PORT}/?msg={msg}']) 
    
    for x in ('https://', 'http://'):
        domain = domain.removeprefix(x)

    if '/' in domain:
        domain, = domain.split('/', 1)

    # open osu and switch servers!
    osu_location = config['osu_location']
    cmd = f'"{osu_location}" -devserver {domain}'
    subprocess.Popen(cmd, shell=True)

    msg = f'Currently on {domain}!'
    config['last_server'] = domain

    # redirct them back to the menu
    # and tell them that they are on a server!
    return (301, b'', [f'Location: http://127.0.0.1:{PORT}/?msg={msg}'])


@domain.add_route(path = '/', method = ['GET'])
async def main(con: Connection):
    html = load_file('./templates/index.html')
    if 'msg' in con.params:
        msg = unquote(con.params['msg']).encode()
    else:
        msg = b''
    
    html = html.replace(
        b'{{msg}}',
        msg
    )

    if config['last_server']:
        with open('./config.json', 'w+') as f:
            f.seek(0)
            f.truncate()
            f.write(json.dumps(config))
        last_server = config['last_server'].encode()
    else:
        last_server = b''

    html = html.replace(
        b'{{last_server}}',
        last_server
    )

    return (200, html, html_header)

server = Lamp()
server.add_domain(domain)

# Run the server in a new thread 
T = Thread(
    target = server.run, 
    kwargs = {'bind': ('127.0.0.1', PORT), 'debug': True}
)
T.start()

if first_time:
    from tkinter import Tk
    from tkinter import filedialog
    root = Tk()
    root.withdraw()

    config['osu_location'] = filedialog.askopenfilename(
        initialdir = "", title = "osu!.exe location.",
        filetypes = (("osu!", "osu!.exe"),)
    )

    with open('./config.json', 'w') as f:
        f.write(json.dumps(config))

# Create the window for our gui
webview.create_window(
    title = 'Server Switcher!', 
    url = f'http://127.0.0.1:{PORT}/',
    resizable = False,
    width = 300,
    height = 300
)
webview.start()

# once the user closes the window
# stop the event loop and close the thread
import asyncio
loop = asyncio.get_event_loop()
loop.stop()
loop.close()
T.kill()