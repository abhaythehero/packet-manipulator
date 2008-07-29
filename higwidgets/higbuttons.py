#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2006 Insecure.Com LLC.
# Copyright (C) 2007-2008 Adriano Monteiro Marques
#
# Author: Adriano Monteiro Marques <adriano@umitproject.org>
#         Cleber Rodrigues <cleber.gnu@gmail.com>
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
higwidgets/higbuttons.py

   button related classes
"""

__all__ = ['HIGMixButton', 'HIGButton', 'HIGArrowButton']

import gtk
import gobject

class HIGMixButton (gtk.HBox):
    def __init__(self, title, stock):
        gtk.HBox.__init__(self, False, 4)
        self.img = gtk.Image()
        self.img.set_from_stock(stock, gtk.ICON_SIZE_BUTTON)
        
        self.lbl = gtk.Label(title)
		
        self.hbox1 = gtk.HBox(False, 2)
        self.hbox1.pack_start(self.img, False, False, 0)
        self.hbox1.pack_start(self.lbl, False, False, 0)
		
        self.align = gtk.Alignment(0.5, 0.5, 0, 0)
        self.pack_start(self.align)
        self.pack_start(self.hbox1)

class HIGButton (gtk.Button):
    def __init__ (self, title="", stock=None):
        if title and stock:
            gtk.Button.__init__(self)
            content = HIGMixButton(title, stock)
            self.add(content)
        elif title and not stock:
            gtk.Button.__init__(self, title)
        elif stock:
            gtk.Button.__init__(self, stock=stock)
        else:
            gtk.Button.__init__(self)

class HIGToggleButton(gtk.ToggleButton):
    def __init__(self, title="", stock=None):
        if title and stock:
            gtk.ToggleButton.__init__(self)
            content = HIGMixButton(title, stock)
            self.add(content)
        elif title and not stock:
            gtk.ToggleButton.__init__(self, title)
        elif stock:
            gtk.ToggleButton.__init__(self, stock)
            self.set_use_stock(True)
        else:
            gtk.ToggleButton.__init__(self)

class HIGArrowButton(gtk.Button):
    __gtype_name__ = "HIGArrowButton"

    def __init__(self, orient, label=None):
        super(HIGArrowButton, self).__init__()
        
        # Fascist mode!
        self.arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_ETCHED_IN)

        # No genocide yet :)
        self._active = False
        self.orientation = orient

        self.label = gtk.Label()
        
        if label:
            self.label.set_text(label)
            self.label.set_use_markup(True)

        hbox = gtk.HBox(False, 2)
        hbox.pack_start(self.arrow)
        hbox.pack_start(self.label)
        hbox.show_all()

        self.add(hbox)

    def set_orientation(self, orient):
        shadow = self.arrow.get_property("shadow-type")

        if orient == gtk.ORIENTATION_HORIZONTAL:
            self.orient = gtk.ORIENTATION_HORIZONTAL

            if self.get_active():
                self.arrow.set(gtk.ARROW_LEFT, shadow)
            else:
                self.arrow.set(gtk.ARROW_RIGHT, shadow)
        else:
            self.orient = gtk.ORIENTATION_VERTICAL

            if self.get_active():
                self.arrow.set(gtk.ARROW_UP, shadow)
            else:
                self.arrow.set(gtk.ARROW_DOWN, shadow)

    def get_orientation(self):
        return self.orient

    def set_shadow(self, value):
        direction = self.arrow.get_property("arrow-type")
        self.arrow.set(direction, value)

    def get_shadow(self, value):
        return self.arrow.get_property("shadow-type")

    def get_active(self):
        return self._active

    def set_active(self, val):
        self._active = val
        self.orientation = self.orientation

    orientation = property(get_orientation, set_orientation)
    shadow_type = property(get_shadow, set_shadow)
    active      = property(get_active, set_active)

gobject.type_register(HIGArrowButton)