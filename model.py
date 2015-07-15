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

import logging

from gi.repository import GLib
from gi.repository import GObject
from aptdaemon import client as apt


class SystemUpdaterModel(GObject.GObject):

    STATE_IDLE = 0
    STATE_REFRESHING = 1
    STATE_CHECKING = 2
    STATE_UPDATING = 3

    EXIT_SUCCESS = 0
    EXIT_FAILED = 1
    EXIT_CANCELLED = 2

    progress_signal = GObject.Signal('progress',
                                     arg_types=([float]))
    progress_detail_signal = GObject.Signal('progress-detail',
                                            arg_types=([str]))
    finished_signal = GObject.Signal('finished',
                                     arg_types=([int, object]))
    cancellable_signal = GObject.Signal('cancellable',
                                        arg_types=([bool]))
    size_signal = GObject.Signal('size',
                                 arg_types=([int]))

    def __init__(self):
        GObject.GObject.__init__(self)
        self._client = apt.AptClient()
        self._state = None
        self._transaction = None
        self._client.clean(wait=True)

    def get_state(self):
        return self._state

    def refresh(self):
        logging.debug('refresh-in')
        self._state = self.STATE_REFRESHING
        self._transaction = self._client.update_cache()
        self._transaction.connect('progress-details-changed', self.__refresh_progress_cb)
        self._transaction.connect('progress-download-changed', self.__refresh_detail_cb)
        self._transaction.connect('finished', self.__refresh_finished_cb)
        self._transaction.connect('cancellable-changed', self.__cancellable_cb)
        self._transaction.run()
        logging.debug('refresh-out')

    def check(self):
        logging.debug('check-in')
        self._state = self.STATE_CHECKING
        self._transaction = self._client.upgrade_system()
        self._transaction.connect('dependencies-changed', self.__check_finished_cb)
        GLib.idle_add(self._transaction.simulate)
        logging.debug('check-out')

    def check_size(self, packages):
        logging.debug('check-size-in')
        transaction = self._client.upgrade_packages(packages)
        transaction.connect('download-changed', self.__check_size_cb)
        GLib.idle_add(transaction.simulate)
        logging.debug('check-size-out')

    def update(self, packages):
        logging.debug('update-in')
        self._state = self.STATE_UPDATING
        self._transaction = self._client.upgrade_packages(packages)
        self._transaction.connect('progress-download-changed', self.__update_progress_cb)
        self._transaction.connect('finished', self.__update_finished_cb)
        self._transaction.connect('cancellable-changed', self.__cancellable_cb)
        self._transaction.run()
        logging.debug('update-out')

    def cancel(self):
        if self._transaction and self._transaction.cancellable:
            self._transaction.cancel()

    def _convert_status(self, status):
        if status == 'exit-success':
            status = self.EXIT_SUCCESS
        elif status == 'exit-cancelled':
            status = self.EXIT_CANCELLED
        else:
            status = self.EXIT_FAILED
        return status

    def __refresh_finished_cb(self, transaction, status):
        logging.debug('__refresh_finished_cb %s', status)
        self.finished_signal.emit(self._convert_status(status), None)

    def __check_finished_cb(self, transaction, installs, reinstalls,
                            removals, purges, upgrades, downgrades, kepts):
        logging.debug('__check_finished_cb')
        packages = []
        for package in upgrades:
            name, version = package.split('=')
            if name.endswith('activity'):
                packages.append(str(package))
        self.finished_signal.emit(self.EXIT_SUCCESS, packages)

    def __update_finished_cb(self, transaction, status):
        logging.debug('__update_finished_cb %s', status)
        packages = []
        for package in transaction.packages[4]:
            packages.append(str(package))
        self.finished_signal.emit(self._convert_status(status), packages)

    def __refresh_progress_cb(self, transaction, current_items, total_items,
                     current_bytes, total_bytes, current_cps, eta):
        logging.debug('__refresh_progress_cb %d:%d items', current_items, total_items)
        progress = 0
        if total_items > 0:
            progress = float(current_items) / float(total_items)
        self.progress_signal.emit(progress)

    def __refresh_detail_cb(self, transaction, uri, status, description,
                             total_bytes, current_bytes, extra):
        logging.debug('__refresh_detail_cb %s', description)
        self.progress_detail_signal.emit(description)

    def __update_progress_cb(self, transaction, uri, status, description,
                      total_bytes, current_bytes, extra):
        logging.debug('__update_progress_cb %s %s %s',
                      description, str(current_bytes), str(total_bytes))
        self.progress_signal.emit(float(current_bytes) / float(total_bytes))
        self.progress_detail_signal.emit(description)

    def __cancellable_cb(self, transaction, cancellable):
        logging.debug('__cancellable_cb %r', cancellable)
        self.cancellable_signal.emit(cancellable)

    def __check_size_cb(self, transaction, download):
        logging.debug('__check_size_cb %d', download)
        self.size_signal.emit(download)
