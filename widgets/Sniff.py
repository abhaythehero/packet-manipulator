import gtk
import pango
import gobject
import Backend

from umitCore.I18N import _

from Manager.PreferenceManager import Prefs
from higwidgets.higanimates import HIGAnimatedBar

class SniffRenderer(gtk.CellRendererText):
    __gtype_name__ = "SniffRenderer"

    def do_render(self, window, widget, back, cell, expose, flags):
        cr = window.cairo_create()
        cr.save()

        cr.set_line_width(0.5)
        cr.set_dash([1, 1], 1)
        cr.move_to(back.x, back.y + back.height)
        cr.line_to(back.x + back.width, back.y + back.height)
        cr.stroke()

        cr.restore()

        return gtk.CellRendererText.do_render(self, window, widget, back, cell, expose, flags)

gobject.type_register(SniffRenderer)

class SniffPage(gtk.VBox):
    COL_NO     = 0
    COL_TIME   = 1
    COL_SRC    = 2
    COL_DST    = 3
    COL_PROTO  = 4
    COL_INFO   = 5
    COL_COLOR  = 6
    COL_OBJECT = 7

    def __init__(self, session, context=None):
        super(SniffPage, self).__init__(False, 4)

        self.session = session

        self.set_border_width(2)

        self.__create_toolbar()
        self.__create_view()

        self.statusbar = HIGAnimatedBar('', gtk.STOCK_INFO)
        self.pack_start(self.statusbar, False, False)

        self.show_all()

        self.use_colors = True

        # TODO: get from preference
        self.colors = (
            gtk.gdk.color_parse('#FFFA99'),
            gtk.gdk.color_parse('#8DFF7F'),
            gtk.gdk.color_parse('#FFE3E5'),
            gtk.gdk.color_parse('#C797FF'),
            gtk.gdk.color_parse('#A0A0A0'),
            gtk.gdk.color_parse('#D6E8FF'),
            gtk.gdk.color_parse('#C2C2FF'),
        )

        Prefs()['gui.maintab.sniffview.font'].connect(self.__modify_font)
        Prefs()['gui.maintab.sniffview.usecolors'].connect(self.__modify_colors)


        if not context:
            self.store.append([self.session.packet])
            self.statusbar.label = _('<b>Editing <tt>%s</tt></b>') % self.session.packet.summary()
        else:
            self.context = context
            self.context.start()

            self.statusbar.label = _('<b>Sniffing on <tt>%s</tt> ...</b>') % context.iface
            self.timeout_id = gobject.timeout_add(200, self.__update_tree)

        self.tree.get_selection().connect('changed', self.__on_selection_changed)
        self.filter.get_entry().connect('activate', self.__on_apply_filter)

    def __create_toolbar(self):
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_style(gtk.TOOLBAR_ICONS)

        stocks = (
            gtk.STOCK_MEDIA_STOP,
            gtk.STOCK_SAVE,
            gtk.STOCK_SAVE_AS
        )

        callbacks = (
            self.__on_stop,
            self.__on_save,
            self.__on_save_as
        )

        tooltips = (
            _('Stop capturing'),
            _('Save packets'),
            _('Save packets as')
        )

        for tooltip, stock, callback in zip(tooltips, stocks, callbacks):
            action = gtk.Action(None, None, tooltip, stock)
            action.connect('activate', callback)

            self.toolbar.insert(action.create_tool_item(), -1)

        self.filter = SniffFilter()

        item = gtk.ToolItem()
        item.add(self.filter)
        item.set_expand(True)

        self.toolbar.insert(item, -1)

        self.pack_start(self.toolbar, False, False)

    def __create_view(self):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        self.store = gtk.ListStore(object)
        self.tree = gtk.TreeView(self.store)

        # Create a filter function
        self.model_filter = self.store.filter_new()
        self.model_filter.set_visible_func(self.__filter_func)

        self.tree.set_model(self.model_filter)

        idx = 0
        rend = SniffRenderer()

        for txt in (_('No.'), _('Time'), _('Source'), \
                    _('Destination'), _('Protocol'), _('Info')):

            col = gtk.TreeViewColumn(txt, rend)
            col.set_cell_data_func(rend, self.__cell_data_func, idx)
            self.tree.append_column(col)

            idx += 1

        sw.add(self.tree)
        self.pack_start(sw)

    def __cell_data_func(self, col, cell, model, iter, idx):
        packet = model.get_value(iter, 0)

        if idx == self.COL_NO:
            cell.set_property('text', str(model.get_path(iter)[0] + 1))
        elif idx == self.COL_TIME:
            cell.set_property('text', packet.get_time())
        elif idx == self.COL_SRC:
            cell.set_property('text', packet.get_source())
        elif idx == self.COL_DST:
            cell.set_property('text', packet.get_dest())
        elif idx == self.COL_PROTO:
            cell.set_property('text', packet.get_protocol_str())
        elif idx == self.COL_INFO:
            cell.set_property('text', packet.summary())

        cell.set_property('cell-background-gdk', self.__get_color(packet))
       
    def __modify_font(self, font):
        try:
            desc = pango.FontDescription(font)

            for col in self.tree.get_columns():
                for rend in col.get_cell_renderers():
                    rend.set_property('font-desc', desc)
        except:
            # Block change

            return True
    
    def __modify_colors(self, value):
        self.use_colors = value
        self.tree.set_rules_hint(not self.use_colors)

    def __get_color(self, packet):
        if self.use_colors:
            proto = packet.get_protocol_str()
            return self.colors[hash(proto) % len(self.colors)]
        else:
            return None

    def __update_tree(self):
        for packet in self.context.get_data():
            self.store.append([packet])

            # Scroll to end
            if self.context.auto_scroll:
                self.tree.scroll_to_cell(len(self.model_filter) - 1)

        alive = self.context.is_alive()

        if self.context.exception:
            self.statusbar.label = "<b>%s</b>" % self.context.exception
            self.statusbar.image = gtk.STOCK_DIALOG_ERROR
            self.statusbar.start_animation(True)
        elif not alive:
            self.statusbar.label = \
                _("<b>Sniffing session finished (%d packets caputered)</b>") % self.context.tot_count
            self.statusbar.image = gtk.STOCK_INFO
            self.statusbar.start_animation(True)

        return alive

    def stop_sniffing(self):
        if hasattr(self, 'context') and self.context:
            self.context.destroy()

    # Signals callbacks

    def __on_selection_changed(self, selection):
        model, iter = selection.get_selected()

        if not iter:
            return

        packet = model.get_value(iter, 0)

        if not packet:
            return

        from App import PMApp

        nb = PMApp().main_window.get_tab("MainTab").session_notebook
        session = nb.get_current_session()

        if session:
            session.set_active_packet(packet)

    def __on_apply_filter(self, entry):
        self.model_filter.refilter()

    def __filter_func(self, model, iter):
        txt = self.filter.get_text()

        if not txt:
            return True

        packet = model.get_value(iter, 0)

        strs = (
            str(model.get_path(iter)[0] + 1),
            packet.get_time(),
            packet.get_source(),
            packet.get_dest(),
            packet.get_protocol_str(),
            packet.summary()
        )

        # TODO: implement a search engine like num: summary: ?

        for pattern in strs:
            if txt in pattern:
                return True

        return False

    def __on_stop(self, action):
        if getattr(self, 'context', None) and self.context.is_alive():
            self.context.destroy()

    def __on_save(self, action, saveas_on_fail=True):
        if getattr(self, 'context', None) and self.context.cap_file:
            self.__save_packets(self.context.cap_file)
        else:
            self.__on_save_as(None)

    def __on_save_as(self, action):
        dialog = gtk.FileChooserDialog(_('Save Pcap file to'),
                self.get_toplevel(), gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))

        for name, pattern in ((_('Pcap files'), '*.pcap'),
                              (_('Pcap gz files'), '*.pcap.gz'),
                              (_('All files'), '*')):

            filter = gtk.FileFilter()
            filter.set_name(name)
            filter.add_pattern(pattern)
            dialog.add_filter(filter)

        if dialog.run() == gtk.RESPONSE_ACCEPT:
            self.__save_packets(dialog.get_filename())

        dialog.hide()
        dialog.destroy()

    def __save_packets(self, fname):
        lst = []
        iter = None

        for idx in xrange(len(self.store)):
            iter = self.store.get_iter((idx, ))
            lst.append(self.store.get_value(iter, 0))

        # Now dump to file
        self.statusbar.image = gtk.STOCK_HARDDISK
        self.statusbar.label = \
            _("<b>Written %d packets to %s</b>") % (len(lst), fname)

        try:
            Backend.write_pcap_file(fname, lst)
        except Exception, err:
            self.statusbar.image = gtk.STOCK_DIALOG_ERROR
            self.statusbar.label = _("<b>Error while writing to %s (%s)</b>") % (fname, str(err))

        self.statusbar.start_animation(True)

