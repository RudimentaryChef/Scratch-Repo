from gymnasium import spaces
import numpy as np


class DiceAdventurePythonEnv:
    def __init__(self, game, player="1S", all_players=True):
        """
        :param game: A Dice Adventure game object
        :param player: The player to play as
        :param all_players: Determines whether agent plays as all players or only the player provided in parameter
        'player'
        """
        self.game = game
        self.player = player
        self.types = {"1S": "human", "2S": "dwarf", "3S": "giant"}
        self.mask = 5
        self.action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                           5: 'submit', 6: 'PA', 7: 'PB', 8: 'PC', 9: 'PD', 10: 'undo'}
        self.levels = {}

        num_actions = len(self.action_map)
        self.action_space = spaces.Discrete(num_actions)
        # The observation will be the coordinate of the agent
        # this can be described both by Discrete and Box space
        vector_len = self.mask * self.mask * len(self.get_type_positions()) * 4
        self.observation_space = spaces.Box(low=0, high=100,
                                            shape=(vector_len,), dtype=np.float32)

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
        state = self.game.get_state()
        self.game.execute_action(player, self.action_map[action])
        next_state = self.game.get_state()

        reward = self.get_reward(state, next_state)

    @staticmethod
    def get_reward(state, next_state):
        # Get reward
        """
        Rewards:
        1. Player getting goal
        2. Players getting to tower after getting all goals

        Penalties:
        1. Player losing health
        """
        return 0

    def get_observation(self, state):
        """
        Constructs an array observation for agent based on state. Dimensions:
        1. self.mask x self.mask (1-2)
        2. len(get_type_positions()) (3)
        3. 4 (4) - max number of object types is 4 [i.e., M4]
        Total Est.: 5x5x10x4 = 1000
        :param state:
        :return:
        """
        # new_obs, reward, terminated, truncated, info
        type_pos = self.get_type_positions()
        x = None
        y = None
        for i in state["scene"]:
            if i["type"] == self.types[self.player]:
                x = i["x"]
                y = i["y"]
                break
        ego_x = int(self.mask / 2)
        ego_y = int(self.mask / 2)

        offset = ((self.mask - 1) / 2)
        x_bound_upper = x + offset
        x_bound_lower = x - offset
        y_bound_upper = y + offset
        y_bound_lower = y - offset

        grid = np.zeros((self.mask, self.mask, len(type_pos), 4))
        for obj in state["scene"]:
            if x_bound_lower <= obj["x"] <= x_bound_upper and \
                    y_bound_lower <= obj["y"] <= y_bound_upper:
                other_x = ego_x - (x - obj["x"])
                other_y = ego_y - (y - obj["y"])

                if obj["name"][0] in ["M", "T", "S"]:
                    enemy_lvl = int(obj["name"][1]) - 1
                    grid[other_x][other_y][type_pos[obj["type"]]][enemy_lvl] = 1
                else:
                    grid[other_x][other_y][type_pos[obj["type"]]][0] = 1

        return np.ndarray.flatten(grid)

    @staticmethod
    def get_type_positions():
        return {'human': 0, 'dwarf': 1, 'giant': 2, 'goal': 3,
                'door': 4, 'wall': 5, 'monster': 6, 'trap': 7,
                'rock': 8, 'tower': 9}
