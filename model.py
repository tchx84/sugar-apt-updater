
STATE_IDLE = 0
STATE_CHECKING = 1
STATE_CHECKED = 2
STATE_DOWNLOADING = 3
STATE_UPDATING = 4

class SystemUpdaterModel(object):

    def __init__(self):
        self._state = STATE_IDLE

    def get_state(self):
        return self._state

    def check_updates(self):
        pass

    def updates(self, packages):
        pass

    def cancel(self):
        pass