class SniffFilter(gtk.HBox):
    __gtype_name__ = "SniffFilter"

    def __init__(self):
        super(SniffFilter, self).__init__(False, 2)

        self.set_border_width(4)

        self._entry = gtk.Entry()
        self._box = gtk.EventBox()
        self._box.add(gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU))

        self._entry.set_has_frame(False)

        self.pack_start(self._entry)
        self.pack_end(self._box, False, False)

        self._box.connect('button-release-event', self.__on_button_release)
        self._entry.connect('changed', self.__on_update)

        self._colors = None
    
    def do_realize(self):
        gtk.HBox.do_realize(self)

        self._colors = (
            self.style.white,
            gtk.gdk.color_parse("#FEFEDC")
        )
        
        self.__on_update(self._entry)

    def do_expose_event(self, evt):
        alloc = self.allocation    
        rect = gtk.gdk.Rectangle(alloc.x, alloc.y, alloc.width, alloc.height)

        self.style.paint_flat_box(
            self.window,          
            self._entry.state,  
            self._entry.get_property('shadow_type'),
            alloc,                                    
            self._entry,                            
            'entry_bg',                               
            rect.x, rect.y, rect.width, rect.height   
        )                                             

        self.style.paint_shadow(
            self.window,        
            self._entry.state,
            self._entry.get_property('shadow_type'),
            alloc,                                    
            self._entry,                            
            'entry',                                  
            rect.x, rect.y, rect.width, rect.height   
        )

        return gtk.HBox.do_expose_event(self, evt)

    def __on_button_release(self, image, evt):
        if evt.button == 1:
            self._entry.set_text('')

    def __on_update(self, entry):
        if self._entry.get_text():
            color = self._colors[1]
        else:
            color = self._colors[0]

        self._entry.modify_base(gtk.STATE_NORMAL, color)
        self._box.modify_bg(gtk.STATE_NORMAL, color)
        self.modify_base(gtk.STATE_NORMAL, color)

    def get_text(self):
        return self._entry.get_text()

    def set_text(self, txt):
        self._entry.set_text(txt)

    def get_entry(self):
        return self._entry

gobject.type_register(SniffFilter)
