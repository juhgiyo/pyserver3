#!/usr/bin/python
"""
@file async_tcp_client.py
@author Woong Gyu La a.k.a Chris. <juhgiyo@gmail.com>
        <http://github.com/juhgiyo/pyserver>
@date March 10, 2016
@brief AsyncTcpClient Interface
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

AsyncTcpClient Class.
"""
import asyncio
import socket
from collections import deque
import threading

from .async_controller import AsyncController
from .callback_interface import *
from .server_conf import *
# noinspection PyDeprecation
from .preamble import *
import traceback
'''
Interfaces
variables
- hostname
- port
- addr = (hostname,port)
- callback
functions
- def send(data)
- def close() # close the socket
'''


class AsyncTcpClient(asyncio.Protocol):
    def __init__(self, hostname, port, callback, no_delay=True):
        self.is_closing = False
        self.callback = None
        if callback is not None and isinstance(callback, ITcpSocketCallback):
            self.callback = callback
        else:
            raise Exception('callback is None or not an instance of ITcpSocketCallback class')
        self.hostname = hostname
        self.port = port
        self.addr = (hostname, port)
        self.send_queue = deque()  # thread-safe dequeue
        self.transport_dict = {'packet': None, 'type': PacketType.SIZE, 'size': SIZE_PACKET_LENGTH, 'offset': 0}
        
        self.recv_buffer=[]

        self.sock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if no_delay:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        err = None
        try:
            self.sock.connect((hostname, port))
            AsyncController.instance().add(self)
        except Exception as e:
            err = e
        finally:
            def callback_connection():
                if self.callback is not None:
                    self.callback.on_newconnection(self, err)

            thread = threading.Thread(target=callback_connection)
            thread.start()


        self.loop = asyncio.get_event_loop()
        coro = self.loop.create_connection(lambda: self, sock=self.sock)
        AsyncController.instance().pause()
        (self.transport,_)=self.loop.run_until_complete(coro)
        AsyncController.instance().resume()

    def connection_made(self, transport):
        self.transport=transport

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
            self.is_closing = True
            self.transport.close()
            AsyncTcpClient.instance().discard(self)
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
