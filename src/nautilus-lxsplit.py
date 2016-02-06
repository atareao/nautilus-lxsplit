#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#
#
# Copyright (C) 2015 Lorenzo Carbonell
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
#
#
#
from gi.repository import Nautilus as FileManager
from gi.repository import Gtk, GObject, Notify
from urllib import unquote_plus
import subprocess
import os

_ = str


class Notificator(GObject.Object):
	def __init__(self):
		super(Notificator, self).__init__()
		Notify.init("nautilus-lxsplit")
		self.notification = Notify.Notification.new("", "", "")
	
	def send_notification(self, title, text, file_path_to_icon=""):
		print(title,text)
		self.notification.update(title,text,file_path_to_icon)
		self.notification.show()

class SetSplitSizeDialog(Gtk.Dialog):
	def __init__(self,file_size):
		Gtk.Dialog.__init__(self,_('Split size file'),None,Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,(Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT,Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL))
		self.set_size_request(350, 100)
		self.set_resizable(False)
		self.connect('destroy', self.close_application)
		#
		vbox0 = Gtk.VBox(spacing = 5)
		vbox0.set_border_width(5)
		self.get_content_area().add(vbox0)
		#
		frame1 = Gtk.Frame()
		vbox0.add(frame1)
		#
		table1 = Gtk.Table(rows = 1, columns = 2, homogeneous = False)
		table1.set_border_width(5)
		table1.set_col_spacings(5)
		table1.set_row_spacings(5)
		frame1.add(table1)
		#
		label1 = Gtk.Label(_('Split size (MB)')+':')
		label1.set_tooltip_text(_('Set de split size'))
		label1.set_alignment(0,.5)
		table1.attach(label1,0,1,0,1, xoptions = Gtk.AttachOptions.FILL, yoptions = Gtk.AttachOptions.SHRINK)
		#
		self.entry1 = Gtk.SpinButton()
		self.entry1.set_adjustment(Gtk.Adjustment(1,1,100000000,1,10,100))
		self.entry1.set_value(file_size)
		table1.attach(self.entry1,1,2,0,1, xoptions = Gtk.AttachOptions.FILL, yoptions = Gtk.AttachOptions.SHRINK)
		#
		self.show_all()

	def get_split_size(self):
		return int(self.entry1.get_value())
		
	def close_application(self,widget):
		self.hide()	

"""
Tools to share folders
"""	
class LSSplitMenuProvider(GObject.GObject, FileManager.MenuProvider):
	"""Implements the 'Replace in Filenames' extension to the File Manager right-click menu"""

	def __init__(self):
		"""File Manager crashes if a plugin doesn't implement the __init__ method"""
		self.notificator = Notificator()
	
	def is_an_alone_file_for_split(self,items):
		if len(items) == 1:
			if not items[0].is_directory():
				path = unquote_plus(items[0].get_uri())[7:]
				filename, file_extension = os.path.splitext(path)
				if file_extension != '.001':
					return True
		return False

	def is_an_alone_file_for_join(self,items):
		if len(items) == 1:
			if not items[0].is_directory():
				path = unquote_plus(items[0].get_uri())[7:]
				filename, file_extension = os.path.splitext(path)
				if file_extension == '.001':
					return True
		return False
	
	def menu_split_file(self,menu,items):
		sssd = SetSplitSizeDialog(50)
		if sssd.run() == Gtk.ResponseType.ACCEPT:
			sssd.hide()
			split_size = sssd.get_split_size()
			thefile = unquote_plus(items[0].get_uri())[7:]
			print(thefile)
			print('lxsplit -s %s %sM'%(thefile,split_size))
			os.chdir(os.path.dirname(thefile))
			p = subprocess.Popen(["lxsplit", "-s",thefile, "%sM"%(split_size)], stdout = subprocess.PIPE)
			out, err = p.communicate()			
			print(0)
			print(out,err)
			if out.find('filesize is same as size of the filename')!=-1:
				self.notificator.send_notification('Nautilus-LXSplit','%s filesize is same as size of the filename! Aborting...'%(os.path.basename(thefile)))
			else:
				self.notificator.send_notification('Nautilus-LXSplit','Splitted %s'%(os.path.basename(thefile)))
			print(1)
		sssd.destroy()

	def menu_join_file(self,menu,items):
		thefile = unquote_plus(items[0].get_uri())[7:]
		os.chdir(os.path.dirname(thefile))
		p = subprocess.Popen(["lxsplit", "-j", thefile], stdout = subprocess.PIPE)
		out, err = p.communicate()
		print(out,err)
		if out.find('already exists! Aborting')!=-1:
			self.notificator.send_notification('Nautilus-LXSplit','J%s already exists! Aborting...'%(os.path.basename(thefile)))
		else:
			self.notificator.send_notification('Nautilus-LXSplit','Joined %s'%(os.path.basename(thefile)))
		print(1)
	
	def get_file_items(self, window, sel_items):
		"""Adds the 'Replace in Filenames' menu item to the File Manager right-click menu,
		   connects its 'activate' signal to the 'run' method passing the selected Directory/File"""
		if self.is_an_alone_file_for_split(sel_items):
			top_menuitem = FileManager.MenuItem(name='LXSplitMenuProvider::Gtk-lxsplit',
									 label=_('Split file'),
									 tip=_('Split this file'))
			top_menuitem.connect('activate', self.menu_split_file, sel_items)
			return top_menuitem,
		elif self.is_an_alone_file_for_join(sel_items):
			top_menuitem = FileManager.MenuItem(name='LXSplitMenuProvider::Gtk-lxjoin',
									 label=_('Join file'),
									 tip=_('Join this file'))
			top_menuitem.connect('activate', self.menu_join_file, sel_items)
			return top_menuitem,
		return

if __name__=='__main__':
	sssd = SetSplitSizeDialog(50)
	if sssd.run() == Gtk.ResponseType.ACCEPT:
		print(sssd.get_split_size())
