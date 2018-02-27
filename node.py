import os
import time  
import threading
import socket
import sys
import pickle
import queue
import xml.etree.ElementTree as elt
from shutil import copyfile
from watchdog.observers import Observer  
from watchdog.events import PatternMatchingEventHandler  
from pathlib import Path


def getIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def peers_server():
    global PEERS_LIST
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(('172.31.99.18', 8888))
    except socket.error as msg:
        print(msg)
    client_socket.send('request'.encode('ascii'))
    data = client_socket.recv(1024)
    if data:
        PEERS_LIST = pickle.loads(data)


def get_connected_peers():
    t1 = threading.Thread(target=peers_server, args=( ))
    t1.start()
    t1.join()
    ip = getIP()
    if ip in PEERS_LIST:
        PEERS_LIST.remove(ip)


class MyHandler(PatternMatchingEventHandler):
    def process(self, event):
        if event.is_directory and event.event_type == 'modified':
            pass
        else:
            params = {}
            path = event.src_path.replace(DIRECTORY,'')
            fname = os.path.basename(event.src_path)
            pr = fname.split('-')
            if pr[0] != 'ps':
                params.update({'dir': path})
                params.update({'isDir': event.is_directory})
                params.update({'flag': event.event_type})
                if event.event_type == 'moved':
                    pathm = event.dest_path.replace(DIRECTORY,'')
                    params.update({'dirMov': pathm})
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


def send_client(client_socket):
    while True:
        try:
            params = q.get()
            if params is None:
                pass
            else:
                print('send')
                print(params)
                direct = params['dir']
                params['dir'] = 'ps-' + params['dir']
                client_socket.send(pickle.dumps(params))
                if not params['isDir']:
                    if params['flag'] == 'created' or params['flag'] == 'modified':
                        with open(DIRECTORY + direct, 'rb') as fs:
                            client_socket.send(b'BEGIN')
                            while True:
                                data = fs.read(1024)
                                client_socket.send(data)
                                if not data:
                                    break
                            client_socket.send(b'ENDED')
                            fs.close()
        except Exception as msg:
            print(msg)


def listen_client(client_socket):
    while True:
        try:
            data = client_socket.recv(4096)
            if data:
                print('listen')
                params = pickle.loads(data)
                print(params)
                client_socket.send('gracias'.encode('ascii'))
                if not params['isDir']:
                    if params['flag'] == 'created' or params['flag'] == 'modified':
                        with open(DIRECTORY + params['dir'], "wb") as fw:
                            while True:
                                data = client_socket.recv(32)
                                if data == b'BEGIN':
                                    continue
                                elif data == b'ENDED':
                                    break
                                else:
                                    fw.write(data)
                            fw.close()
                    elif params['flag'] == 'deleted':
                        os.remove(DIRECTORY + params['dir'])
                    else:
                        copyfile(DIRECTORY + params['dir'], DIRECTORY + params['dirMov'])
                        os.remove(DIRECTORY + params['dir'])
                else:
                    if params['flag'] == 'created':
                        os.makedirs(DIRECTORY + params['dir'])
                    elif params['flag'] == 'deleted':
                        os.rmdir(DIRECTORY + params['dir'])
                    else:
                        os.makedirs(DIRECTORY + params['dirMov'])
        except Exception as msg:
            print(msg)


def client_thread(peer_ip):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        client_socket.connect((peer_ip, PORT))
    except socket.error as msg:
        print(msg)

    threading.Thread(target=send_client, args=(client_socket,)).start()
    threading.Thread(target=listen_client, args=(client_socket,)).start()


def server_thread(peers):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((HOST, PORT))
    except socket.error as msg:
        print(msg)
    server_socket.listen(10)
    print('Servidor Iniciado')
    while 1:
        connection, address = server_socket.accept()
        if address[0] not in peers:
            threading.Thread(target=send_client, args=(connection,)).start()
            threading.Thread(target=listen_client, args=(connection,)).start()

    server_socket.close()


if __name__ == '__main__':
    DIRECTORY = str(Path.home()) + '/p2pSync/'

    if not os.path.exists(DIRECTORY):
        os.makedirs(DIRECTORY)
    
    HOST = ''
    PORT = 8883
    PEERS_LIST = []

    q = queue.Queue()

    get_connected_peers()
    print(PEERS_LIST)

    threading.Thread(target=watcher, args=( )).start()
    thread = threading.Thread(target=server_thread, args=(PEERS_LIST, ))
    thread.daemon=True
    thread.start()

    for peer in PEERS_LIST:
        thread = threading.Thread(target=client_thread, args=(peer, ))
        thread.daemon=True
        thread.start()
