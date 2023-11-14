from collections import Counter
from copy import deepcopy
from json import loads
from random import choice
from random import shuffle
import re
from tabulate import tabulate


# TODO NEED TO MAKE OBJECT_POS TRACKING MORE GENERAL SINCE MULTIPLE ENEMIES OF THE SAME TYPE CAN EXIST ON THE GRID
# TODO AT THE SAME TIME
class DiceAdventure:
    def __init__(self, level=1, render=False, render_verbose=False, num_repeats=0, restart_on_finish=False):
        # Game config
        self.config = loads(open("config.json", "r").read())
        # Level vars
        self.levels = {}
        self.get_levels()
        self.curr_level = deepcopy(self.levels[level])
        self.curr_level_num = level
        self.num_repeats = num_repeats
        self.restart_on_finish = restart_on_finish
        self.lvl_repeats = {lvl: self.num_repeats for lvl in self.levels}
        self.empty = self.config["OBJECT_INFO"]["Empty Space"]["regex"]
        self.tower = self.config["OBJECT_INFO"]["Tower"]["regex"]
        self.wall = self.config["OBJECT_INFO"]["Wall"]["regex"]
        self.player_regex = r"\dS"
        self.enemy_regexes = {"Monster": self.config["OBJECT_INFO"]["Monster"]["regex"],
                              "Trap": self.config["OBJECT_INFO"]["Trap"]["regex"],
                              "Stone": self.config["OBJECT_INFO"]["Stone"]["regex"]}
        self.terminated = False
        # Game phase vars
        self.phases = self.config["PHASES"]
        self.phase_num = 0
        self.dice_rolls = self.config["DICE_ROLLS"]
        self.respawn_wait = 2
        # Rendering
        self.render_game = render
        self.render_verbose = render_verbose
        # Actions and Types
        self.valid_pin_types = self.config["ACTIONS"]["VALID_PIN_TYPES"]
        self.directions = self.config["ACTIONS"]["DIRECTIONS"]
        self.valid_pin_actions = self.config["ACTIONS"]["VALID_PIN_ACTIONS"]
        self.valid_move_actions = self.config["ACTIONS"]["VALID_MOVE_ACTIONS"]
        self.reverse_actions = self.config["ACTIONS"]["REVERSE_ACTIONS"]
        # Setup init values
        # Keeps track of the number of times an obj appears on the grid
        self.counts = Counter()
        self.object_pos = self.get_object_locations()
        self.players = self.get_init_player_info()

    ###################
    # INITIALIZE GAME #
    ###################

    def get_init_player_info(self):
        """
        Gets initial values for playable characters
        :return: Dict
        """
        # 2 * Sight_Range + 1
        # piv = player initial values
        piv = {}
        for player in ["1S", "2S", "3S"]:
            piv[player] = deepcopy(self.config["PLAYER_INIT_VALUES"][player])
            piv[player].update(self.get_player_init_values(self.object_pos[player]["x"],
                                                           self.object_pos[player]["y"]))
        return piv

    def get_player_init_values(self, pos_x, pos_y):
        common = deepcopy(self.config["PLAYER_INIT_VALUES"]["COMMON"])
        common["start_x"] = pos_x
        common["start_y"] = pos_y
        common["respawn_counter"] = None
        return common

    def get_levels(self):
        levels = deepcopy(self.config["LEVELS"])
        self.levels = {int(k): [[row[i:i + 2] for i in range(0, len(row), 2)] for row in v.strip().split("\n")]
                       for k, v in levels.items()}

    def next_level(self):
        """
        Moves the game to the next level or repeats the same level
        :return:
        """
        # If level should be repeated, decrement repeat counter
        if self.lvl_repeats[self.curr_level_num]:
            self.lvl_repeats[self.curr_level_num] -= 1
        else:
            # Otherwise, move on to next level
            self.curr_level_num += 1
            # If finished final level and set to restart, go back to first level
            if self.curr_level_num > len(self.levels):
                if self.restart_on_finish:
                    self.curr_level_num = 1
                else:
                    print("FINISHED ALL LEVELS!")
                    if self.render_game:
                        self.render()
                    self.terminated = True
                    return
        # Set current level
        self.curr_level = deepcopy(self.levels[self.curr_level_num])
        # Re-initialize values
        self.counts = Counter()
        self.object_pos = self.get_object_locations()
        self.players = self.get_init_player_info()
        self.phase_num = 0

    def reset_player_values(self, p):
        self.players[p]["action_plan"] = []
        self.players[p]["action_path_x"] = None
        self.players[p]["action_path_y"] = None
        self.players[p]["action_plan_step"] = 0
        self.players[p]["action_points"] = self.players[p]["max_points"]
        self.players[p]["action_plan_finalized"] = False
        self.players[p]["pin_x"] = None
        self.players[p]["pin_y"] = None
        self.players[p]["pin_path_x"] = None
        self.players[p]["pin_path_y"] = None
        self.players[p]["pin_type"] = None
        self.players[p]["pin_plan_finalized"] = False
        self.players[p]["pin_finalized"] = False

    ###########################
    # GET STATE & SEND ACTION #
    ###########################

    def get_state(self):
        """
        Constructs a state representation of the game environment.
        :return: Dict
        """
        state = {
            "gameData": {
                "gridWidth": len(self.curr_level[0]),
                "gridHeight": len(self.curr_level),
                "level": self.curr_level_num,
                "phase": self.phases[self.phase_num]
            },
            "scene": []
        }
        obj_info = deepcopy(self.config["OBJECT_INFO"])
        for i in range(len(self.curr_level)):
            for j in range(len(self.curr_level[0])):
                objs = self.curr_level[i][j].split("-")
                for obj in objs:
                    info = {}
                    # Get current info about players
                    if obj in self.players:
                        info.update({"name": self.players[obj]["name"],
                                     "type": self.players[obj]["type"],
                                     "x": i,
                                     "y": j,
                                     "action_points": self.players[obj]["action_points"],
                                     "max_points": self.players[obj]["max_points"],
                                     "health": self.players[obj]["health"],
                                     "sightRange": self.players[obj]["sight_range"],
                                     "status": self.players[obj]["status"],
                                     "respawn_counter": self.players[obj]["respawn_counter"],
                                     "goal_reached": self.players[obj]["goal_reached"],
                                     "pin_type": self.players[obj]["pin_type"].split("(")[0] if self.players[obj]["pin_type"] else None,
                                     "pin_path_x": self.players[obj]["pin_path_x"],
                                     "pin_path_y": self.players[obj]["pin_path_y"],
                                     "pin_plan_finalized": self.players[obj]["pin_plan_finalized"],
                                     "action_path_x": self.players[obj]["action_path_x"],
                                     "action_path_y": self.players[obj]["action_path_y"],
                                     "action_plan_finalized": self.players[obj]["action_plan_finalized"]
                                     })
                        state["scene"].append(info)

                    # Check if object is a pin
                    elif re.match("(P(A|B|C|D)\\(\\dS\\))", obj):
                        info.update({
                            "name": obj.split("(")[0],
                            "type": "pin",
                            "x": i,
                            "y": j
                        })
                        state["scene"].append(info)
                    else:
                        # Get info about other game objects
                        for obj_name in obj_info:
                            if re.match(obj_info[obj_name]["regex"], obj):
                                info.update(obj_info[obj_name])
                                break
                        # Specify whose goal it is
                        if info["type"] == "goal" and info["name"] != "tower":
                            info["name"] = self.players[obj[0]+"S"]["name"] + " Goal"
                        else:
                            info["name"] = obj.split("(")[0]
                        info["x"] = i
                        info["y"] = j
                        state["scene"].append(info)
        return state

    def execute_action(self, player, action):
        """
        Applies an action to the player given.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # If all players have died, reset level
        if all([self.players[p]["status"] == "dead" for p in self.players]):
            self.lvl_repeats[self.curr_level_num] += 1
            self.next_level()
            return

        if self.phases[self.phase_num] == "pin_planning":
            self.pin_planning(player, action)
        elif self.phases[self.phase_num] == "action_planning":
            self.action_planning(player, action)
        # Render grid
        if self.render_game:
            self.render()

    def check_player_status(self):
        """
        Checks whether players are dead or alive and respawn players if enough game cycles have passed
        :return: N/A
        """
        for p in self.players:
            if self.players[p]["status"] == "dead":
                # Check if they've waited enough game cycles
                if (self.players[p]["respawn_counter"] / len(self.phases)) != self.respawn_wait:
                    self.players[p]["respawn_counter"] += 1
                # Player has waited long enough
                else:
                    self.players[p]["status"] = "alive"
                    self.players[p]["respawn_counter"] = None
                    self.place(p, x=self.players[p]["start_x"], y=self.players[p]["start_y"])

    ##############################
    # PHASE PLANNING & EXECUTION #
    ##############################

    def pin_planning(self, player, action):
        """
        Executes logic for the pin planning phase.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # Player is dead, can not take actions at this time
        if self.players[player]["status"] == "dead":
            return
            # If player has not finalized pin selection, allow them to change pin or select no pin
        if not self.players[player]["pin_finalized"]:
            # Allow player to specify pin type
            if action in self.valid_pin_types:
                self.players[player]["pin_type"] = f"{action}({player})"
                self.players[player]["pin_path_x"] = int(self.object_pos[player]["x"])
                self.players[player]["pin_path_y"] = int(self.object_pos[player]["y"])

            elif action == "submit":
                # If player has not yet selected a pin type, specify "no-pin"
                if self.players[player]["pin_type"] is None:
                    self.players[player]["pin_type"] = "no-pin"
                    self.players[player]["pin_plan_finalized"] = True
                else:
                    self.players[player]["pin_path_x"] = self.object_pos[player]["x"]
                    self.players[player]["pin_path_y"] = self.object_pos[player]["y"]
                # Finalize pin selection
                self.players[player]["pin_finalized"] = True

            # No-op/invalid action
            else:
                return
        else:
            # If user specified no pin, there is nothing further they can do during this phase
            if self.players[player]["pin_type"] != "no-pin":
                curr_x = int(self.players[player]["pin_path_x"])
                curr_y = int(self.players[player]["pin_path_y"])
                valid_actions = [i[0]
                                 for i in [[d] + list(self.update_location_by_direction(d, curr_x, curr_y))
                                           for d in self.directions]
                                 if curr_x != i[1] or curr_y != i[2]]

                if action in valid_actions:
                    # If player has finalized plan or are out of action points, they cannot continue at this time
                    if self.players[player]["pin_plan_finalized"] or self.players[player]["action_points"] <= 0:
                        # No-op
                        return
                    else:
                        self.players[player]["pin_plan"].append(action)
                        self.update_plan_location(player, action, "pin_path")
                elif action == "submit":
                    # If player has finalized plan or are out of action points, they cannot continue at this time
                    if self.players[player]["pin_plan_finalized"] or self.players[player]["action_points"] <= 0:
                        # No-op
                        return
                    else:
                        self.players[player]["pin_plan_finalized"] = True
                        self.players[player]["action_points"] -= 1
                # No-op/invalid action
                else:
                    return
            else:
                # No-op/player cannot take an action at this time, must wait until next phase
                return

        self.check_phase()

    @staticmethod
    def create_pin_regex(x):
        return f"(-{x}\\(\\dS\\)|{x}\\(\\dS\\)-|{x}\\(\\dS\\)|-{x}|{x}-|{x})"

    def action_planning(self, player, action):
        """
        Executes logic for the action planning phase.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # Player is dead, can not take actions at this time
        if self.players[player]["status"] == "dead":
            return
        # Set init values of action plan
        if self.players[player]["action_path_x"] is None or self.players[player]["action_path_y"] is None:
            self.players[player]["action_path_x"] = int(self.object_pos[player]["x"])
            self.players[player]["action_path_y"] = int(self.object_pos[player]["y"])

        curr_x = int(self.players[player]["action_path_x"])
        curr_y = int(self.players[player]["action_path_y"])
        valid_moves = [i[0]
                       for i in [[d] + list(self.update_location_by_direction(d, curr_x, curr_y))
                                 for d in self.directions]
                       if curr_x != i[1] or curr_y != i[2]]
        valid_moves.extend(["wait"])

        if action in valid_moves:
            # If player has finalized plan or exhausted action points, they cannot move at this time
            if self.players[player]["action_plan_finalized"] or self.players[player]["action_points"] <= 0:
                # No-op
                return
            else:
                self.players[player]["action_plan"].append(action)
                self.update_plan_location(player, action, "action_path")
                self.players[player]["action_points"] -= 1
        elif action == "submit":
            self.players[player]["action_plan_finalized"] = True
        else:
            # No-op/invalid action
            return
        self.check_phase()

    def check_phase(self):
        """
        Checks whether conditions have been met to end the current phase and apply the actions of the current phase.
        :return: N/A
        """
        curr_phase = self.phases[self.phase_num]
        # Need to end pinning phase, place pins, and begin planning phase
        if curr_phase == "pin_planning" and all([self.players[p]["pin_plan_finalized"]
                                                 for p in self.players
                                                 if self.players[p]["status"] == "alive"]):
            for p in self.players:
                if self.players[p]["status"] == "alive":
                    # If player has not decided to pin, pin type will be 'no-pin'
                    if self.players[p]["pin_type"] != "no-pin":
                        # Place pin and store location of pin for player
                        self.place(self.players[p]["pin_type"],
                                   self.players[p]["pin_path_x"],
                                   self.players[p]["pin_path_y"])
                        self.players[p]["pin_x"] = int(self.players[p]["pin_path_x"])
                        self.players[p]["pin_y"] = int(self.players[p]["pin_path_y"])

                    # Reset values
                    self.players[p]["pin_plan"] = []
                    self.players[p]["pin_path_x"] = None
                    self.players[p]["pin_path_y"] = None
                    self.players[p]["pin_x"] = None
                    self.players[p]["pin_y"] = None
                    self.players[p]["pin_finalized"] = False
                    self.players[p]["pin_plan_finalized"] = False
            # Change to action planning phase
            self.update_phase()
        elif curr_phase == "action_planning" \
                and all([self.players[p]["action_plan_finalized"]
                         for p in self.players
                         if self.players[p]["status"] == "alive"]):
            # Change to execution phase
            self.update_phase()
            res = self.execute_plans()
            if res != "next_level":
                # Reset values
                for p in self.players:
                    # Remove pins from grid if player placed one
                    if self.players[p]["pin_type"] and self.players[p]["pin_type"] != "no-pin":

                        # pin_regex = self.create_pin_regex(self.players[p]['pin_type'])
                        # self.remove(pin_regex, x=self.players[p]["pin_x"], y=self.players[p]["pin_y"], as_regex=True)
                        self.remove(self.players[p]['pin_type'], x=self.players[p]["pin_x"], y=self.players[p]["pin_y"])
                    self.reset_player_values(p)
                self.update_phase()

    def update_phase(self):
        """
        Moves the game to the next phase.
        :return: N/A
        """
        self.phase_num = (self.phase_num + 1) % len(self.phases)
        # Check if players need respawning
        self.check_player_status()
        # Trigger enemy movement
        if self.phases[self.phase_num] == "enemy_execution":
            self.execute_enemy_plans()

    def execute_plans(self):
        """
        Executes plans for each player by iterating over team until no actions remain in their plans.
        :return: N/A
        """
        # Number of player moves is length of action plan minus 1 (ignoring final submit action)
        player_moves = {p: len(self.players[p]["action_plan"]) - 1
                        for p in self.players}
        max_moves = max(list(player_moves.values()))
        for i in range(max_moves):
            for p in self.players:
                # If player is alive and has another move in its action plan (need to include length of action
                # plan in condition because it could get truncated if it loses combat)
                if self.players[p]["status"] == "alive" and i < len(self.players[p]["action_plan"]):
                    # Get action to make and move
                    # action = self.players[p]["action_plan"][self.players[p]["action_plan_step"]]
                    action = self.players[p]["action_plan"][i]
                    self.move(p, action)
                    self.players[p]["action_plan_step"] += 1

                    # Check if player has reached goal
                    goal = p[0]+"G"
                    if not self.players[p]["goal_reached"] and self.at(p, goal):
                        # Indicate goal reached
                        self.players[p]["goal_reached"] = True
                        # Destroy goal
                        self.remove(goal)
                    # Check if player has reached tower
                    if self.at(p, self.tower) and all([self.players[i]["goal_reached"] for i in self.players]):
                        self.next_level()
                        return "next_level"
                    # Render result of moves
                    if self.render_game:
                        self.render()
            # CHECK IF PLAYER AND MONSTER/TRAP/STONE IN SAME AREA AFTER
            # EACH PASS OF EACH CHARACTER MOVES
            self.check_combat()
        return None

    def execute_enemy_plans(self):
        """
        Executes plans for enemy monsters by iterating over enemy team until no actions remain in their plans.
        :return: N/A
        """
        monsters = [i for i in self.object_pos if re.match(self.enemy_regexes["Monster"], i)]
        moves = self.config["OBJECT_INFO"]["Monster"]["moves"]
        max_moves = max(list(moves.values()))

        for i in range(1, max_moves + 1):
            if not monsters:
                break
            for m in monsters:
                # Monster can move on this turn
                if i <= moves[m[1]]:
                    self.move_monster(m)
            # Check to see if com at needs to be initiated
            self.check_combat()
            # Render result of moves
            if self.render_game:
                self.render()
            # Some monsters may have been defeated
            monsters = [i for i in self.object_pos if re.match(self.enemy_regexes["Monster"], i)]
        self.update_phase()

    def undo(self, p):
        """
        Implements an undo feature for the given player.
        :param p: The player to apply an undo action to
        :return: N/A
        """
        curr_phase = self.phases[self.phase_num]
        if curr_phase == "pin_planning":
            # During pin planning, action points are only consumed after clicking submit, at which point it would
            # be too late to undo actions
            # Can only undo if pin is finalized, the pin_plan is not finalized, and there's an action in the pin_plan
            if self.players[p]["pin_finalized"] \
                    and not self.players[p]["pin_plan_finalized"] \
                    and self.players[p]["pin_plan"]:
                last_action = self.players[p]["pin_plan"].pop()
                # Use the reverse of the last action selected to step the pin back to the previous position
                self.update_plan_location(p, self.reverse_actions[last_action], "pin_path")
        elif curr_phase == "action_planning":
            last_action = self.players[p]["action_plan"].pop()
            # Use the reverse of the last action selected to step the player back to the previous position
            self.update_plan_location(p, self.reverse_actions[last_action], "action_path")
            self.players[p]["action_points"] += 1
        else:
            # No-op/invalid action
            return

    ##########
    # COMBAT #
    ##########

    def check_combat(self, x=None, y=None):
        """
        Checks if players and enemies are co-located which would initiate combat
        :param x: The x position of the grid to check
        :param y: The y position of the grid to check
        :return: N/A
        """
        if x is None or y is None:
            # If multiple players end up on the same grid square, using a set will ensure spot is only checked once
            # for combat (
            player_loc = set([(self.object_pos[p]["x"], self.object_pos[p]["y"])
                              for p in self.players
                              if p in self.object_pos])
        else:
            player_loc = [(x, y)]

        for loc in player_loc:
            players = [p for p in list(self.players.keys()) if p in self.curr_level[loc[0]][loc[1]].split("-")]
            if not players:
                return

            for e, rgx in self.enemy_regexes.items():
                self.combat(players, rgx, e, loc[0], loc[1])

    def combat(self, players, enemy_regex, enemy_type, x, y):
        """
        Executes combat logic. Given the list of players at the x,y position, determine if any enemies are at
        that position and if so, initiate combat
        :param players: A list of players at the x,y position
        :param enemy_regex: A regex representing the enemy name
        :param enemy_type: The enemy type
        :param x: The x position of the grid where combat occurs
        :param y: The y position of the grid where combat occurs
        :return: N/A
        """
        enemies = []
        for obj in self.curr_level[x][y].split("-"):
            if re.match(enemy_regex, obj):
                enemies.append(obj)
        # enemies = re.findall(enemy_regex, self.curr_level[x][y])
        if not enemies:
            return
        else:
            player_rolls = sum([self.get_player_dice_roll(p, enemy_type) for p in players])
            # Split on left parenthesis incase there is one
            enemy_rolls = sum([self.get_enemy_dice_roll(e.split("(")[0]) for e in enemies])
            if player_rolls >= enemy_rolls:
                self.multi_remove(enemies)
                for p in players:
                    self.players[p]["combat_success"] = True
            else:
                for p in players:
                    if enemy_type == "Monster":
                        # Lose a heart
                        self.players[p]["health"] -= 1
                        # Go back a step (if player has moved)
                        prev_action_step = self.players[p]["action_plan_step"] - 1
                        # Only have character take a step back if it has moved
                        if prev_action_step > 0 and self.phases[self.phase_num] != "enemy_execution":
                            prev_action = self.players[p]["action_plan"][prev_action_step]
                            self.move(p, self.reverse_actions[prev_action])
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    elif enemy_type == "Trap":
                        # Lose a heart
                        self.players[p]["health"] -= 1
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    elif enemy_type == "Stone":
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    # If player dies, remove from board
                    if self.players[p]["health"] <= 0:
                        self.players[p]["health"] = 0
                        self.players[p]["status"] = "dead"
                        self.players[p]["respawn_counter"] = 0
                        self.remove(p)
                    self.players[p]["combat_success"] = False
                # Traps are destroyed
                if enemy_type == "Trap":
                    self.multi_remove(enemies)

    def get_player_dice_roll(self, p, e):
        if self.dice_rolls[p][e]["val"] > 0:
            roll = choice(range(self.dice_rolls[p][e]["val"]))
        else:
            roll = 0
        return roll + self.dice_rolls[p][e]["const"]

    def get_enemy_dice_roll(self, e):
        if self.dice_rolls[e]["val"] > 0:
            roll = choice(range(self.dice_rolls[e]["val"]))
        else:
            roll = 0
        return roll + self.dice_rolls[e]["const"]

    ##########################
    # POSITIONING & MOVEMENT #
    ##########################

    def move(self, player, action, x=None, y=None, old_pos=None):
        """
        Moves the given player according to the given action
        :param player: The player to move
        :param action: The cardinal action to take
        :param x: Specifies the x location of the player to move
        :param y: Specifies the y location of the player to move
        :param old_pos: Specifies the current x,y location of the player which becomes the previous location after the
        move
        :return: N/A
        """
        if action == "wait":
            # No-op
            return
        # x is None and y is None, need to get new position
        if x is None or y is None:
            x = self.object_pos[player]["x"]
            y = self.object_pos[player]["y"]
            old_pos = (x, y)

            x, y = self.update_location_by_direction(action, x, y)

        self.place(player, x, y, old_x=old_pos[0], old_y=old_pos[1])

    def place(self, obj, x, y, old_x=None, old_y=None, index=None):
        """
        Places the given object at the given x,y position
        :param obj: The object to place
        :param x: Specifies the x location to place on
        :param y: Specifies the y location to place on
        :param old_x: Specifies the current x location of the object which becomes the previous x location after the
        placement
        :param old_y: Specifies the current y location of the object which becomes the previous y location after the
        placement
        :param index: If provided, specifies that 'obj' should be placed on board with value of 'index' in parentheses
        (usually for identification purposes)
        :return:
        """
        # If 'index' parameter is provided, specifies that obj should be placed on board with value of
        # 'index' in parentheses (usually for identification purposes)
        if index:
            obj = f"{obj}({index})"

        # Redraw player on board
        if self.curr_level[x][y] == self.empty:
            self.curr_level[x][y] = f"{obj}"
        else:
            self.curr_level[x][y] += f"-{obj}"

        # Remove obj from old position if it was previously on the grid
        if old_x is not None and old_y is not None:
            self.remove(obj, old_x, old_y, delete=False)

        # Update location of object
        if obj not in self.object_pos:
            self.object_pos[obj] = {"x": x, "y": y}
        else:
            self.object_pos[obj]["x"] = x
            self.object_pos[obj]["y"] = y

    def check_valid_move(self, x, y, avoid=None, as_regex=False):
        """
        Checks whether the given x,y position is a valid position for movement/placement.
        :param x: Specifies the x location to move/place to
        :param y: Specifies the y location to move/place to
        :return: True/False
        """
        if avoid is None:
            avoid = []

        if 0 <= x < len(self.curr_level) and 0 <= y < len(self.curr_level[0]):
            objs = self.curr_level[x][y].split("-")
            for o in objs:
                # Cannot move where walls are
                if o == self.wall:
                    break
                # Check if new spot has objects to avoid
                elif as_regex:
                    if any([re.match(av, o) for av in avoid]):
                        break
                # Consider items in 'avoid' for exact match
                else:
                    if o in avoid:
                        break
            # Passed all the tests
            else:
                return True
        return False

    def update_location_by_direction(self, action, x, y):
        if action == "left" and self.check_valid_move(x, y - 1):
            y -= 1
        elif action == "right" and self.check_valid_move(x, y + 1):
            y += 1
        elif action == "up" and self.check_valid_move(x - 1, y):
            x -= 1
        elif action == "down" and self.check_valid_move(x + 1, y):
            x += 1
        return x, y

    def move_monster(self, m):
        """
        Implements logic for monster movement. Currently, this is random walk.
        :param m: The monster to move
        :return: N/A
        """
        x = self.object_pos[m]["x"]
        y = self.object_pos[m]["y"]
        old_pos = (x, y)

        options = [("left", x, y-1), ("right", x, y+1), ("up", x-1, y), ("down", x+1, y)]
        shuffle(options)
        while options:
            op = options.pop()
            if self.check_valid_move(op[1], op[2],
                                     avoid=[self.enemy_regexes["Stone"], self.enemy_regexes["Trap"]],
                                     as_regex=True):
                self.move(m, action=op[0], x=op[1], y=op[2], old_pos=old_pos)
                break

    def remove(self, obj, x=None, y=None, delete=True):
        """
        Removes the given object from the grid. The x,y position of the object can be optionally supplied
        :param obj: The object to remove
        :param x: The x position of the object to remove
        :param y: The y position of the object to remove
        :param delete: If False, does not delete object from object list
        :return: N/A
        """
        if x is None or y is None:
            x = self.object_pos[obj]["x"]
            y = self.object_pos[obj]["y"]

        # Remove object from position
        objs = self.curr_level[x][y].split('-')
        objs.remove(obj)
        self.curr_level[x][y] = '-'.join(objs)

        # If nothing on board spot, place empty character
        if self.curr_level[x][y] == "":
            self.curr_level[x][y] = self.empty
        # Delete object from object positions dict
        if obj in self.object_pos:
            del self.object_pos[obj]

    def multi_remove(self, objs):
        """
        Removes the given objects from the grid
        :param objs: A list of objects to remove
        :return: N/A
        """
        for o in objs:
            self.remove(o)

    def get_object_locations(self):
        """
        Gets the locations of objects on the grid
        :return: Dict
        """
        objs = {}
        for i in range(len(self.curr_level)):
            for j in range(len(self.curr_level[0])):
                obj = self.curr_level[i][j]
                if obj not in [self.wall, self.empty]:
                    self.counts[obj] += 1
                    if self.counts[obj] > 1:
                        obj_id = f"{obj}({self.counts[obj]})"
                    else:
                        obj_id = obj
                    objs[obj_id] = {"x": i, "y": j}
                    # Set what's in grid to obj_id
                    self.curr_level[i][j] = obj_id
        return objs

    def update_plan_location(self, player, action, plan):
        """
        Given a player and an action, update the location of the player's pin or action plan
        :param player: The player to adjust the pin location for
        :param action: The action that determines the new x,y position of the pin
        :param plan: The plan to update. One of {pin, action}
        """
        x = int(self.players[player][f"{plan}_x"])
        y = int(self.players[player][f"{plan}_y"])

        x, y = self.update_location_by_direction(action, x, y)

        self.players[player][f"{plan}_x"] = x
        self.players[player][f"{plan}_y"] = y

    ################
    # GOAL TESTING #
    ################

    def at(self, player, obj):
        """
        Checks whether the given player and object are co-located
        :param player: The player to check
        :param obj: The object to check
        :return: True/False
        """
        return self.object_pos[player]["x"] == self.object_pos[obj]["x"] \
            and self.object_pos[player]["y"] == self.object_pos[obj]["y"]

    #############
    # RENDERING #
    #############

    def render(self):
        """
        Renders the game in the console as an ascii grid
        :return: N/A
        """
        if self.render_verbose:
            info = [
                ["Level:", self.curr_level_num],
                ["Phase:", self.phases[self.phase_num]],
            ]
            print("Game Info:")
            print(tabulate(info, tablefmt="grid"))
        print("Grid:")
        print(tabulate(self.curr_level, tablefmt="grid"), end="\n\n")

