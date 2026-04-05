# -*- encoding: utf-8 -*-
import ue

class GameInstanceProxy(object):
    def init(self):
        game_instance = self.uobject # type: ue.GameInstance
        ue.LogWarning('GameInstance init! %s' % game_instance)

    def shutdown(self):
        ue.LogWarning('GameInstance shutdown!')