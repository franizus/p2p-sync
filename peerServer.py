import socket
import sys
import threading
import select
import pickle


def listen_client(client_socket):
    try:
        data = client_socket.recv(1024).decode('ascii')
        if data:
            client_socket.send(pickle.dumps(list(set(PEER_LIST))))
    except socket.error as msg:
        print(msg)
        client_socket.close()


if __name__ == "__main__":
    HOST = ''
    PORT = 8888
    CONNECTION_LIST = []
    PEER_LIST = []
    SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        SERVER_SOCKET.bind((HOST, PORT))
    except socket.error as msg:
        print(msg)

    SERVER_SOCKET.listen(10)
    CONNECTION_LIST.append(SERVER_SOCKET)

    while 1:
        READ_SOCKETS, WRITE_SOCKETS, ERROR_SOCKETS = select.select(
            CONNECTION_LIST, [], [])
        for socket in READ_SOCKETS:
            if socket == SERVER_SOCKET:
                connection, address = SERVER_SOCKET.accept()
                CONNECTION_LIST.append(connection)
                PEER_LIST.append(address[0])
                threading.Thread(target=listen_client, args=(connection, )).start()

    SERVER_SOCKET.close()