import os
import time  
import threading
import socket
import subprocess
import shlex
import sys
import pickle
import queue
import xml.etree.ElementTree as elt
from shutil import copyfile
from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler  
from pathlib import Path


def get_network_mask():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("8.8.8.8", 80))
    ip_addr = sock.getsockname()[0]
    ip_split = ip_addr.split('.')
    net_addr = ''
    for i in range(3):
        net_addr += ip_split[i] + '.'
    net_addr += '0/24'
    return net_addr


def get_connected_peers():
    args = shlex.split('nmap -oX ./ex.xml -p ' + str(PORT) +
                       ' ' + get_network_mask() + ' --open')
    subprocess.call(args)
    xml_content = elt.parse('ex.xml').getroot()
    for address in xml_content.iter('address'):
        PEERS_LIST.append(address.get('addr'))


class MyHandler(PatternMatchingEventHandler):
    def process(self, event):
        params = {}
        params.update({'dir': event.src_path})
        params.update({'isDir': event.is_directory})
        params.update({'flag': event.event_type})
        if event.event_type == 'moved':
            params.update({'dirMov': event.dest_path})
        print(event)
        if event.is_directory and event.event_type == 'modified':
            pass
        else:
            q.put(params)

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)
    
    def on_deleted(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)


def watcher():
    observer = Observer()
    observer.schedule(MyHandler(), DIRECTORY, True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


def client_thread(peer_ip):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((peer_ip, PORT))
    except socket.error as msg:
        pass

    while True:
        try:
            data = client_socket.recv(4096)
            if data:
                params = pickle.loads(data)
                client_socket.send('gracias'.encode('ascii'))
                if not params['isDir']:
                    if params['flag'] == 'created' or params['flag'] == 'modified':
                        with open(params['dir'], 'wb') as f:
                            while True:
                                data = client_socket.recv(1024)
                                if not data:
                                    break
                                f.write(data)
                        f.close()
                    elif params['flag'] == 'deleted':
                        os.remove(params['dir'])
                    else:
                        copyfile(params['dir'], params['dirMov'])
                        os.remove(params['dir'])
                else:
                    if params['flag'] == 'created':
                        os.makedirs(params['dir'])
                    elif params['flag'] == 'deleted':
                        os.rmdir(params['dir'])
                    else:
                        os.makedirs(params['dirMov'])
        except socket.error:
            client_socket.close()

    client_socket.close()


def listen_client(client_socket):
    while True:
        try:
            params = q.get()
            if params is None:
                pass
            else:
                client_socket.send(pickle.dumps(params))
                data = client_socket.recv(1024)

                if not params['isDir']:
                    if params['flag'] == 'created' or params['flag'] == 'modified':
                        f = open(params['dir'],'rb')
                        l = f.read(1024)
                        while (l):
                            client_socket.send(l)
                            l = f.read(1024)
                        f.close()
        except socket.error:
            pass


def server_thread(peers):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((HOST, PORT))
    except socket.error as msg:
        print(msg)
    server_socket.listen(10)
    while 1:
        connection, address = server_socket.accept()
        if address[0] not in peers:
            CLIENT_THREADS.append(threading.Thread(
                target=client_thread, args=(address[0], )).start())
        CONNECTION_THREADS.append(threading.Thread(
            target=listen_client, args=(connection,)).start())

    server_socket.close()


if __name__ == '__main__':
    DIRECTORY = str(Path.home()) + '/p2pSync'

    if not os.path.exists(DIRECTORY):
        os.makedirs(DIRECTORY)
    
    HOST = ''
    PORT = 8891
    PEERS_LIST = []
    CONNECTION_THREADS = []
    CLIENT_THREADS = []

    q = queue.Queue()
    
    get_connected_peers()

    threading.Thread(target=watcher, args=( )).start()
    threading.Thread(target=server_thread, args=(PEERS_LIST, )).start()

    for peer in PEERS_LIST:
        CLIENT_THREADS.append(threading.Thread(target=client_thread, args=(peer, )).start())
