from collections import Counter
from copy import deepcopy
from datetime import datetime
from dice_adventure import DiceAdventure
from gymnasium import Env
from gymnasium import spaces
from json import dumps
import numpy as np
from os import makedirs
from os import path
from random import choice
from stable_baselines3 import PPO
from time import sleep

"""
Assumptions:
1. step(): Previous state is based on resulting state of previous action, not the state right before taking the action.
"""


class DiceAdventurePythonEnv(Env):
    def __init__(self, id_, player, model_filename, track_metrics=False, **kwargs):
        """
        :param game: A Dice Adventure game object
        'player'
        """
        self.id = id_
        print(self.id)
        self.game = None
        self.prev_state = None
        self.kwargs = kwargs
        self.player = player
        self.player_num = 0
        self.players = {"3S": "Human", "1S": "Dwarf", "2S": "Giant"}
        self.player_ids = ["1S", "2S", "3S"]

        self.masks = {"1S": 1, "2S": 2, "3S": 3}
        self.max_mask_radius = max(self.masks.values())
        self.local_mask_radius = self.masks[self.player]
        self.action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                           5: 'submit', 6: 'PA', 7: 'PB', 8: 'PC', 9: 'PD', 10: 'undo'}

        self.goals = {"1S": False, "2S": False, "3S": False}
        self.pin_mapping = {"A": 0, "B": 1, "C": 2, "D": 3}

        self.time_steps = 0
        self.load_threshold = 500000
        self.model_filename = model_filename
        self.model = None

        num_actions = len(self.action_map)
        self.action_space = spaces.Discrete(num_actions)
        # The observation will be the coordinate of the agent
        # this can be described both by Discrete and Box space
        self.mask_size = self.max_mask_radius * 2 + 1
        vector_len = self.mask_size * self.mask_size * len(self.get_type_positions()) * 4
        self.observation_space = spaces.Box(low=-5, high=100,
                                            shape=(vector_len,), dtype=np.float32)

        # Metrics
        self.metrics_dir = "metrics"
        makedirs(self.metrics_dir, exist_ok=True)
        self.track_metrics = track_metrics
        self.metrics_save_threshold = 10000
        self.rewards_tracker = []

    def step(self, action):
        # Update model for other players
        self.time_steps += 1
        if self.time_steps % self.load_threshold == 0:
            if path.exists(self.model_filename):
                self.model = PPO.load(self.model_filename)
        game_action = self.action_map[action]
        # Execute action of agent
        self.game.execute_action(self.player, game_action)

        # Get next state
        next_state = self.game.get_state()
        p1 = self.get_obj_from_scene_by_type(self.prev_state, self.players[self.player])
        p2 = self.get_obj_from_scene_by_type(next_state, self.players[self.player])

        # If player is dead, must wait until alive again
        while p2["dead"]:
            self.play_others(game_action, self.prev_state, next_state)
            self.prev_state = deepcopy(next_state)
            next_state = self.game.get_state()
            p2 = self.get_obj_from_scene_by_type(next_state, self.players[self.player])
            break
        else:
            # Simulate other players
            self.play_others(game_action, self.prev_state, next_state)
            self.prev_state = next_state

        # new_obs, reward, terminated, truncated, info
        new_obs = self.get_observation(next_state)
        reward = self.get_reward(p1, p2, self.prev_state, next_state)
        terminated = self.game.terminated
        truncated = False
        info = {}

        self.save_metrics()

        return new_obs, reward, terminated, truncated, info

    def play_others(self, game_action, state, next_state):
        # Play as other players (temporary)
        for p in self.players:
            if p != self.player:
                # Only force submit on other characters if case where self.player clicking submit does not
                # change the game phase (otherwise, these players will just forfeit their turns immediately)
                if game_action == "submit" \
                        and state["content"]["gameData"]["currentPhase"] == next_state["content"]["gameData"]["currentPhase"]:
                    a = game_action
                elif self.model:
                    a, _states = self.model.predict(self.get_observation(next_state, player=p))
                else:
                    a = choice(self.action_map)
                self.game.execute_action(p, a)
                next_state = self.game.get_state()

    def close(self):
        pass

    def render(self, mode='console'):
        if not self.game.render:
            self.game.render()

    def reset(self, **kwargs):
        self.game = DiceAdventure(**self.kwargs)
        self.prev_state = self.game.get_state()
        return self.get_observation(self.prev_state), {}

    def get_reward(self, p1, p2, state, next_state):
        # Get reward
        """
        Rewards:
        1. Player getting goal + small
        2. Players getting to tower after getting all goals + small
        3. Winning combat

        Penalties:
        1. Player losing health
        2.
        """
        r = 0
        # Player getting goal
        if self.goal_reached(state, next_state):
            r += .5
        # Players getting to tower after getting all goals
        if self.check_new_level(next_state):
            r += 1
        if self.health_lost(p1, p2):
            r -= 1

        if self.track_metrics:
            self.rewards_tracker.append([self.time_steps,
                                         datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f'),
                                         str(r),
                                         state["content"]["gameData"]["level"],
                                         state["content"]["gameData"]["num_repeats"],
                                         self.player])
        #if r > 0:
        #    print(r)
        return r

    def goal_reached(self, state, next_state):
        # no goal in prev state, goal in next state
        # no goal in either state but next state is new level
        g1 = self.get_obj_from_scene_by_type(state, "shrine")
        g2 = self.get_obj_from_scene_by_type(next_state, "shrine")

        # Goal has now been reached since previous state
        # OR goal was not reached in previous state but either:
        # 1. level has changed meaning it would have been reached, OR
        # 2. The level is the same but has repeated, indicated by the num_repeats field incrementing
        # Repeating in this way does not apply to team losses and level resets
        return (not g1["reached"] and g2["reached"]) \
            or (not g1["reached"]
                and (state["content"]["gameData"]["level"] != next_state["content"]["gameData"]["level"]
                     or state["content"]["gameData"]["num_repeats"] < next_state["content"]["gameData"]["num_repeats"]))

    def check_new_level(self, next_state):
        return self.prev_state["content"]["gameData"]["level"] < next_state["content"]["gameData"]["level"] or \
            (self.prev_state["content"]["gameData"]["level"] == next_state["content"]["gameData"]["level"] and
             self.prev_state["content"]["gameData"]["num_repeats"] < next_state["content"]["gameData"]["num_repeats"])

    def health_lost(self, p1, p2):
        """
        Checks difference between previous and next state to determine if a player has lost health or died
        :param next_state: The state resulting from the previous action
        :return: True if a player has lost health or died, False otherwise
        """
        return (p1["health"] < p2["health"]) or (not p1["dead"] and p2["dead"])

    @staticmethod
    def get_obj_from_scene_by_type(state, obj_type):
        o = None
        for ele in state["content"]["scene"]:
            if ele.get("type") == obj_type:
                o = ele
                break
        if o is None:
            print(state)
        return o

    def get_observation(self, state, player=None):
        """
        Constructs an array observation for agent based on state. Dimensions:
        1. self.mask x self.mask (1-2)
        2. len(get_type_positions()) (3)
        3. 4 (4) - max number of object types is 4 [i.e., M4]
        Total Est.: 5x5x10x4 = 1000
        :param state:
        :return:
        """
        type_pos = self.get_type_positions()
        x = None
        y = None
        p_info = np.array([])

        if player is None:
            player = self.player

        for i in state["content"]["scene"]:
            if i["type"] == self.players[player]:
                x = i["x"]
                y = i["y"]
                # p_info = self.parse_player_state_data(i)
                break

        x_bound_upper = x + self.local_mask_radius
        x_bound_lower = x - self.local_mask_radius
        y_bound_upper = y + self.local_mask_radius
        y_bound_lower = y - self.local_mask_radius

        grid = np.zeros((self.mask_size, self.mask_size, len(type_pos), 4))
        for obj in state["content"]["scene"]:
            if obj["type"] in type_pos and obj["x"] and obj["y"]:
                if x_bound_lower <= obj["x"] <= x_bound_upper and \
                        y_bound_lower <= obj["y"] <= y_bound_upper:
                    other_x = self.local_mask_radius - (x - obj["x"])
                    other_y = self.local_mask_radius - (y - obj["y"])
                    # For enemies or pins, determine which type
                    obj_type = obj["name"][0]
                    if obj_type in ["M", "T", "S", "P"]:
                        if obj_type == "P":
                            version = self.pin_mapping[obj["name"][1]]
                        else:
                            version = int(obj["name"][1]) - 1

                        grid[other_x][other_y][type_pos[obj["type"]]][version] = 1
                    else:
                        grid[other_x][other_y][type_pos[obj["type"]]][0] = 1

        return np.concatenate((np.ndarray.flatten(grid), p_info))

    @staticmethod
    def parse_player_state_data(p_info):
        state_map = {
            "action_points": {"pos": 0, "map": {}},
            "max_points": {"pos": 1, "map": {}},
            "health": {"pos": 2, "map": {}},
            "status": {"pos": 3, "map": {"dead": 0, "alive": 1}},
            "respawn_counter": {"pos": 4, "map": {None: -1, 0: 0, 1: 1}},
            "goal_reached": {"pos": 5, "map": {False: 0, True: 1}},
            "pin_path_x": {"pos": 6, "map": {None: -1}},
            "pin_path_y": {"pos": 7, "map": {None: -1}},
            "pin_finalized": {"pos": 8, "map": {False: 0, True: 1}},
            "pin_plan_finalized": {"pos": 9, "map": {False: 0, True: 1}},
            "action_path_x": {"pos": 10, "map": {None: -1}},
            "action_path_y": {"pos": 11, "map": {None: -1}},
            "action_plan_finalized": {"pos": 12, "map": {False: 0, True: 1}}
        }
        vector = np.zeros((len(state_map,)))
        for field in state_map:
            data = p_info[field]
            # Value should come from mapping
            if data in state_map[field]["map"]:
                vector[state_map[field]["pos"]] = state_map[field]["map"][data]
            # Otherwise, value is scalar
            else:
                vector[state_map[field]["pos"]] = data
        return vector

    @staticmethod
    def get_type_positions():
        return {'human': 0, 'dwarf': 1, 'giant': 2, 'goal': 3,
                'door': 4, 'wall': 5, 'monster': 6, 'trap': 7,
                'rock': 8, 'tower': 9, 'pin': 10}

    def save_metrics(self):
        if self.track_metrics:
            # Save rewards logs
            if len(self.rewards_tracker) >= self.metrics_save_threshold:
                filename = f"{self.metrics_dir}/rewards_over_time_-{self.players[self.player]}-id-{self.id}.txt"
                with open(filename,
                          "a" if path.exists(filename) else "w") as file:
                    for i in self.rewards_tracker:
                        file.write(",".join([str(ele) for ele in i])+"\n")
                self.rewards_tracker = []
