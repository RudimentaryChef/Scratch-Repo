from copy import deepcopy
from datetime import datetime
from dice_adventure import DiceAdventure
from gymnasium import Env
from gymnasium import spaces
from json import loads
import numpy as np
from os import listdir
from os import makedirs
from os import path
from random import choice
from random import seed
from stable_baselines3 import PPO
import unity_socket
import re
import pprint
pp = pprint.PrettyPrinter(indent=2)


class DiceAdventurePythonEnv(Env):
    def __init__(self, id_,
                 player,
                 model_number,
                 env_metrics=False,
                 train_mode=False,
                 server="local",
                 observation_type="vector",
                 automate_players=True,
                 random_players=False,
                 set_random_seed=False,
                 **kwargs):
        self.id = id_
        print(f"INITIALIZING ENV {self.id}...")
        if set_random_seed:
            seed(self.id)

        self.game = None
        self.config = self.config = loads(open("config/main_config.json", "r").read())
        self.reward_codes = self.config["GYM_ENVIRONMENT"]["REWARD"]["CODES"]
        self.observation_object_positions = self.config["GYM_ENVIRONMENT"]["OBSERVATION"]["OBJECT_POSITIONS"]
        self.object_size_mappings = self.config["OBJECT_INFO"]["ENEMIES"]["ENEMY_SIZE_MAPPING"]
        self.kwargs = kwargs
        self.player_num = 0
        self.players = ["Dwarf", "Giant", "Human"]
        # self.players = {"1S": "Dwarf", "2S": "Giant", "3S": "Human", "Dwarf": "1S", "Giant": "2S", "Human": "3S"}
        self.player_ids = ["1S", "2S", "3S"]
        # self.player = self.players[player]
        self.player = player
        self.automate_players = automate_players
        self.random_players = random_players

        # self.masks = {"1S": 1, "2S": 3, "3S": 2}
        self.masks = {"Dwarf": 1, "Giant": 3, "Human": 2}
        self.max_mask_radius = max(self.masks.values())
        self.local_mask_radius = self.masks[self.player]
        self.action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                           5: 'submit', 6: 'pinga', 7: 'pingb', 8: 'pingc', 9: 'pingd', 10: 'undo'}
        # pingA, pingB, etc.

        self.goals = {"1S": False, "2S": False, "3S": False}
        self.pin_mapping = {"A": 0, "B": 1, "C": 2, "D": 3}

        self.time_steps = 0
        self.load_threshold = 110000
        self.model_number = model_number
        self.model_dir = "train/{}/model/".format(self.model_number)
        self.model = None

        ##################
        # TRAIN SETTINGS #
        ##################

        self.train_mode = train_mode

        ################
        # ENV SETTINGS #
        ################

        num_actions = len(self.action_map)
        self.action_space = spaces.Discrete(num_actions)
        # The observation will be the coordinate of the agent
        # this can be described both by Discrete and Box space
        self.mask_size = self.max_mask_radius * 2 + 1
        vector_len = (self.mask_size * self.mask_size * len(set(self.observation_object_positions.values())) * 4) + 6
        self.observation_space = spaces.Box(low=-5, high=100,
                                            shape=(vector_len,), dtype=np.float32)
        ###################
        # METRIC TRACKING #
        ###################
        self.metrics_dir = self.config["GYM_ENVIRONMENT"]["METRICS"]["DIRECTORY"].format(model_number)
        makedirs(self.metrics_dir, exist_ok=True)
        self.track_metrics = env_metrics
        self.metrics_save_threshold = 10000
        # Reward tracking
        self.rewards_tracker = []
        self.num_games = 0

        # Server type
        self.server = server
        self.unity_socket_url = self.config["GYM_ENVIRONMENT"]["UNITY"]["URL"]

        if self.server == "local":
            self.create_game()
        self.prev_observed_state = self.get_state()

    def step(self, action, player=None):
        if player is None:
            player = self.player
        action = int(action)
        self.time_steps += 1
        # Update model for use by other players
        self.check_for_new_model()

        state = self.get_state()
        # Execute action and get next state
        game_action = self.action_map[action]
        next_state = self.execute_action(player, game_action)

        # pstate_1 = self.get_obj_from_scene_by_type(self.prev_state, self.players[player])
        pstate_1 = self.get_obj_from_scene_by_type(state, player)
        pstate_2 = self.get_obj_from_scene_by_type(next_state, player)

        # Determine reward based on change in state
        # reward = self.get_reward(pstate_1, pstate_2, self.prev_state, next_state)
        reward = self.get_reward(pstate_1, pstate_2, self.prev_observed_state, next_state)

        # Update previous state to current one
        # Should update this before
        self.prev_observed_state = deepcopy(next_state)

        # Simulate other players
        if self.automate_players:
            self.play_others(game_action, self.prev_observed_state, next_state)
            next_state = self.get_state()

        # new_obs, reward, terminated, truncated, info
        # TODO define termination for local game and unity version
        terminated = next_state["status"] == "Done"
        if terminated:
            new_obs, info = self.reset()
        else:
            new_obs = self.get_observation(next_state)
            info = {}
        truncated = False
        # Track metrics
        self.save_metrics()

        return new_obs, reward, terminated, truncated, info

    def close(self):
        pass

    def render(self, mode='console'):
        if self.server == "local":
            self.game.render()
        else:
            pass

    def reset(self, **kwargs):
        if self.server == "local":
            self.create_game()
            state = self.get_state()
            obs = self.get_observation(state)
        else:
            state = self.get_state()
            obs = self.get_observation(state)
        return obs, {}

    def execute_action(self, player, game_action):
        if self.server == "local":
            self.game.execute_action(player, game_action)
        else:
            url = self.unity_socket_url.format(player.lower())
            unity_socket.execute_action(url, game_action)
        return self.get_state()

    def get_state(self, player="dwarf"):
        if self.server == "local":
            state = self.game.get_state()
        else:
            url = self.unity_socket_url.format(player)
            state = unity_socket.get_state(url)
        return state

    ###########
    # HELPERS #
    ###########

    def play_others(self, game_action, state, next_state):
        # Play as other players
        for p in self.players:
            if p != self.player:
                # Only force submit on other characters if case where self.player clicking submit does not
                # change the game phase (otherwise, these players will just forfeit their turns immediately)
                if game_action == "submit" \
                        and state["content"]["gameData"]["currentPhase"] == next_state["content"]["gameData"]["currentPhase"]:
                    a = game_action
                elif self.model and not self.random_players:
                    a, _states = self.model.predict(self.get_observation(next_state, player=p))
                    # Need to convert to python int
                    a = self.action_map[int(a)]
                else:
                    a = choice(list(self.action_map.values()))
                # print(f"Other Player: {p}: Action: {a}")
                _ = self.execute_action(p, a)
                # next_state = self.get_state()

    def check_for_new_model(self):
        if self.automate_players:
            if self.time_steps % self.load_threshold == 0:
                self.model, _ = load_model(self.model_dir)

    def create_game(self):
        self.kwargs["model_number"] = self.model_number
        self.game = DiceAdventure(**self.kwargs)
        self.num_games += 1
        # self.prev_state = self.game.get_state()

    def get_reward(self, p1, p2, state, next_state):
        # Get reward
        """
        Rewards:
        1. Player getting goal (0.5)
        2. Player getting to tower after getting all players have collected goals (1.0)
        3. Player winning combat (0.5) - TODO
        4. Player placing pin on object (0.1) - TODO

        Penalties:
        1. Player losing health (-1.0)
        2.
        """
        r = 0
        reward_types = []

        # Player getting goal
        if self.goal_reached(state, next_state):
            reward_types.append(self.reward_codes["0"])
            r += 1
        # Players getting to tower after getting all goals
        if self.check_new_level(state, next_state):
            reward_types.append(self.reward_codes["1"])
            r += 1
        # Player winning combat
        # if self.check_combat_outcome():
        #     r += .5
        # Player placing pin on object
        # if self.check_pin_placement(p2, next_state):
        #     r += .1
        # Player losing health
        if self.health_lost_or_dead(p1, p2):
            reward_types.append(self.reward_codes["2"])
            r -= .1

        if self.track_metrics:
            # [timestep, timestamp, player, game, level, reward_type, reward]
            self.rewards_tracker.append([self.time_steps,
                                         datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f'),
                                         self.player,
                                         str(self.num_games),
                                         state["content"]["gameData"]["level"],
                                         ",".join(reward_types),
                                         str(r)
                                         ])
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

    @staticmethod
    def check_new_level(state, next_state):
        return state["content"]["gameData"]["level"] != next_state["content"]["gameData"]["level"]
        #or \
        #    (self.prev_state["content"]["gameData"]["level"] == next_state["content"]["gameData"]["level"] and
        #     self.prev_state["content"]["gameData"]["num_repeats"] < next_state["content"]["gameData"]["num_repeats"])

    @staticmethod
    def check_pin_placement(p1, p2, next_state):
        x = p2["pinCursorX"]
        y = p2["pinCursorY"]
        # No pin placed
        if x is None or y is None:
            return False

        for obj in next_state["content"]["scene"]:
            # Pin was placed on object
            if x == obj["x"] and y == obj["y"]:
                # This check avoids giving repeated awards for placing pin. The reward should only be given once
                # Check that the location of the pin cursor from one state to the next has changed
                if p1["pinCursorX"] != p2["pinCursorX"] and p1["pinCursorY"] != p2["pinCursorY"]:
                    return True
        return False

    def check_combat_outcome(self):
        """
        Checks the outcome of a combat event. Because combat is triggered while
        players move, the resulting state of the final action plan being submitted
        may include combat during player movement or enemy movement. Thus, this function
        will check the previous and next states and use the following criteria to determine
        combat outcome. Note, during this period it is possible the player has won and lost
        combat multiple times.
            1. Need to figure this out.
        :return:
        """
        pass

    @staticmethod
    def health_lost_or_dead(p1, p2):
        """
        Checks difference between previous and next state to determine if a player has lost health or died
        :param next_state: The state resulting from the previous action
        :return: True if a player has lost health or died, False otherwise
        """
        return (p1["health"] < p2["health"]) or p2["dead"]  # or (not p1["dead"] and p2["dead"])

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
        2. len(self.observation_type_positions) (3)
        3. 4 (4) - max number of object types is 4 [i.e., M4]
        4. six additional state variables
        Total Est.: 7x7x10x4+6= 1006
        :param state:
        :return:
        """
        if player is None:
            player = self.player
        x, y, player_info = self.parse_player_state_data(state, player)

        x_bound_upper = x + self.local_mask_radius
        x_bound_lower = x - self.local_mask_radius
        y_bound_upper = y + self.local_mask_radius
        y_bound_lower = y - self.local_mask_radius

        grid = np.zeros((self.mask_size, self.mask_size, len(set(self.observation_object_positions.values())), 4))
        for obj in state["content"]["scene"]:
            if obj["type"] in self.observation_object_positions and obj["x"] and obj["y"]:
                if x_bound_lower <= obj["x"] <= x_bound_upper and \
                        y_bound_lower <= obj["y"] <= y_bound_upper:
                    other_x = self.local_mask_radius - (x - obj["x"])
                    other_y = self.local_mask_radius - (y - obj["y"])
                    # For pins and enemies, determine which type for version
                    if obj["type"] == "pin":
                        version = self.pin_mapping[obj["name"][1]]
                    # For enemies, determine which type for version
                    elif re.match("(monster|trap|stone)", obj["type"].lower()):
                        # elif obj["name"] in ["Monster", "Trap", "Stone"]:
                        version = self.object_size_mappings[obj["type"].split("_")[0]]
                    # All other objects have one version
                    else:
                        version = 0
                    grid[other_x][other_y][self.observation_object_positions[obj["type"]]][version] = 1

        return np.concatenate((np.ndarray.flatten(grid), np.ndarray.flatten(player_info)))

    @staticmethod
    def parse_player_state_data(state, player):
        # Locate player and their shrine in scene
        player_obj = None
        shrine_obj = None
        for obj in state["content"]["scene"]:
            if player_obj and shrine_obj:
                break
            if obj["type"] == player:
                player_obj = obj
            elif obj["type"] == "shrine" and obj.get("character") == player:
                shrine_obj = obj

        state_map = {
            "actionPoints": 0,
            "health": 1,
            "dead": 2,
            "reached": 3,
            "pinCursorX": 4,
            "pinCursorY": 5
        }
        value_map = {True: 1, False: 0, None: 0}
        player_info = np.zeros((len(state_map,)))

        for field in state_map:
            if field == "reached":
                data = shrine_obj[field]
            else:
                data = player_obj[field]
            # Value should come from mapping
            if data in [True, False, None]:
                player_info[state_map[field]] = value_map[data]
            # Otherwise, value is scalar
            else:
                player_info[state_map[field]] = data
        return player_obj["x"], player_obj["y"], player_info

    def save_metrics(self):
        if self.track_metrics:
            # Save rewards logs
            if len(self.rewards_tracker) >= self.metrics_save_threshold:
                filename = f"{self.metrics_dir}/rewards_over_time_-{self.player}-id-{self.id}.txt"
                with open(filename,
                          "a" if path.exists(filename) else "w") as file:
                    for i in self.rewards_tracker:
                        file.write("\t".join([str(ele) for ele in i])+"\n")
                self.rewards_tracker = []


def load_model(model_dir, env=None, device=None, tensorboard_log_dir=None):
    model_files = [model_dir + file.rstrip(".zip") for file in listdir(model_dir)]
    latest = sorted([(file, int(file.split("-")[-1])) for file in model_files], key=lambda x: x[1])[-1]
    if env or device:
        model = PPO.load(latest[0], env=env, device=device, tensorboard_log=tensorboard_log_dir)
    else:
        model = PPO.load(latest[0])
    return model, latest[1]
