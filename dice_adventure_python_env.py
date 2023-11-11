

class DiceAdventurePythonEnv:
    def __init__(self, game, player="X"):
        self.game = game
        self.player = player
        self.action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                           5: 'submit', 6: 'PA', 7: 'PB', 8: 'PC', 9: 'PD', 10: 'undo'}

    def close(self):
        pass

    def render(self, mode='console'):
        if not self.game.render:
            self.game.render()

    def reset(self):
        pass

    def step(self, action, player=None):
        if not player:
            player = self.player
        self.game.send_action(player, self.action_map[action])
        next_state = self.game.get_state()

    def get_observation(self):
        # new_obs, reward, terminated, truncated, info
        # TODO CHECK IF PLAYER IS AT GOAL (REMEMBER TO REMOVE GOAL)
        pass
    """
    def at_goal(self):
        return all([all([i["x"] == j["x"] for i in self.objects.values() for j in self.objects.values()]),
                    all([i["y"] == j["y"] for i in self.objects.values() for j in self.objects.values()])
                    ])
    """