#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2008 Adriano Monteiro Marques
#
# Author: Francesco Piccinno <stack.box@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

"""
HTTP protocol dissector (Offline attack).

This module uses TCP reassembler exposed in TCP decoder.
"""

from base64 import b64decode
from struct import pack, unpack
from socket import inet_ntoa

from urllib import unquote

from PM.Core.Atoms import defaultdict
from PM.Core.Logger import log
from PM.Gui.Plugins.Core import Core
from PM.Gui.Plugins.Engine import Plugin
from PM.Manager.AttackManager import *
from PM.Manager.SessionManager import SessionManager

HTTP_NAME = 'dissector.http'
HTTP_PORTS = (80, 8080)
HTTP_TRAILER = '\r\n\r\n'

NTLM_WAIT_RESPONSE = 0

FORM_USERNAME = HTTP_REQUEST  = 0
FORM_PASSWORD = HTTP_RESPONSE = 1

g_fields = None

def form_extract(data, type=FORM_USERNAME):
    if not g_fields:
        return None

    for pattern in unquote(data).split('&'):
        try:
            k, v = pattern.split('=', 1)
            if g_fields[k] == type:
                return v
        except:
            pass

class HTTPRequest(object):
    http_type = HTTP_REQUEST

    def __init__(self, sess):
        self.headers_complete = False
        self.content_length = -1
        self.chunked = False
        self.headers = defaultdict(list)
        self.body = ''
        self.chunks = [(-1, '')]

        self.session = sess

    def feed(self, hlfstream, mpkt, data):
        """
        @return a tuple (bool, int) with bool = True if the response/request
                parsing is complete. The int is the last data count.
        """
        if not self.headers_complete:
            end_ptr = self._parse_headers(mpkt, data)

            if self.headers_complete:

                if self.content_length > 0 or self.chunked:
                    if data[end_ptr:]:
                        ret = self._parse_body(data[end_ptr:], end_ptr)

                        if ret[0]:
                            self._analyze_headers(mpkt)
                            self._parse_post(mpkt)
                            mpkt.set_cfield(HTTP_NAME + '.response', self.body)

                        return ret

                    return False, end_ptr

                self._analyze_headers(mpkt)
                return True, end_ptr

            return False, end_ptr
        else:
            ret = self._parse_body(data)

            if ret[0]:
                self._analyze_headers(mpkt)
                self._parse_post(mpkt)
                mpkt.set_cfield(HTTP_NAME + '.response', self.body)

            return ret

    def _parse_headers(self, mpkt, payload):
        idx = payload.find(HTTP_TRAILER)

        if idx >= 0:
            header_part = payload[:idx]
            self.headers_complete = True
        else:
            last = payload.rfind('\r\n')

            if last == 0:
                return 3
            if last == -1:
                return 0

            header_part = payload[:last]

        for line in header_part.splitlines():
            if not line:
                break

            key, value = line.split(' ', 1)

            if key[-1] == ':':
                key = key[:-1].lower()
            else:
                key = key.lower()
                value = value.rsplit(' ', 1)

                if key.upper() == 'GET':
                    self._parse_get(mpkt, value[0])

            if key == 'content-length':
                try:
                    value = int(value)
                    self.content_length = value

                except ValueError:
                    pass

            elif key == 'transfer-encoding':
                self.chunked = True

            elif key == 'authorization':
                if value[0:9].upper() == 'PASSPORT ':
                    self._parse_passport(mpkt, value[9:])
                elif value[0:5].upper() == 'NTLM ':
                    self._parse_ntlm(mpkt, value[5:])
                elif value[0:6].upper() == 'BASIC ':
                    self._parse_basic(mpkt, value[6:])
                elif value[0:7].upper() == 'DIGEST ':
                    self._parse_digest(mpkt, value[7:])

            elif key == 'www-authenticate':
                if value[0:5] == 'NTLM ':
                    self._parse_ntlm(mpkt, value[5:])

            self.headers[key].append(value)

        if self.headers_complete:
            return idx + 4
        else:
            return last

    def _analyze_headers(self, mpkt):
        if self.http_type == HTTP_REQUEST:
            mpkt.set_cfield(HTTP_NAME + '.is_request', True)
            mpkt.set_cfield(HTTP_NAME + '.is_response', False)
        else:
            mpkt.set_cfield(HTTP_NAME + '.is_request', False)
            mpkt.set_cfield(HTTP_NAME + '.is_response', True)

        mpkt.set_cfield(HTTP_NAME + '.headers', self.headers)

        for req in ('get', 'post', 'head'):
            if req in self.headers:
                mpkt.set_cfield(HTTP_NAME + '.request',
                                req.upper() + " " + self.headers[req][0][0])
                mpkt.set_cfield(HTTP_NAME + '.protocol',
                                self.headers[req][0][1])
                break

        if 'user-agent' in self.headers:
            mpkt.set_cfield(HTTP_NAME + '.browser',
                            self.headers['user-agent'][0])

        if 'accept-language' in self.headers:
            mpkt.set_cfield(HTTP_NAME + '.language',
                            self.headers['accept-language'][0])

        if 'server' in self.headers:
            mpkt.set_cfield('banner', self.headers['server'][0])

    def _parse_get(self, mpkt, val):
        idx = val.find('?')

        if idx < 0:
            return

        username = form_extract(val)
        password = form_extract(val, FORM_PASSWORD)

        if username and password:
            mpkt.set_cfield('username', username)
            mpkt.set_cfield('password', password)

    def _parse_post(self, mpkt):
        if not 'post' in self.headers:
            return

        username = form_extract(self.body)
        password = form_extract(self.body, FORM_PASSWORD)

        if username and password:
            mpkt.set_cfield('username', username)
            mpkt.set_cfield('password', password)

    def _parse_passport(self, mpkt, val):
        # TODO: implement me.
        pass

    def _parse_digest(self, mpkt, val):
        values = []
        found = False
        user = ''

        try:
            for value in val.split(','):
                ret = value.strip().split('=', 1)

                if isinstance(ret, list) and len(ret) == 2:
                    k, v = ret

                    if v[0] == v[-1] and (v[0] == '"' or v[0] == '\''):
                        v = v[1:-1]

                    if k.upper() == 'USERNAME':
                        user = v
                        found = True
                    else:
                        values.append(k + "=" + v)
        finally:
            if found:
                mpkt.set_cfield('username', user)
                mpkt.set_cfield('password', ', '.join(values))

    def _parse_ntlm(self, mpkt, val):
        val = b64decode(val)
        ident, msgtype = unpack('8sI', val[0:12])

        if msgtype == 2:
            challenge_data = unpack('8B', val[24:32])

            s = ''
            for i in challenge_data:
                s += '%02X' % i

            self.session.data = (NTLM_WAIT_RESPONSE, s)

        elif msgtype == 3:
            if self.session.data and self.session.data[0] == NTLM_WAIT_RESPONSE:
                ulen, umaxlen, uoffset = unpack('HHI', val[36:44])
                lmlen, lmmaxlen, lmoffset = unpack('HHI', val[12:20])
                ntlen, ntmaxlen, ntoffset = unpack('HHI', val[20:28])

                username = ''
                ret = val[uoffset:uoffset + ulen]

                for i in xrange(0, len(username), 2):
                    username += chr(ord(ret[i]) & 0x7f)

                password = 'NTLM: '
                for i in val[lmoffset:lmoffset + 24]:
                    password += '%02X' % ord(i)

                password += ':'
                for i in val[ntoffset:ntoffset + 24]:
                    password += '%02X' % ord(i)

                password += ':' + self.session.data[1]

                mpkt.set_cfield('user', username)
                mpkt.set_cfield('password', password)

                self.session.data = None

    def _parse_basic(self, val):
        val = b64decode(val)
        ret = val.split(':', 1)

        if isinstance(ret, tuple) and len(ret) == 2:
            mpkt.set_cfield('user', ret[0])
            mpkt.set_cfield('password', ret[1])

    def _parse_body(self, payload, end_ptr=0):
        if self.chunked:
            idx = 0
            clen, cbody = self.chunks[-1]

            if clen == -1:
                idx = payload.find('\r\n')

                if not idx:
                    return False, end_ptr

                clen = int(payload[:idx], 16)
                idx += 2

                if clen == 0:
                    self.body = '\r\n'.join(map(lambda x: x[1], self.chunks))
                    return True, idx

            real = payload[idx:]
            missing = clen - len(cbody)

            if missing > 0:
                captured = min(len(real), missing)
                cbody += real[:captured]

                self.chunks[-1] = (clen, cbody)

                if len(cbody) == clen:
                    self.chunks.append((-1, ''))
                    return False, captured + idx + end_ptr
                elif len(cbody) > clen:
                    raise Exception('This is impossible')
                else:
                    return False, captured + idx + end_ptr
            elif missing == 0:
                self.chunks.append((-1, ''))
                return False, idx + end_ptr
            elif missing < 0:
                raise Exception('This should not happen')

        elif self.content_length > 0:
            missing = self.content_length - len(self.body)

            if missing > 0:
                captured = min(len(payload), missing)
                self.body += payload[:captured]

                if len(self.body) == self.content_length:
                    return True, captured + end_ptr
                elif len(self.body) > self.content_length:
                    raise Exception('This is impossible')
                else:
                    return False, captured + end_ptr

            elif missing == 0:
                return True, end_ptr
            elif missing < 0:
                raise Exception('This should not happen')

        else:
            self.body += payload
            return True, len(payload) + end_ptr

