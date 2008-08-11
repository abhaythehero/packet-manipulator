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

import sys

from xml.sax import handler, make_parser
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesNSImpl

from Atoms import Singleton

TYPES = {
    str        : 'str',
    bool       : 'bool',
    dict       : 'dict',
    float      : 'float',
    int        : 'int',
    list       : 'list',
    tuple      : 'tuple'
}

class Option(object):
    def __init__(self, value, default=None):
        self.type = 'str'
        self.converter = str
        self.cbs = []

        for k, v in TYPES.items():
            if isinstance(value, k):
                self.type = v
                self.converter = k
                break

        self._value = self.converter(value)

    def connect(self, callback, call=True):
        self.cbs.append(callback)

        if call:
            callback(self.value)

    def disconnect(self, callback):
        if callback in self.cbs:
            self.cbs.remove(callback)

    def get_value(self):
        assert isinstance(self._value, self.converter)
        return self._value

    def set_value(self, val):
        # Check type?
        if not isinstance(val, self.converter):
            val = self.converter(val)

        for cb in self.cbs:
            # Lock if a callback returns True
            if cb(val):
                print "set_value(): Ignoring change"
                return

        print "set_value(): %s = %s" % (self, val)
        self._value = val

    def __repr__(self):
        return "(%s)" % self._value

    value = property(get_value, set_value)

class PreferenceLoader(handler.ContentHandler):
    def __init__(self, outfile):
        self.outfile = outfile
        self.options = {}

    def startElement(self, name, attrs):
        if name in ('bool', 'int', 'float', \
                    'str', 'list', 'tuple'):

            opt_name = None
            opt_value = None

            for attr in attrs.keys():
                if attr == 'id':
                    opt_name = attrs.get(attr)
                if attr == 'value':
                    opt_value = attrs.get(attr)
            
            try:
                if name == 'bool':
                    if opt_value.lower() == 'true' or opt_value == '1':
                        opt_value = True
                    else:
                        opt_value = False
                elif name == 'int':
                    opt_value = int(opt_value)
                elif name == 'float':
                    opt_value = float(opt_value)
                elif name == 'list':
                    opt_value = opt_value.split(",")
                    opt_value = filter(None, opt_value)
                elif name == 'tuple':
                    opt_value = opt_value.split(",")
                    opt_value = filter(None, opt_value)
                    opt_value = tuple(opt_value)
            except:
                return

            if opt_name != None and opt_value != None:
                self.options[opt_name] = Option(opt_value)

class PreferenceWriter:
    def __init__(self, fname, options):
        output = open(fname, 'w')
        self.writer = XMLGenerator(output, 'utf-8')
        self.writer.startDocument()
        self.writer.startElementNS((None, 'PacketManipulator'), 'PacketManipulator', {})

        for key, option in options.items():

            attr_vals = {
                (None, u'id') : key,
                (None, u'value') : str(option.value)
            }

            attr_qnames = {
                (None, u'id') : u'id',
                (None, u'value') : u'value'
            }

            attrs = AttributesNSImpl(attr_vals, attr_qnames)
            self.writer.startElementNS((None, str(option.type)), str(option.type), attrs)
            self.writer.endElementNS((None, str(option.type)), str(option.type))

        self.writer.endElementNS((None, 'PacketManipulator'), 'PacketManipulator')
        self.writer.endDocument()
        output.close()

class Prefs(Singleton):
    options = {
        'gui.docking' : True,
        'gui.maintab.sniffview.font' : 'Monospace 10',
        'gui.maintab.sniffview.usecolors' : False,
        'gui.maintab.hexview.font' : 'Monospace 10',
        'gui.maintab.hexview.bpl' : 16,
        
        'gui.views.protocol_selector_tab' : True,
        'gui.views.property_tab' : True,
        'gui.views.status_tab' : True,
        'gui.views.vte_tab' : False,
        'gui.views.hack_tab' : False,
        'gui.views.console_tab' : False,

        'backend.system' : 'scapy',
    }

    def __init__(self):
        self.fname = 'pm-prefs.xml'
        
        try:
            opts = self.load_options()
            self.options.update(self.load_options())
        except Exception:
            pass

        diff_dict = {}
        for name, opt in self.options.items():
            if not isinstance(opt, Option):
                diff_dict[name] = Option(opt)

        self.options.update(diff_dict)

    def load_options(self):
        handler = PreferenceLoader(sys.stdout)
        parser = make_parser()
        parser.setContentHandler(handler)
        parser.parse(self.fname)

        return handler.options

    def write_options(self):
        writer = PreferenceWriter(self.fname, self.options)

    def __getitem__(self, x):
        return self.options[x]

if __name__ == "__main__":
    Prefs().load_options('test.xml')

