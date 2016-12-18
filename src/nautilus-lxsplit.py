#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of nautilus-lxsplit
#
# Copyright (C) 2012-2016 Lorenzo Carbonell
# lorenzo.carbonell.cerezo@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gi
try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('Nautilus', '3.0')
    gi.require_version('Notify', '0.7')
except Exception as e:
    print(e)
    exit(-1)
from gi.repository import Nautilus as FileManager
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Notify
from urllib import unquote_plus
import subprocess
import shlex
import os
from threading import Thread

APPNAME = 'nautilus-lxsplit'
ICON = 'nautilus-lxsplit'
VERSION = '$VERSION$'

_ = str


class IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """
    def __init__(self):
        GObject.GObject.__init__(self)

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)


class DoItInBackground(IdleObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'start_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (str,)),
        'end_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (float,)),
    }

    def __init__(self, element, rutine):
        IdleObject.__init__(self)
        Thread.__init__(self)
        self.element = element
        self.rutine = rutine
        self.stopit = False
        self.ok = True
        self.daemon = True
        self.process = None

    def stop(self, *args):
        self.stopit = True

    def process_file(self):
        os.chdir(os.path.dirname(self.element))
        args = shlex.split(self.rutine)
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE)
        out, err = self.process.communicate()

    def run(self):
        self.emit('started', get_duration(self.element))
        try:
            if self.stopit is True:
                self.ok = False
                break
            self.emit('start_one', self.element)
            self.process_file()
            self.emit('end_one', get_duration(self.element))
        except Exception as e:
            self.ok = False
        try:
            if self.process is not None:
                self.process.terminate()
                self.process = None
        except Exception as e:
            print(e)
        self.emit('ended', self.ok)


class Progreso(Gtk.Dialog, IdleObject):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent):
        Gtk.Dialog.__init__(self, title, parent,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT)
        IdleObject.__init__(self)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame1 = Gtk.Frame()
        vbox.pack_start(frame1, True, True, 0)
        table = Gtk.Table(2, 2, False)
        frame1.add(table)
        #
        self.label = Gtk.Label()
        table.attach(self.label, 0, 2, 0, 1,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        #
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(300, 0)
        table.attach(self.progressbar, 0, 1, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        button_stop = Gtk.Button()
        button_stop.set_size_request(40, 40)
        button_stop.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_STOP, Gtk.IconSize.BUTTON))
        button_stop.connect('clicked', self.on_button_stop_clicked)
        table.attach(button_stop, 1, 2, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK)
        self.stop = False
        self.show_all()
        self.max_value = float(max_value)
        self.value = 0.0
        self.title = title

    def set_max_value(self, anobject, max_value):
        self.max_value = float(max_value)

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def increase(self, anobject, value):
        self.value += float(value)
        fraction = self.value/self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value >= self.max_value:
            self.hide()

    def set_element(self, anobject, element):
        self.label.set_text(('%s: %s') % (self.title, element))


class Notificator(GObject.Object):
    def __init__(self):
        super(Notificator, self).__init__()
        Notify.init("nautilus-lxsplit")
        self.notification = Notify.Notification.new("", "", "")

    def send_notification(self, title, text, file_path_to_icon=""):
        print(title, text)
        self.notification.update(title, text, file_path_to_icon)
        self.notification.show()


class SetSplitSizeDialog(Gtk.Dialog):
    def __init__(self, file_size, window):
        Gtk.Dialog.__init__(self,
                            _('Split size file'),
                            window,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,
                             Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        self.set_size_request(350, 100)
        self.set_resizable(False)
        self.connect('destroy', self.close_application)
        #
        vbox0 = Gtk.VBox(spacing=5)
        vbox0.set_border_width(5)
        self.get_content_area().add(vbox0)
        #
        frame1 = Gtk.Frame()
        vbox0.add(frame1)
        #
        table1 = Gtk.Table(rows=1, columns=2, homogeneous=False)
        table1.set_border_width(5)
        table1.set_col_spacings(5)
        table1.set_row_spacings(5)
        frame1.add(table1)
        #
        label1 = Gtk.Label(_('Split size (MB)')+':')
        label1.set_tooltip_text(_('Set de split size'))
        label1.set_alignment(0, .5)
        table1.attach(label1, 0, 1, 0, 1,
                      xoptions=Gtk.AttachOptions.FILL,
                      yoptions=Gtk.AttachOptions.SHRINK)
        self.entry1 = Gtk.SpinButton()
        self.entry1.set_adjustment(Gtk.Adjustment(1, 1, 100000000, 1, 10, 100))
        self.entry1.set_value(file_size)
        table1.attach(self.entry1, 1, 2, 0, 1,
                      xoptions=Gtk.AttachOptions.FILL,
                      yoptions=Gtk.AttachOptions.SHRINK)
        #
        self.show_all()

    def get_split_size(self):
        return int(self.entry1.get_value())

    def close_application(self, widget):
        self.hide()


def get_duration(file_in):
    return os.path.getsize(file_in)


def get_files(files_in):
    files = []
    for file_in in files_in:
        print(file_in)
        file_in = unquote_plus(file_in.get_uri()[7:])
        if os.path.isfile(file_in):
            files.append(file_in)
    return files


class LSSplitMenuProvider(GObject.GObject, FileManager.MenuProvider):
    """
    Implements the 'Replace in Filenames' extension to the File Manager\
    right-click menu
    """

    def __init__(self):
        """
        File Manager crashes if a plugin doesn't implement the __init__\
        method
        """
        self.notificator = Notificator()

    def is_an_alone_file_for_split(self, items):
        if len(items) == 1:
            if not items[0].is_directory():
                path = unquote_plus(items[0].get_uri())[7:]
                filename, file_extension = os.path.splitext(path)
                if file_extension != '.001':
                    return True
        return False

    def is_an_alone_file_for_join(self, items):
        if len(items) == 1:
            if not items[0].is_directory():
                path = unquote_plus(items[0].get_uri())[7:]
                filename, file_extension = os.path.splitext(path)
                if file_extension == '.001':
                    return True
        return False

    def split_finished(self, widget, ok, afile):
            if ok is False:
                self.notificator.send_notification(
                    'Nautilus-LXSplit',
                    '%s filesize is same as size of the filename! Aborting...'
                    % (os.path.basename(afile)))
            else:
                self.notificator.send_notification(
                    'Nautilus-LXSplit',
                    'Splitted %s' % (os.path.basename(afile)))

    def join_finished(self, widget, ok, afile):
        if ok is False:
            self.notificator.send_notification(
                'Nautilus-LXSplit',
                'J%s already exists! Aborting...' % (
                    os.path.basename(afile)))
        else:
            self.notificator.send_notification(
                'Nautilus-LXSplit',
                'Joined %s' % (os.path.basename(afile)))

    def menu_split_file(self, menu, items, window):
        sssd = SetSplitSizeDialog(50, window)
        if sssd.run() == Gtk.ResponseType.ACCEPT:
            split_size = sssd.get_split_size()
            sssd.destroy()
            files = get_files(items)
            rutine = 'lxsplit -s "%s" %sM' % (files[0], split_size)
            diib = DoItInBackground(files[0], rutine)
            progreso = Progreso(_('Split file'), window, len(files))
            diib.connect('started', progreso.set_max_value)
            diib.connect('start_one', progreso.set_element)
            diib.connect('end_one', progreso.increase)
            diib.connect('ended', progreso.close)
            diib.connect('ended', self.split_finished, files[0])
            progreso.connect('i-want-stop', diib.stop)
            diib.start()
            progreso.run()
        sssd.destroy()

    def menu_join_file(self, menu, items):
        files = get_files(items)
        if files > 0:
            rutine = 'lxsplit -j "%s"' % (files[0])
            diib = DoItInBackground(files[0], rutine)
            progreso = Progreso(_('Join file'), window, len(files))
            diib.connect('started', progreso.set_max_value)
            diib.connect('start_one', progreso.set_element)
            diib.connect('end_one', progreso.increase)
            diib.connect('ended', progreso.close)
            diib.connect('ended', self.join_finished, files[0])
            progreso.connect('i-want-stop', diib.stop)
            diib.start()
            progreso.run()

    def get_file_items(self, window, sel_items):
        """
        Adds the 'Replace in Filenames' menu item to the File Manager\
        right-click menu, connects its 'activate' signal to the 'run'\
        method passing the selected Directory/File
        """
        top_menuitem = FileManager.MenuItem(
            name='LXSplitMenuProvider::Gtk-lxsplit-top',
            label=_('Split and join files'),
            tip=_('Tool to split and join files'))
        submenu = FileManager.Menu()
        top_menuitem.set_submenu(submenu)

        if self.is_an_alone_file_for_split(sel_items):
            sub_menuitem_00 = FileManager.MenuItem(
                name='LXSplitMenuProvider::Gtk-lxsplit-sub-01',
                label=_('Split file'),
                tip=_('Split this file'))
            sub_menuitem_00.connect('activate',
                                    self.menu_split_file,
                                    sel_items,
                                    window)
        elif self.is_an_alone_file_for_join(sel_items):
            sub_menuitem_00 = FileManager.MenuItem(
                name='LXSplitMenuProvider::Gtk-lxsplit-sub-01',
                label=_('Join file'),
                tip=_('Join this file'))
            sub_menuitem_00.connect('activate',
                                    self.menu_join_file,
                                    sel_items)
        submenu.append_item(sub_menuitem_00)

        sub_menuitem_01 = FileManager.MenuItem(
            name='LXSplitMenuProvider::Gtk-lxsplit-sub-02',
            label=_('About'),
            tip=_('About'))
        sub_menuitem_01.connect('activate', self.about, window)
        submenu.append_item(sub_menuitem_01)
        return top_menuitem,

    def about(self, widget, window):
        ad = Gtk.AboutDialog(parent=window)
        ad.set_name(APPNAME)
        ad.set_version(VERSION)
        ad.set_copyright('Copyrignt (c) 2016\nLorenzo Carbonell')
        ad.set_comments(APPNAME)
        ad.set_license('''
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
''')
        ad.set_website('http://www.atareao.es')
        ad.set_website_label('http://www.atareao.es')
        ad.set_authors([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_documenters([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_icon_name(ICON)
        ad.set_logo_icon_name(APPNAME)
        ad.run()
        ad.destroy()

if __name__ == '__main__':
    sssd = SetSplitSizeDialog(50, None)
    if sssd.run() == Gtk.ResponseType.ACCEPT:
        print(sssd.get_split_size())
