#!/usr/bin/python
"""
@file async_tcp_server.py
@author Woong Gyu La a.k.a Chris. <juhgiyo@gmail.com>
        <http://github.com/juhgiyo/pyserver>
@date March 10, 2016
@brief AsyncTcpServer Interface
@version 0.1

@section LICENSE

The MIT License (MIT)

Copyright (c) 2016 Woong Gyu La <juhgiyo@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

@section DESCRIPTION

AsyncTcpServer Class.
"""
import asyncio
import socket
import threading
from collections import deque

from .async_controller import AsyncController
from .callback_interface import *
from .server_conf import *
from .preamble import *
# noinspection PyDeprecation
import traceback
import copy

'''
Interfaces
variable
- addr
- callback
function
- def send(data)
- def close() # close the socket
'''


class AsyncTcpSocket(asyncio.Protocol):
    def __init__(self, server, transport, addr, callback):
        self.server = server
        self.is_closing = False
        self.callback = None
        if callback is not None and isinstance(callback, ITcpSocketCallback):
            self.callback = callback
        else:
            raise Exception('callback is None or not an instance of ITcpSocketCallback class')
        self.sock = transport.get_extra_info('socket')
        self.addr = addr
        self.transport=transport
        self.recv_buffer=[]
        self.transport_dict = {'packet': None, 'type': PacketType.SIZE, 'size': SIZE_PACKET_LENGTH, 'offset': 0}
        self.send_queue = deque()  # thread-safe queue
        if self.server.no_delay:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        AsyncController.instance().add(self)
        if callback is not None:
            self.callback.on_newconnection(self, None)

    def data_received(self, data):
        try:
            if data is None or len(data) == 0:
                return

            self.recv_buffer.concat(data)
            data = self.recv_buffer[:self.transport_dict['size']]
            self.recv_buffer=self.recv_buffer[self.transport_dict['size']:]

            if self.transport_dict['packet'] is None:
                self.transport_dict['packet'] = data
            else:
                self.transport_dict['packet'] += data
            read_size = len(data)
            if read_size < self.transport_dict['size']:
                self.transport_dict['offset'] += read_size
                self.transport_dict['size'] -= read_size
            else:
                if self.transport_dict['type'] == PacketType.SIZE:
                    should_receive = Preamble.to_should_receive(self.transport_dict['packet'])
                    if should_receive < 0:
                        preamble_offset = Preamble.check_preamble(self.transport_dict['packet'])
                        self.transport_dict['offset'] = len(self.transport_dict['packet']) - preamble_offset
                        self.transport_dict['size'] = preamble_offset
                        # self.transport_dict['packet'] = self.transport_dict['packet'][
                        #                           len(self.transport_dict['packet']) - preamble_offset:]
                        self.transport_dict['packet'] = self.transport_dict['packet'][preamble_offset:]
                        return
                    self.transport_dict = {'packet': None, 'type': PacketType.DATA, 'size': should_receive, 'offset': 0}
                else:
                    receive_packet = self.transport_dict
                    self.transport_dict = {'packet': None, 'type': PacketType.SIZE, 'size': SIZE_PACKET_LENGTH, 'offset': 0}
                    self.callback.on_received(self, receive_packet['packet'])
        except Exception as e:
            print(e)
            traceback.print_exc()

    def connection_lost(self, exc):
        self.close()

    def close(self):
        if not self.is_closing:
            self.handle_close()

    def error_received(self, exc):
        if not self.is_closing:
            self.handle_close()

    def handle_close(self):
        try:
            print('asyncTcpSocket close called')
            self.is_closing = True
            self.transport.close()
            self.server.discard_socket(self)
            AsyncController.instance().discard(self)
            if self.callback is not None:
                self.callback.on_disconnect(self)
        except Exception as e:
            print(e)
            traceback.print_exc()

    def send(self, data):
        state = State.SUCCESS
        self.transport.write({'data': Preamble.to_preamble_packet(len(data)) + data, 'offset': 0})
        try:
            if self.callback is not None:
                self.callback.on_sent(self, state, data)
        except Exception as e:
            print(e)
            traceback.print_exc()

    def gethostbyname(self, arg):
        return self.sock.gethostbyname(arg)

    def gethostname(self):
        return self.sock.gethostname()


'''
Interfaces
variables
- callback
- acceptor
functions
- def close() # close the socket
- def getSockList()
- def shutdownAllClient()
'''


class AsyncTcpServer(asyncio.Protocol):
    def __init__(self, port, callback, acceptor, bind_addr='', no_delay=True):
        self.is_closing = False
        self.lock = threading.RLock()
        self.sock_set = set([])

        self.acceptor = None
        if acceptor is not None and isinstance(acceptor, IAcceptor):
            self.acceptor = acceptor
        else:
            raise Exception('acceptor is None or not an instance of IAcceptor class')
        self.callback = None
        if callback is not None and isinstance(callback, ITcpServerCallback):
            self.callback = callback
        else:
            raise Exception('callback is None or not an instance of ITcpServerCallback class')

        self.port = port
        self.no_delay = no_delay

        self.sock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.sock.bind((bind_addr, port))
        self.sock.listen(5)

        AsyncController.instance().add(self)
        
        self.loop = asyncio.get_event_loop()
        #coro = self.loop.create_server(lambda: self, sock=self.sock)
        #(self.server,_)=self.loop.run_until_complete(coro)
        self.server = self.loop.create_server(lambda: self, sock=self.sock)

        if self.callback is not None:
            self.callback.on_started(self)

    def connection_made(self, transport):
        try:
            if transport is not None:
                addr = transport.get_extra_info('peername')
                if not self.acceptor.on_accept(self, addr):
                    transport.close()
                else:
                    sockcallback = self.acceptor.get_socket_callback()
                    sock_obj = AsyncTcpSocket(self, transport, addr, sockcallback)
                    with self.lock:
                        self.sock_set.add(sock_obj)
                    if self.callback is not None:
                        self.callback.on_accepted(self, sock_obj)
        except Exception as e:
            print(e)
            traceback.print_exc()


    def close(self):
        if not self.is_closing:
            self.handle_close()

    def error_received(self, exc):
        if not self.is_closing:
            self.handle_close()

    def handle_close(self):
        try:
            print('asyncTcpServer close called')
            self.is_closing = True
            with self.lock:
                delete_set = copy.copy(self.sock_set)
                for item in delete_set:
                    item.close()
                self.sock_set = set([])
            self.server.close()
            AsyncController.instance().discard(self)
            if self.callback is not None:
                self.callback.on_stopped(self)
        except Exception as e:
            print(e)
            traceback.print_exc()

    def discard_socket(self, sock):
        print('asyncTcpServer discard socket called')
        with self.lock:
            self.sock_set.discard(sock)

    def shutdown_all(self):
        with self.lock:
            delete_set = copy.copy(self.sock_set)
            for item in delete_set:
                item.close()
            self.sock_set = set([])

    def get_socket_list(self):
        with self.lock:
            return list(self.sock_set)
