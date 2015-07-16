# Copyright (C) 2008, One Laptop Per Child
# Copyright (C) 2009, Tomeu Vizoso
# Copyright (C) 2015, Martin Abente Lahaye - <tch@sugarlabs.org>
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

from gettext import gettext as _
from gettext import ngettext
import locale
import logging

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from sugar3.graphics import style
from sugar3.graphics.icon import Icon

from jarabe.controlpanel.sectionview import SectionView


class SystemUpdaterView(SectionView):

    def __init__(self, model, alerts):
        SectionView.__init__(self)

        self.set_spacing(style.DEFAULT_SPACING)
        self.set_border_width(style.DEFAULT_SPACING * 2)

        self._top_label = Gtk.Label()
        self._top_label.set_line_wrap(True)
        self._top_label.set_justify(Gtk.Justification.LEFT)
        self._top_label.props.xalign = 0
        self.pack_start(self._top_label, False, True, 0)
        self._top_label.show()

        separator = Gtk.HSeparator()
        self.pack_start(separator, False, True, 0)
        separator.show()

        self._bottom_label = Gtk.Label()
        self._bottom_label.set_line_wrap(True)
        self._bottom_label.set_justify(Gtk.Justification.LEFT)
        self._bottom_label.props.xalign = 0
        self._bottom_label.set_markup(
            _('Software updates correct errors, eliminate security '
              'vulnerabilities, and provide new features.'))
        self.pack_start(self._bottom_label, False, True, 0)
        self._bottom_label.show()

        self._update_box = None
        self._progress_pane = None

        self._model = model.SystemUpdaterModel()
        self._model.connect('progress', self.__progress_cb)
        self._model.connect('progress-detail', self.__detail_cb)
        self._model.connect('finished', self.__finished_cb)
        self._model.connect('cancellable', self.__cancellable_cb)
        self._model.connect('size', self.__size_cb)

        self._initialize()

    def _initialize(self):
        top_message = _('Initializing...')
        self._top_label.set_markup('<big>%s</big>' % top_message)
        self._refresh()

    def _switch_to_update_box(self, packages):
        if self._update_box in self.get_children():
            return

        if self._progress_pane in self.get_children():
            self.remove(self._progress_pane)
            self._progress_pane = None

        if self._update_box is None:
            self._update_box = UpdateBox(packages)
            self._update_box.refresh_button.connect(
                'clicked',
                self.__refresh_button_clicked_cb)
            self._update_box.install_button.connect(
                'clicked',
                self.__install_button_clicked_cb)
            self._update_box._package_list.props.model.connect(
                'row-changed', self.__selection_changed_cb)

        self.pack_start(self._update_box, expand=True, fill=True, padding=0)
        self._update_box.show()

    def _switch_to_progress_pane(self):
        if self._progress_pane in self.get_children():
            return

        if self._model.get_state() == self._model.STATE_REFRESHING:
            top_message = _('Refreshing sources...')
        elif self._model.get_state() == self._model.STATE_CHECKING:
            top_message = _('Checking for updates...')
        elif self._model.get_state() == self._model.STATE_UPDATING:
            top_message = _('Installing updates...')
        else:
            top_message = '???'
        self._top_label.set_markup('<big>%s</big>' % top_message)

        if self._update_box in self.get_children():
            self.remove(self._update_box)
            self._update_box = None

        if self._progress_pane is None:
            self._progress_pane = ProgressPane()
            self._progress_pane.cancel_button.connect(
                'clicked',
                self.__cancel_button_clicked_cb)

        self.pack_start(
            self._progress_pane, expand=True, fill=False, padding=0)
        self._progress_pane.show()

    def _switch_to_success(self, packages):
        if self._model.get_state() == self._model.STATE_REFRESHING:
            self._refreshed()
        elif self._model.get_state() == self._model.STATE_CHECKING:
            self._checked(packages)
        elif self._model.get_state() == self._model.STATE_UPDATING:
            self._updated(packages)

    def _switch_to_error(self):
        top_message = _('Can\'t connect to the activity server')
        self._top_label.set_markup('<big>%s</big>' % top_message)
        self._bottom_label.set_markup(
            _('Verify your connection to internet and try again, '
              'or try again later'))
        self._clear_center()

    def _switch_to_cancelled(self):
        top_message = _('The updates have been cancelled')
        self._top_label.set_markup('<big>%s</big>' % top_message)
        self._bottom_label.set_text('')
        self._clear_center()

    def _clear_center(self):
        if self._progress_pane in self.get_children():
            self.remove(self._progress_pane)
            self._progress_pane = None

        if self._update_box in self.get_children():
            self.remove(self._update_box)
            self._update_box = None

    def _refresh(self):
        GLib.idle_add(self._model.refresh)

    def _refreshed(self):
        # XXX do everything here until we can detect progress on simulate
        self._set_toolbar_cancellable(False)
        top_message = _('Checking for updates...')
        self._top_label.set_markup('<big>%s</big>' % top_message)
        self._progress_pane.set_message(_('Please wait...'))
        self._progress_pane.set_progress(1.0)
        GLib.idle_add(self._model.check)

    def _checked(self, packages):
        available_packages = len(packages)
        if not available_packages:
            top_message = _('Your software is up-to-date')
        else:
            top_message = ngettext('You can install %s update',
                                   'You can install %s updates',
                                   available_packages)
            top_message = top_message % available_packages
            top_message = GObject.markup_escape_text(top_message)

        self._top_label.set_markup('<big>%s</big>' % top_message)

        if not available_packages:
            self._clear_center()
        else:
            self._switch_to_update_box(packages)
            GLib.idle_add(self._model.check_size,
                          self._update_box.get_packages_to_update())

    def _updated(self, packages):
        num_installed = len(packages)
        top_message = ngettext('%s update was installed',
                               '%s updates were installed', num_installed)
        top_message = top_message % num_installed
        top_message = GObject.markup_escape_text(top_message)
        self._top_label.set_markup('<big>%s</big>' % top_message)
        self._clear_center()

    def _set_toolbar_cancellable(self, cancellable):
        self.props.is_cancellable = cancellable
        self.props.is_valid = cancellable

    def __progress_cb(self, model, progress):
        self._switch_to_progress_pane()
        self._progress_pane.set_progress(progress)
        if self.props.is_valid is True:
            self.props.is_valid = False

    def __detail_cb(self, model, description):
        self._progress_pane.set_message(description)

    def __refresh_button_clicked_cb(self, button):
        self._refresh()

    def __install_button_clicked_cb(self, button):
        GLib.idle_add(self._model.update,
                      self._update_box.get_packages_to_update())

    def __cancel_button_clicked_cb(self, button):
        self._model.cancel()

    def __cancellable_cb(self, model, cancellable):
        if self._progress_pane:
            self._progress_pane.set_cancellable(cancellable)
        self._set_toolbar_cancellable(cancellable)

    def __finished_cb(self, model, status, packages):
        logging.debug('__finished_cb')
        self._set_toolbar_cancellable(True)
        if status == model.EXIT_FAILED:
            self._switch_to_error()
        elif status == model.EXIT_CANCELLED:
            self._switch_to_cancelled()
        else:
            self._switch_to_success(packages)

    def __size_cb(self, model, size):
        if self._update_box:
            self._update_box._update_total_size_label(size)

    def __selection_changed_cb(self, list_model, path, iterator):
        logging.debug('__selection_changed_cb')
        packages = self._update_box.get_packages_to_update()
        if packages:
            self._model.check_size(packages)

    def undo(self):
        self._model.cancel()


