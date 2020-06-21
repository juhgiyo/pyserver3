#!/usr/bin/python
"""
@file async_udp.py
@author Woong Gyu La a.k.a Chris. <juhgiyo@gmail.com>
        <http://github.com/juhgiyo/pyserver>
@date March 10, 2016
@brief AsyncUDP Interface
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

AsyncUDP Class.
"""
import queue
import asyncio
import socket
import traceback
from .callback_interface import *
from .server_conf import *
from .async_controller import AsyncController

IP_MTU_DISCOVER = 10
IP_PMTUDISC_DONT = 0  # Never send DF frames.
IP_PMTUDISC_WANT = 1  # Use per route hints.
IP_PMTUDISC_DO = 2  # Always DF.
IP_PMTUDISC_PROBE = 3  # Ignore dst pmtu.

'''
Interfaces
variables
- callback
functions
- def send(host,port,data)
- def close() # close the socket
'''


class AsyncUDP(asyncio.Protocol):
    def __init__(self, port, callback, bindaddress=''):
        # self.lock = threading.RLock()
        self.MAX_MTU = 1500
        self.callback = None
        self.port = port
        if callback is not None and isinstance(callback, IUdpCallback):
            self.callback = callback
        else:
            raise Exception('callback is None or not an instance of IUdpCallback class')
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((bindaddress, port))
        except Exception as e:
            print(e)
            traceback.print_exc()
        
        self.transport=None
        AsyncController.instance().add(self)
        if self.callback is not None:
            self.callback.on_started(self)

        self.loop = asyncio.get_event_loop()
        coro = self.loop.create_datagram_endpoint(lambda: self, sock=self.sock)
        AsyncController.instance().pause()
        (self.transport,_)=self.loop.run_until_complete(coro)
        AsyncController.instance().resume()

  # Even though UDP is connectionless this is called when it binds to a port
    def connection_made(self, transport):
        self.transport=transport

    # This is called everytime there is something to read
    def data_received(self, data, addr):
        try:
            if data and self.callback_obj is not None:
                self.callback_obj.on_received(self, addr, data)
        except Exception as e:
            print(e)
            traceback.print_exc()

    def connection_lost(self, exc):
        self.close()

    def close(self):
        self.handle_close()

    def error_received(self, exc):
        self.handle_close()


    def handle_close(self):
        print('asyncUdp close called')
        self.transport.close()
        AsyncController.instance().discard(self)
        try:
            if self.callback is not None:
                self.callback.on_stopped(self)
        except Exception as e:
            print(e)
            traceback.print_exc()

    # noinspection PyMethodOverriding
    def send(self, hostname, port, data):
        if len(data) <= self.MAX_MTU:
            self.transport.sendto(data,(hostname,port))
        else:
            raise ValueError("The data size is too large")

    def gethostbyname(self, arg):
        return self.sock.gethostbyname(arg)

    def gethostname(self):
        return self.sock.gethostname()

    def get_mtu_size(self):
        return self.MAX_MTU

    def check_mtu_size(self, hostname, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((hostname, port))
        s.setsockopt(socket.IPPROTO_IP, IP_MTU_DISCOVER, IP_PMTUDISC_DO)

        max_mtu = self.MAX_MTU
        try:
            s.send('#' * max_mtu)
        except socket.error:
            option = self.sock.getsockopt(socket.IPPROTO_IP, 'IP_MTU', 14)
            max_mtu = s.getsockopt(socket.IPPROTO_IP, option)
        return max_mtu

# Echo udp server test
# def readHandle(sock,addr, data):
#   sock.send(addr[0],addr[1],data)
# server=AsyncUDP(5005,readHandle)
