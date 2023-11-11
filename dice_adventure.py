from json import loads
import re
from random import shuffle
from tabulate import tabulate


# TODO IMPLEMENT MONSTER EXECUTION. NEED TO DEFINE ACTION POINTS FOR EACH MONSTER
class DiceAdventure:
    def __init__(self, level=1, render=False, num_repeats=0):
        # Level vars
        self.levels = {}
        self.get_levels()
        self.curr_level = self.levels[level]
        self.curr_level_num = level
        self.num_repeats = num_repeats
        self.lvl_repeats = {lvl: self.num_repeats for lvl in self.levels}
        self.empty = ".."
        self.tower = "**"
        self.wall = "##"
        # Game phase vars
        self.phases = ["pin_planning", "action_planning", "execute_plan", "enemy_execution"]
        self.phase_num = 0
        self.dice_nums = loads(open("dice_adventure/dice_roll_config.json", "r").read())
        self.respawn_wait = 2
        # Rendering
        self.render_game = render
        # Actions and Types
        self.valid_pin_types = ["PA", "PB", "PC", "PD"]
        self.valid_pin_actions = ["left", "right", "up", "down", "submit"]
        self.valid_move_actions = ["left", "right", "up", "down", "wait", "submit"]
        self.reverse_actions = {"left": "right", "right": "left", "up": "down", "down": "up", "wait": "wait"}
        # Setup init values
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
        piv = {
            "1S": {"name": "Human", "type": "human", "action_points": 6, "max_points": 6, "health": 3, "sight_range": 3},
            "2S": {"name": "Dwarf", "type": "dwarf", "action_points": 6, "max_points": 6, "health": 3, "sight_range": 3},
            "3S": {"name": "Giant", "type": "giant", "action_points": 6, "max_points": 6, "health": 3, "sight_range": 3}
        }
        piv["1S"].update(get_player_init_values(self.object_pos["1S"]["x"],
                                                self.object_pos["1S"]["y"],
                                                self.respawn_wait))
        piv["2S"].update(get_player_init_values(self.object_pos["2S"]["x"],
                                                self.object_pos["2S"]["y"],
                                                self.respawn_wait))
        piv["3S"].update(get_player_init_values(self.object_pos["3S"]["x"],
                                                self.object_pos["3S"]["y"],
                                                self.respawn_wait))
        return piv

    def get_static_object_info(self):
        """
        Gets common values for game objects.
        :return:
        """
        return {
            r"\dG": {"name": "", "type": "goal"},
            r"\dM": {"name": "Monster", "type": "monster"},
            r"\dT": {"name": "Trap", "type": "trap"},
            r"S\d": {"name": "Stone", "type": "stone"},
            self.wall: {"name": "Wall", "type": "wall"},
            self.empty: {"name": "Empty Space", "type": "empty_space"},
            self.tower: {"name": "Tower", "type": "goal"}
        }

    def get_levels(self):
        level_config = loads(open("dice_adventure/level_config.json", "r").read())
        self.levels = {int(k): [[row[i:i + 2] for i in range(0, len(row), 2)] for row in v.strip().split("\n")]
                       for k, v in level_config.items()}

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
        # Set current level
        self.curr_level = self.levels[self.curr_level_num]
        # Re-initialize values
        self.object_pos = self.get_object_locations()
        self.players = self.get_init_player_info()
        self.phase_num = 0

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
        obj_info = self.get_static_object_info()
        for i in range(len(self.curr_level)):
            for j in range(len(self.curr_level[0])):
                info = {}
                obj = self.curr_level[i][j]
                # Get current info about players
                if obj in self.players:
                    info.update({"name": self.players[obj]["name"],
                                 "type": self.players[obj]["type"],
                                 "action_points": self.players[obj]["action_points"],
                                 "max_points": self.players[obj]["max_points"],
                                 "health": self.players[obj]["health"],
                                 "sightRange": self.players[obj]["sight_range"],
                                 "status": self.players[obj]["status"],
                                 "respawn_counter": self.players[obj]["respawn_counter"],
                                 "goal_reached": self.players[obj]["goal_reached"],
                                 "pin_path_x": self.players[obj]["pin_path_x"],
                                 "pin_path_y": self.players[obj]["pin_path_y"],
                                 "action_path_x": self.players[obj]["action_path_x"],
                                 "action_path_y": self.players[obj]["action_path_y"]
                                 })
                    state["scene"].append(info)
                    # If player has a pin on the board, display it
                    if self.players[obj]["pin_type"] != "no-pin" and self.players[obj]["pin_type"] is not None:
                        state["scene"].append({
                            "name": self.players[obj]["pin_type"],
                            "type": "pin",
                            "x": self.players[obj]["pin_x"],
                            "y": self.players[obj]["pin_y"]
                        })
                    continue
                # Get info about other game objects
                for obj_regex in obj_info:
                    if re.match(obj_regex, obj):
                        info.update(obj_info[obj_regex])
                        break
                # Specify whose goal it is
                if info["type"] == "goal" and info["name"] != "tower":
                    info["name"] = self.players[obj[0]+"S"]["name"] + " Goal"
                info["x"] = i
                info["y"] = j
                state["scene"].append(info)
        return state

    def send_action(self, player, action):
        """
        Applies an action to the player given.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # If character is dead, need to wait 2 turns before respawning
        self.check_player_status(player)

        if self.phases[self.phase_num] == "pin_planning":
            self.pin_planning(player, action)
        elif self.phases[self.phase_num] == "action_planning":
            self.action_planning(player, action)
        # Render grid
        if self.render_game:
            self.render()

    def check_player_status(self, p):
        """
        Checks whether the player is dead or alive and respawns the player if enough turns have passed.
        :param p: The player to check
        :return: N/A
        """
        if self.players[p]["status"] == "dead":
            if self.players[p]["respawn_counter"] > 0:
                self.players[p]["respawn_counter"] -= 1
                return
            else:
                self.players[p]["status"] = "alive"
                self.players[p]["respawn_counter"] = self.respawn_wait
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
        if self.players[player]["pin_type"] is None:
            if action in self.valid_pin_types:
                self.players[player]["pin_type"] = action
                self.players[player]["pin_path_x"] = int(self.object_pos[player]["x"])
                self.players[player]["pin_path_y"] = int(self.object_pos[player]["y"])
            elif action == "submit":
                self.players[player]["pin_type"] = "no-pin"
                self.players[player]["pin_plan"].append(action)
            # No-op/invalid action
            else:
                return

        elif action in self.valid_pin_actions:
            # If player has clicked submit or are out of action points, they cannot continue at this time
            if (self.players[player]["pin_plan"] and self.players[player]["pin_plan"][-1] == "submit") \
                    or self.players[player]["action_points"] <= 0:
                # No-op
                return
            else:
                self.players[player]["pin_plan"].append(action)
                self.update_plan_location(player, action, "pin_path")
                if action == "submit":
                    self.players[player]["action_points"] -= 1
        # No-op/invalid action
        else:
            return

        self.check_phase()

    def action_planning(self, player, action):
        """
        Executes logic for the action planning phase.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        if action in self.valid_move_actions:
            if (self.players[player]["action_plan"] and self.players[player]["action_plan"][-1] == "submit") \
                    or self.players[player]["action_points"] <= 0:
                # No-op
                return
            else:
                self.players[player]["action_plan"].append(action)
                self.update_plan_location(player, action, "action_path")
                self.players[player]["action_points"] -= 1
        else:
            # No-op
            return
        self.check_phase()

    def check_phase(self):
        """
        Checks whether conditions have been met to end the current phase and apply the actions of the current phase.
        :return: N/A
        """
        curr_phase = self.phases[self.phase_num]
        # Need to end pinning phase, place pins, and begin planning phase
        if curr_phase == "pin_planning" and all(["submit" in self.players[p]["pin_plan"] for p in self.players]):
            for p in self.players:
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
            # Change to action planning phase
            self.update_phase()
        elif curr_phase == "action_planning" \
                and all(["submit" in self.players[p]["action_plan"] for p in self.players]):
            # Change to execution phase
            self.update_phase()
            res = self.execute_plans()
            if res != "next_level":
                # Reset values
                for p in self.players:
                    # Remove pins from grid if player placed one
                    if self.players[p]["pin_type"] != "no-pin":
                        self.remove(self.players[p]["pin_type"], x=self.players[p]["pin_x"], y=self.players[p]["pin_y"])
                    self.players[p]["action_plan"] = []
                    self.players[p]["action_path_x"] = None
                    self.players[p]["action_path_y"] = None
                    self.players[p]["action_plan_step"] = 0
                    self.players[p]["action_points"] = self.players[p]["max_points"]
                    self.players[p]["pin_x"] = None
                    self.players[p]["pin_y"] = None
                    self.players[p]["pin_path_x"] = None
                    self.players[p]["pin_path_y"] = None
                    self.players[p]["pin_type"] = None
                self.update_phase()


    def update_phase(self):
        """
        Moves the game to the next phase.
        :return: N/A
        """
        self.phase_num = (self.phase_num + 1) % len(self.phases)

    def execute_plans(self):
        """
        Executes plans for each player by iterating over team until no actions remain in their plans.
        :return: N/A
        """
        while True:
            found = False
            for p in self.players:
                # Remove 'submit' action from plan
                if "submit" in self.players[p]["action_plan"]:
                    self.players[p]["action_plan"].remove("submit")
                # If player is alive and has a move in its action plan
                if self.players[p]["action_plan"] and self.players[p]["status"] == "alive":
                    found = True
                    # Get action to make and move
                    action = self.players[p]["action_plan"].pop(0)
                    self.move(p, action)

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
            # No moves were taken for any characters
            if not found:
                break
            # CHECK IF PLAYER AND MONSTER/TRAP/STONE IN SAME AREA AFTER
            # EACH PASS OF EACH CHARACTER MOVES
            self.check_combat()
        return None

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
            # for combat
            player_locs = set([(self.object_pos[p]["x"], self.object_pos[p]["y"])
                               for p in self.players])
        else:
            player_locs = [(x, y)]

        for loc in player_locs:
            players = re.findall(r"\dS", self.curr_level[loc[0]][loc[1]])
            if not players:
                return

            enemy_regexes = [(r"M\d", "monster"), (r"T\d", "trap"), (r"S\d", "stone")]
            for er in enemy_regexes:
                self.combat(players, er[0], er[1], loc[0], loc[1])

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
        enemies = re.findall(enemy_regex, self.curr_level[x][y])
        if not enemies:
            return
        else:
            player_rolls = sum([self.get_die_roll(p, enemy_type=enemy_type) for p in players])
            enemy_rolls = sum([self.get_die_roll(e) for e in enemies])
            if player_rolls >= enemy_rolls:
                self.multi_remove(enemies)
            else:
                for p in players:
                    if enemy_type == "monster":
                        # Lose a heart
                        self.players[p]["health"] -= 1
                        # Go back a step
                        prev_action_step = self.players[p]["action_plan_step"] - 1
                        prev_action = self.players[p]["action_plan"][prev_action_step]
                        self.move(p, self.reverse_actions[prev_action])
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    elif enemy_type == "trap":
                        # Lose a heart
                        self.players[p]["health"] -= 1
                        # Traps are destroyed
                        self.multi_remove(enemies)
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    elif enemy_type == "stone":
                        # Truncate action plan
                        self.players[p]["action_plan"] = []
                        self.players[p]["action_plan_step"] = 0
                    # If player dies, remove from board
                    if self.players[p]["health"] <= 0:
                        self.players[p]["status"] = "dead"
                        self.remove(p)

    def get_die_roll(self, char, enemy_type=None):
        if enemy_type:
            val = choice(range(self.dice_nums[char][enemy_type]["val"])) + self.dice_nums[char][enemy_type]["const"]
        else:
            val = choice(range(self.dice_nums[char]["val"])) + self.dice_nums[char]["const"]
        return val

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

            if action == "left" and self.check_valid_move(x, y-1):
                y -= 1
            elif action == "right" and self.check_valid_move(x, y+1):
                y += 1
            elif action == "up" and self.check_valid_move(x-1, y):
                x -= 1
            elif action == "down" and self.check_valid_move(x+1, y):
                x += 1

        self.place(player, x, y, old_x=old_pos[0], old_y=old_pos[1])
        self.players[player]["action_plan_step"] += 1

    def place(self, obj, x, y, old_x=None, old_y=None):
        """
        Places the given object at the given x,y position
        :param obj: The object to place
        :param x: Specifies the x location to place on
        :param y: Specifies the y location to place on
        :param old_x: Specifies the current x location of the object which becomes the previous x location after the
        placement
        :param old_y: Specifies the current y location of the object which becomes the previous y location after the
        placement
        :return:
        """
        # Redraw player on board
        if self.curr_level[x][y] == self.empty:
            self.curr_level[x][y] = f"{obj}"
        else:
            self.curr_level[x][y] += f"-{obj}"

        # Remove obj from old position if it was previously on the grid
        if old_x is not None and old_y is not None:
            # Remove character from old position
            self.curr_level[old_x][old_y] = re.sub(f"(-{obj}|{obj})",
                                                   "",
                                                   self.curr_level[old_x][old_y])
            # If nothing on board spot, place empty character
            if self.curr_level[old_x][old_y] == "":
                self.curr_level[old_x][old_y] = self.empty

        # Do not save Pings in dictionary (see notes)
        # Pin locations are saved in player objects (due to multiple pins of same type [and therefore dict key values]
        # being able to be placed on the grid)
        if obj[0] != "P":
            # Update location of object
            self.object_pos[obj]["x"] = x
            self.object_pos[obj]["y"] = y

    def check_valid_move(self, x, y):
        """
        Checks whether the given x,y position is a valid position for movement/placement.
        :param x: Specifies the x location to move/place to
        :param y: Specifies the y location to move/place to
        :return: True/False
        """
        if 0 <= x < len(self.curr_level) and 0 <= y < len(self.curr_level[0]):
            if self.curr_level[x][y] != self.wall:
                return True
        return False

    def execute_enemy_plans(self):
        """
        Executes plans for enemy monsters by iterating over enemy team until no actions remain in their plans.
        :return: N/A
        """
        while True:
            found = False
            for p in self.players:
                # Remove 'submit' action from plan
                if "submit" in self.players[p]["action_plan"]:
                    self.players[p]["action_plan"].remove("submit")
                # If player is alive and has a move in its action plan
                if self.players[p]["action_plan"] and self.players[p]["status"] == "alive":
                    found = True
                    # Get action to make and move
                    action = self.players[p]["action_plan"].pop(0)
                    self.move(p, action)

                    # Check if player has reached goal
                    goal = p[0] + "G"
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
            # No moves were taken for any characters
            if not found:
                break
            # CHECK IF PLAYER AND MONSTER/TRAP/STONE IN SAME AREA AFTER
            # EACH PASS OF EACH CHARACTER MOVES
            self.check_combat()
        return None

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
            if self.check_valid_move(op[1], op[2]):
                self.move(m, action=op[0], x=op[1], y=op[2], old_pos=old_pos)
                break

    def remove(self, obj, x=None, y=None):
        """
        Removes the given object from the grid. The x,y position of the object can be optionally supplied
        :param obj: The object to remove
        :param x: The x position of the object to remove
        :param y: The y position of the object to remove
        :return: N/A
        """
        if x is None or y is None:
            x = self.object_pos[obj]["x"]
            y = self.object_pos[obj]["y"]

        # Remove object from position
        self.curr_level[x][y] = re.sub(f"(-{obj}|{obj}-|{obj})",
                                       "",
                                       self.curr_level[x][y])
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
                    objs[obj] = {"x": i, "y": j}
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
        if action == "left" and self.check_valid_move(x, y-1):
            y -= 1
        elif action == "right" and self.check_valid_move(x, y+1):
            y += 1
        elif action == "up" and self.check_valid_move(x-1, y):
            x -= 1
        elif action == "down" and self.check_valid_move(x+1, y):
            x += 1

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
        print(tabulate(self.curr_level, tablefmt="grid"))
        """
        max_num_chars = max([self.curr_level[i][j]
                             for i in self.curr_level
                             for j in self.curr_level[i]])
        if max_num_chars > 2:
            num_chars_per_line = int(np.sqrt(max_num_chars))
        else:
            num_chars_per_line = max_num_chars
        """

def get_player_init_values(pos_x, pos_y, respawn_wait_time):
    return {
        "status": "alive", "start_x": pos_x, "start_y": pos_y, "respawn_counter": respawn_wait_time,
        "goal_reached": False,
        "action_plan": [], "action_plan_step": 0, "action_path_x": pos_x, "action_path_y": pos_y,
        "pin_plan": [], "pin_type": None, "pin_x": None, "pin_y": None, "pin_path_x": None, "pin_path_y": None
    }