class ProgressPane(Gtk.VBox):
    """Container which replaces the `ActivityPane` during refresh or
    install."""

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.set_spacing(style.DEFAULT_PADDING)
        self.set_border_width(style.DEFAULT_SPACING * 2)

        self._progress = Gtk.ProgressBar()
        self.pack_start(self._progress, True, True, 0)
        self._progress.show()

        self._label = Gtk.Label()
        self._label.set_line_wrap(True)
        self._label.set_property('xalign', 0.5)
        self._label.modify_fg(Gtk.StateType.NORMAL,
                              style.COLOR_BUTTON_GREY.get_gdk_color())
        self.pack_start(self._label, True, True, 0)
        self._label.show()

        alignment_box = Gtk.Alignment.new(xalign=0.5, yalign=0.5,
                                          xscale=0, yscale=0)
        self.pack_start(alignment_box, True, True, 0)
        alignment_box.show()

        self.cancel_button = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        alignment_box.add(self.cancel_button)
        self.cancel_button.show()

    def set_message(self, message):
        self._label.set_text(message)

    def set_progress(self, fraction):
        self._progress.props.fraction = fraction

    def set_cancellable(self, cancellable):
        self.cancel_button.set_sensitive(cancellable)


class UpdateBox(Gtk.VBox):

    def __init__(self, packages):
        Gtk.VBox.__init__(self)

        self.set_spacing(style.DEFAULT_PADDING)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show()

        self._package_list = PackageList(packages)
        self._package_list.props.model.connect('row-changed',
                                               self.__row_changed_cb)
        scrolled_window.add(self._package_list)
        self._package_list.show()

        bottom_box = Gtk.HBox()
        bottom_box.set_spacing(style.DEFAULT_SPACING)
        self.pack_start(bottom_box, False, True, 0)
        bottom_box.show()

        self._size_label = Gtk.Label()
        self._size_label.props.xalign = 0
        self._size_label.set_justify(Gtk.Justification.LEFT)
        bottom_box.pack_start(self._size_label, True, True, 0)
        self._size_label.show()

        self.refresh_button = Gtk.Button(stock=Gtk.STOCK_REFRESH)
        bottom_box.pack_start(self.refresh_button, False, True, 0)
        self.refresh_button.show()

        self.install_button = Gtk.Button(_('Install selected'))
        self.install_button.props.image = Icon(
            icon_name='emblem-downloads',
            pixel_size=style.SMALL_ICON_SIZE)
        bottom_box.pack_start(self.install_button, False, True, 0)
        self.install_button.show()

        self._update_total_size_label(_('calculating...'))

    def get_packages_to_update(self):
        packages_to_update = []
        for row in self._package_list.props.model:
            if row[PackageListModel.SELECTED]:
                packages_to_update.append(row[PackageListModel.ID])
        return packages_to_update

    def _update_total_size_label(self, size):
        if not isinstance(size, str):
            size = _format_size(size)
        markup = _('Download size: %s') % size
        self._size_label.set_markup(markup)

    def _update_install_button(self):
        for row in self._package_list.props.model:
            if row[PackageListModel.SELECTED]:
                self.install_button.props.sensitive = True
                return
        self.install_button.props.sensitive = False

    def __row_changed_cb(self, list_model, path, iterator):
        packages = self.get_packages_to_update()
        if packages:
            self._update_total_size_label(_('calculating...'))
        else:
            self._update_total_size_label(0)
        self._update_install_button()