HTTPResponse = HTTPRequest
HTTPResponse.http_type = HTTP_RESPONSE

class HTTPSession(object):
    def __init__(self):
        self.request = HTTPRequest(self)
        self.response = HTTPResponse(self)

        self.requests = [self.request]
        self.responses = [self.response]

        self.req_last_len = 0
        self.res_last_len = 0

        self.data = None

    def feed_request(self, hlfstream, mpkt):
        while hlfstream.count > self.req_last_len:
            ret, idx = self.request.feed(hlfstream, mpkt,
                                         hlfstream.data[self.req_last_len:])

            if idx == 0:
                return

            self.req_last_len += idx

            if ret:
                self.request = HTTPRequest(self)
                self.requests.append(self.request)

    def feed_response(self, hlfstream, mpkt):
        while hlfstream.count > self.res_last_len:
            ret, idx = self.response.feed(hlfstream, mpkt,
                                          hlfstream.data[self.res_last_len:])

            if idx == 0:
                return

            self.res_last_len += idx

            if ret is True:
                self.response = HTTPResponse(self)
                self.responses.append(self.response)

class HTTPDissector(Plugin, OfflineAttack):
    def start(self, reader):
        tcpdecoder = Core().get_need(reader, 'TCPDecoder')

        if not tcpdecoder:
            raise Exception('TCPDecoder plugin not loaded.')

        if not tcpdecoder.reassembler:
            raise Exception('TCP segments reassembling disabled in TCPDecoder.')

        self.sessions = {}
        tcpdecoder.reassembler.add_analyzer(self._tcp_callback)

        conf = AttackManager().get_configuration(HTTP_NAME)

        ufields = conf['username_fields']
        pfields = conf['password_fields']

        global g_fields

        gflieds = dict(map(lambda x: (x, 0), ufields.split(',')) +  \
                       map(lambda x: (x, 1), pfields.split(',')))

    def register_options(self):
        conf = AttackManager().register_configuration(HTTP_NAME)
        conf.register_option('extract_files', True, bool)
        conf.register_option('form_extract', True, bool)

        username_fields = "login,user,email,username,userid,form_loginname," \
                        "loginname,pop_login,uid,id,user_id,screenname,uname," \
                        "ulogin,acctname,account,member,mailaddress," \
                        "membername,login_username,login_email,uin,sign-in"

        password_fields = "pass,password,passwd,form_pw,pw,userpassword,pwd," \
                        "upassword,login_password,passwort,passwrd"

        conf.register_option('username_fields', username_fields, str)
        conf.register_option('password_fields', password_fields, str)

    def _tcp_callback(self, stream, mpkt):
        if stream.dport in HTTP_PORTS:
            stream.listeners.append(self._process_http)

    def _process_http(self, stream, mpkt):
        if hash(stream) not in self.sessions:
            sess = HTTPSession()
            self.sessions[hash(stream)] = sess
        else:
            sess = self.sessions[hash(stream)]

        sess.feed_response(stream.client, mpkt)
        sess.feed_request(stream.server, mpkt)

        if stream.state in (stream.CONN_RESET, stream.CONN_CLOSE, \
                            stream.CONN_TIMED_OUT):

            del self.sessions[hash(stream)]


__plugins__ = [HTTPDissector]
__plugins_deps__ = [('HTTPDissector', ['TCPDecoder'], [], [])]