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

    progress_signal = GObject.Signal('progress',
                                     arg_types=([int, float, object]))
    finished_signal = GObject.Signal('finished',
                                     arg_types=([int, bool, object]))
    error_signal = GObject.Signal('error',
                                   arg_types=([str]))

    def __init__(self):
        GObject.GObject.__init__(self)
        self._client = apt.AptClient()
        self._state = None
        self._client.clean(wait=True)

    def get_state(self):
        return self._state

    def refresh(self):
        logging.debug('refresh-in')
        self._state = self.STATE_REFRESHING
        transaction = self._client.update_cache()
        transaction.connect('progress-details-changed', self.__details_cb)
        transaction.connect('finished', self.__refresh_finished_cb)
        transaction.connect('error', self.__error_cb)
        transaction.run()
        logging.debug('refresh-out')

    def check(self):
        logging.debug('check-in')
        self._state = self.STATE_CHECKING
        transaction = self._client.upgrade_system()
        transaction.connect('dependencies-changed', self.__check_finished_cb)
        transaction.connect('error', self.__error_cb)
        GLib.idle_add(transaction.simulate)
        logging.debug('check-out')

    def update(self, packages):
        logging.debug('update-in')
        self._state = self.STATE_UPDATING
        transaction = self._client.upgrade_packages(packages)
        transaction.connect('progress-download-changed', self.__download_cb)
        transaction.connect('finished', self.__update_finished_cb)
        transaction.connect('error', self.__error_cb)
        transaction.run()
        logging.debug('update-out')

    def cancel(self):
        pass

    def __error_cb(self, transaction, code, details):
        logging.debug('__error_cb %s', str(code))
        try:
            transaction.cancel()
        except:
            logging.error('Could not cancel transaction.')
        self.error_signal.emit(code)

    def __refresh_finished_cb(self, transaction, status):
        logging.debug('__updates_finished_cb %s', status)
        if status != 'exit-success':
            self.error_signal.emit(status)
        else:
            self.finished_signal.emit(self._state, True, None)

    def __check_finished_cb(self, transaction, installs, reinstalls,
                            removals, purges, upgrades, downgrades, kepts):
        logging.debug('__check_finished_cb')
        packages = []
        for package in upgrades:
            name, version = package.split('=')
            if name.endswith('activity'):
                packages.append(str(package))
        self.finished_signal.emit(self._state, True, packages)

    def __update_finished_cb(self, transaction, status):
        logging.debug('__update_finished_cb %s', status)
        if status != 'exit-success':
            self.error_signal.emit(status)
            return
        packages = []
        for package in transaction.packages[4]:
            packages.append(str(package))
        self.finished_signal.emit(self._state, True, packages)

    def __details_cb(self, transaction, current_items, total_items,
                     current_bytes, total_bytes, current_cps, eta):
        logging.debug('__details_cb %d:%d bytes', current_bytes, total_bytes)
        logging.debug('__details_cb %d:%d items', current_items, total_items)

        if self._state == self.STATE_REFRESHING:
            progress = 0
            if total_items > 0:
                progress = float(current_items) / float(total_items)
        elif self._state == self.STATE_CHECKING:
            progress = 1.0
        elif self._state == self.STATE_UPDATING:
            progress = 1.0

        self.progress_signal.emit(self._state, progress, None)

    def __download_cb(self, transaction, uri, status, description,
                      total_bytes, current_bytes, extra):
        logging.debug('__download_cb %s %s %s',
                      description, str(current_bytes), str(total_bytes))
        self.progress_signal.emit(self._state, float(current_bytes) / float(total_bytes), description)