class PackageList(Gtk.TreeView):

    def __init__(self, packages):
        list_model = PackageListModel(packages)
        Gtk.TreeView.__init__(self, list_model)

        self.set_reorderable(False)
        self.set_enable_search(False)
        self.set_headers_visible(False)

        # select
        select_renderer = Gtk.CellRendererToggle()
        select_renderer.props.activatable = True
        select_renderer.props.xpad = style.DEFAULT_PADDING
        select_renderer.props.indicator_size = style.zoom(26)
        select_renderer.connect('toggled', self.__toggled_cb)

        select_column = Gtk.TreeViewColumn()
        select_column.pack_start(select_renderer, True)
        select_column.add_attribute(select_renderer, 'active',
                                    PackageListModel.SELECTED)
        self.append_column(select_column)

        # package
        package_renderer = Gtk.CellRendererText()

        package_column = Gtk.TreeViewColumn()
        package_column.pack_start(package_renderer, True)
        package_column.add_attribute(package_renderer, 'markup',
                                     PackageListModel.PACKAGE)
        self.append_column(package_column)

        # version
        version_renderer = Gtk.CellRendererText()

        version_column = Gtk.TreeViewColumn()
        version_column.pack_start(version_renderer, True)
        version_column.add_attribute(version_renderer, 'markup',
                                     PackageListModel.VERSION)
        self.append_column(version_column)

    def __toggled_cb(self, cell_renderer, path):
        row = self.props.model[path]
        row[PackageListModel.SELECTED] = not row[PackageListModel.SELECTED]


class PackageListModel(Gtk.ListStore):

    ID = 0
    PACKAGE = 1
    VERSION = 2
    SELECTED = 3

    def __init__(self, packages):
        Gtk.ListStore.__init__(self, str, str, str, bool)

        for package in packages:
            _id = package
            _package, _version = _id.split('=')
            row = []
            row.append(_id)
            row.append(_package)
            row.append(_version)
            row.append(True)
            self.append(row)


def _format_size(size):
    """Convert a given size in bytes to a nicer better readable unit"""
    if size == 0:
        # TRANS: download size is 0
        return _('None')
    elif size < 1024:
        # TRANS: download size of very small updates
        return _('1 KB')
    elif size < 1024 * 1024:
        # TRANS: download size of small updates, e.g. '250 KB'
        return locale.format_string(_('%.0f KB'), size / 1024.0)
    else:
        # TRANS: download size of updates, e.g. '2.3 MB'
        return locale.format_string(_('%.1f MB'), size / 1024.0 / 1024)
