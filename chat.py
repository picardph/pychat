import threading
import socket
import enum
import math


class ChatState(enum.Enum):
    idle = 0
    host_is_waiting = 1
    hosting = 2
    connected = 3


MESSAGE_START_TEXT = 0
MESSAGE_TEXT = 1
MESSAGE_REQUEST_USERNAME = 2
MESSAGE_USERNAME = 3


class Chat:
    def __init__(self, username, receive_callback, error_callback):
        self.__socket = None
        self.__client = None
        self.__ip = ''
        self.__port = 0
        self.__state = ChatState.idle
        self.__name = username
        self.__other_name = ''
        self.__callback = receive_callback
        self.__error = error_callback
        self.__thread = None
        self.__stop_event = threading.Event()

    def host(self, host, port):
        # The server must be running on a different thread to keep things responsive.
        self.__thread = threading.Thread(target=self.__run_host, args=(host, port)).start()

    def connect(self, host, port):
        self.__thread = threading.Thread(target=self.__run_client, args=(host, port)).start()

    def is_done(self):
        return self.__stop_event.is_set()

    def stop(self):
        self.__stop_event.set()

    def get_address(self):
        return self.__ip

    def get_port(self):
        return self.__port

    def get_state(self):
        return self.__state

    def get_username(self):
        return self.__name

    def get_connected_username(self):
        return self.__other_name

    def send_message(self, message):
        if self.__state == ChatState.hosting or self.__state == ChatState.connected:
            num = math.ceil(len(message) / 1023)
            if num > 255:
                raise RuntimeError('Message is to long to send.')

            # Send the start message to tell the client there is a text message coming
            # and how many packets to prepare for.
            start_msg = bytearray()
            start_msg.append(MESSAGE_START_TEXT)
            start_msg.append(num)
            self.__client.send(start_msg)

            for i in range(num):
                # If we are on the last message then there may not be
                # 1023 bytes remaining so we will just grab whatever is left.
                place = i * 1022
                msg = bytearray()
                msg.append(MESSAGE_TEXT)
                if i == num - 1:
                    msg += message[place:].encode()
                else:
                    msg += message[place:place + 1022].encode()
                msg += '\n'.encode()
                self.__client.send(msg)
        else:
            raise RuntimeError('Must be connected to send a message.')

    def __run_client(self, host, port):
        try:
            self.__state = ChatState.connected
            self.__ip = host
            self.__port = port

            try:
                self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__socket.settimeout(1)
                self.__socket.connect((host, port))
                # We use the same socket when we are not the host.
                self.__client = self.__socket
            except socket.error:
                raise RuntimeError('Failed to connect.')

            self.__listen()
        except Exception as e:
            self.__error(str(e))

    def __run_host(self, host, port):
        try:
            self.__state = ChatState.host_is_waiting
            self.__ip = host
            self.__port = port

            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.__socket.bind((host, port))
            self.__socket.settimeout(1)
            self.__socket.listen(1)

            self.__listen()
        except Exception as e:
            self.__error(str(e))

    def __listen(self):
        while not self.__stop_event.is_set():
            if self.__state == ChatState.host_is_waiting:
                # Unlike with the FTP project, the chat program can only have one
                # client at a time so it does not make sense to start a thread for
                # each client that connects. Instead I have a state machine and the program
                # switches states depending on if there is a client connected.
                try:
                    self.__client, address = self.__socket.accept()
                except socket.error:
                    continue

                self.__state = ChatState.hosting

                # Send the new client our username and request their username in response.
                data = bytearray()
                data.append(MESSAGE_REQUEST_USERNAME)
                data += self.__name.encode()
                self.__client.send(data)

            elif self.__state == ChatState.hosting or self.__state == ChatState.connected:
                data = bytearray()
                try:
                    data = bytearray(self.__client.recv(2))
                except socket.error:
                    continue

                if not data or len(data) == 0:
                    continue

                # The first byte will always be used to indicate
                # what kind of message was sent.
                if int(data[0]) == MESSAGE_START_TEXT:
                    # We support text messages of infinite length so this message will tell
                    # us how many more text messages are coming that will hold the final reassembled
                    # message. Well in theory it is not infinite. There are 1023 characters in each
                    # message (first byte is for message type) and only a 8-bit number is used to indicate
                    # the number of messages. So 1023 * 255 = 260865. 260,865 characters can be sent. I'm not
                    # going to allow more than one byte to hold the message number because then we
                    # need to deal with the endianess of the computers and I don't want to deal with that.
                    num = int(data[1])
                    message = ''
                    for i in range(num):
                        data = bytearray(self.__client.recv(1024))
                        if int(data[0]) != MESSAGE_TEXT:
                            raise RuntimeError('Expected a text-formatted message.')
                        message += data[1:].decode()
                    self.__callback(message)
                elif int(data[0]) == MESSAGE_USERNAME:
                    # Get the rest of the message.
                    data += self.__client.recv(1022)
                    # The other computer has sent us a username so lets remember it.
                    self.__other_name = data[1:].decode()
                elif int(data[0]) == MESSAGE_REQUEST_USERNAME:
                    # The other computer wants to know what our username is. It will also contain
                    # the username of that computer.
                    data += self.__client.recv(1022)
                    self.__other_name = data[1:].decode()
                    response_msg = bytearray()
                    response_msg.append(MESSAGE_USERNAME)
                    response_msg += self.__name.encode()
                    self.__client.send(response_msg)
                elif int(data[0]) == MESSAGE_TEXT:
                    raise RuntimeError('Expected a text message after a start-text message.')
        # Post chat clean up.
        if self.__client is not None:
            self.__client.close()
        if self.__socket is not None:
            self.__socket.close()
        self.__state = ChatState.idle
