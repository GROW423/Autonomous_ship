content = open('/app/boat_connection.py').read()

if 'class SocketMavlink' not in content:
    insert_pos = content.find('class BoatConnection')
    socket_class = '''class SocketMavlink(mavutil.mavfile):
    """Wrap existing socket for pymavlink 2.4.49"""
    def __init__(self, sock, address, source_system=255, source_component=0):
        self._sock = sock
        mavutil.mavfile.__init__(self, sock.fileno(), address, source_system=source_system, source_component=source_component)
    def recv(self, n=None):
        if n is None:
            n = self.mav.bytes_needed()
        try:
            return self._sock.recv(n)
        except socket.error:
            return b''
    def write(self, buf):
        try:
            self._sock.send(buf)
        except socket.error:
            pass


'''
    content = content[:insert_pos] + socket_class + content[insert_pos:]

content = content.replace('self.mav = mavutil.mavfile(', 'self.mav = SocketMavlink(')

open('/app/boat_connection.py', 'w').write(content)
print('done')
print('has SocketMavlink class:', 'class SocketMavlink' in content)
print('has SocketMavlink call:', 'self.mav = SocketMavlink(' in content)
