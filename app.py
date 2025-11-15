from flask import Flask, render_template_string, session, request
from flask_socketio import SocketIO, emit
from pages import borah_cam, contact, home, visit, weather, gallery, facilities, seismic
import pty
import os
import select
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

home.register(app)
contact.register(app)
borah_cam.register(app)
visit.register(app)
weather.register(app)
gallery.register(app)
facilities.register(app)
seismic.register(app)

# Terminal storage
terminals = {}

# Terminal HTML template
TERMINAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Terminal</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: #000;
            font-family: monospace;
        }
        #terminal-container {
            width: 100%;
            height: calc(100vh - 40px);
        }
        h1 {
            color: #0f0;
            margin: 0 0 10px 0;
        }
    </style>
</head>
<body>
    <h1>Remote Terminal</h1>
    <div id="terminal-container"></div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    
    <script>
        const term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#ffffff'
            }
        });
        
        const fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        term.open(document.getElementById('terminal-container'));
        fitAddon.fit();
        
        const socket = io('/terminal');
        
        term.onData(data => {
            socket.emit('input', { data: data });
        });
        
        socket.on('output', (data) => {
            term.write(data.data);
        });
        
        window.addEventListener('resize', () => {
            fitAddon.fit();
            socket.emit('resize', {
                cols: term.cols,
                rows: term.rows
            });
        });
        
        socket.on('connect', () => {
            socket.emit('resize', {
                cols: term.cols,
                rows: term.rows
            });
        });
    </script>
</body>
</html>
"""

@app.route('/terminal')
def terminal():
    return render_template_string(TERMINAL_HTML)

def read_output(sid, fd):
    """Read output from terminal and send to browser"""
    while sid in terminals:
        try:
            timeout = 0.1
            (ready, _, _) = select.select([fd], [], [], timeout)
            if ready:
                output = os.read(fd, 1024)
                if output:
                    socketio.emit('output', 
                                {'data': output.decode('utf-8', errors='ignore')},
                                namespace='/terminal',
                                to=sid)
        except OSError:
            break

@socketio.on('connect', namespace='/terminal')
def handle_connect():
    """Start a new terminal session"""
    sid = request.sid
    
    # Create a pseudo-terminal
    master, slave = pty.openpty()
    
    # Start bash in the pseudo-terminal
    p = subprocess.Popen(
        ['/bin/bash'],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        preexec_fn=os.setsid
    )
    
    # Store terminal info
    terminals[sid] = {
        'fd': master,
        'process': p
    }
    
    # Start reading output in background
    socketio.start_background_task(read_output, sid, master)
    
    emit('output', {'data': 'Terminal connected. Type commands below:\r\n'})

@socketio.on('input', namespace='/terminal')
def handle_input(data):
    """Handle input from the browser"""
    sid = request.sid
    if sid in terminals:
        os.write(terminals[sid]['fd'], data['data'].encode())

@socketio.on('resize', namespace='/terminal')
def handle_resize(data):
    """Handle terminal resize"""
    sid = request.sid
    if sid in terminals:
        import fcntl
        import termios
        import struct
        
        fd = terminals[sid]['fd']
        winsize = struct.pack('HHHH', data['rows'], data['cols'], 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

@socketio.on('disconnect', namespace='/terminal')
def handle_disconnect():
    """Clean up terminal session"""
    sid = request.sid
    if sid in terminals:
        terminals[sid]['process'].kill()
        os.close(terminals[sid]['fd'])
        del terminals[sid]

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)
