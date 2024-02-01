from copy import deepcopy
from datetime import datetime
from json import loads
from os import makedirs
from os import path
from random import choice
from random import shuffle
import re
from environment.classes.board import Board
from environment.classes.objects import *


class DiceAdventure:
    def __init__(self, level=1, limit_levels=None, render=False, render_verbose=False, num_repeats=0,
                 restart_on_finish=False, round_cap=0, level_sampling=False,
                 track_metrics=True, metrics_dir=None, metrics_save_threshold=10000):
        # Game config
        self.config = loads(open("environment/config.json", "r").read())
        # Level vars
        self.levels = {}
        self.limit_levels = limit_levels if limit_levels else [int(i) for i in list(self.config["LEVELS"].keys())]
        self.get_levels()
        self.curr_level_num = level if level in self.limit_levels else self.limit_levels[0]
        self.curr_level = deepcopy(self.levels[self.curr_level_num])
        self.num_repeats = num_repeats
        self.restart_on_finish = restart_on_finish
        self.lvl_repeats = {lvl: self.num_repeats for lvl in self.levels}
        self.empty = self.config["OBJECT_INFO"]["Empty Space"]["regex"]
        self.tower = self.config["OBJECT_INFO"]["Tower"]["regex"]
        self.wall = self.config["OBJECT_INFO"]["Wall"]["regex"]
        self.terminated = False
        self.restart_on_team_loss = False
        # Places a cap on the number of rounds per level
        self.round_cap = round_cap
        # Determines whether levels should be randomly sampled
        self.level_sampling = level_sampling

        # Character/Object vars
        self.player_regex = r"\dS"
        self.enemy_regexes = {"Monster": self.config["OBJECT_INFO"]["Monster"]["regex"],
                              "Trap": self.config["OBJECT_INFO"]["Trap"]["regex"],
                              "Stone": self.config["OBJECT_INFO"]["Stone"]["regex"]}

        ##########
        # BOARD #
        #########
        self.board = Board(width=len(self.curr_level),
                           height=len(self.curr_level[0]),
                           object_positions=self.curr_level,
                           config=self.config)
        self.board.print_board()
        exit(0)

        ################
        # PLAYERS VARS #
        ################
        self.player_codes = [""]

        ##############
        # PHASE VARS #
        ##############
        self.phase_num = 0
        self.phases = self.config["PHASES"]
        # Pin Planning
        self.valid_pin_actions = self.config["ACTIONS"]["VALID_PIN_ACTIONS"]
        self.valid_pin_types = self.config["ACTIONS"]["VALID_PIN_TYPES"]
        self.pin_code_mapping = self.config["OBJECT_INFO"]["Pin"]["code_mapping"]
        # Action Planning
        self.valid_move_actions = self.config["ACTIONS"]["VALID_MOVE_ACTIONS"]

        self.dice_rolls = self.config["DICE_ROLLS"]
        self.respawn_wait = 2
        # Rendering
        self.render_game = render
        self.render_verbose = render_verbose

        # Actions and Types
        self.directions = self.config["ACTIONS"]["DIRECTIONS"]

        self.reverse_actions = self.config["ACTIONS"]["REVERSE_ACTIONS"]
        # Setup init values
        # Metrics
        self.track_metrics = track_metrics
        self.metrics = self.get_metrics_dict()
        self.num_rounds = 0
        self.metrics_dir = metrics_dir if metrics_dir is not None else "monitoring"
        makedirs(self.metrics_dir, exist_ok=True)
        # Number of calls to execute_action() or get_state() functions
        self.num_calls = 0
        # After this number of calls to the game, save metrics in log files
        self.metrics_save_threshold = metrics_save_threshold
        # {1: {"Human": {"health_lost": ['2023-11-20 09:43:54', ]

        ###################
        # INITIALIZE GAME #
        ###################
        self.pin_planning_init()

    def get_levels(self):
        levels = deepcopy(self.config["LEVELS"])
        self.levels = {int(k): [[row[i:i + 2] for i in range(0, len(row), 2)] for row in v.strip().split("\n")]
                       for k, v in levels.items()
                       if int(k) in self.limit_levels}

    def next_level(self):
        """
        Moves the game to the next level or repeats the same level
        :return:
        """
        # Track number of rounds
        if self.track_metrics:
            self._track_game_metrics(metric_name="rounds", metric=self.num_rounds)

        if self.restart_on_team_loss:
            pass
        # If level sampling turned on, randomly sample for next level
        if self.level_sampling:
            self.curr_level_num = choice(list(self.levels))

        # If level should be repeated, decrement repeat counter
        elif self.lvl_repeats[self.curr_level_num]:
            self.lvl_repeats[self.curr_level_num] -= 1
            print(F"REPEATING LEVEL: {self.curr_level_num} | NUM REPEATS LEFT: {self.lvl_repeats[self.curr_level_num]}")
        else:
            # Otherwise, move on to next level
            self.curr_level_num += 1
            # If finished final level and set to restart, go back to first level
            if self.curr_level_num > len(self.levels):
                if self.restart_on_finish:
                    # print(f"RESTARTING TO FIRST LEVEL!")
                    self.curr_level_num = self.limit_levels[0]
                else:
                    # print("FINISHED ALL LEVELS!")
                    if self.render_game:
                        self.render()
                    self.terminated = True
                    if self.track_metrics:
                        self._save_metrics()
                    raise TerminationException()

        # Set current level
        self.curr_level = deepcopy(self.levels[self.curr_level_num])
        # Re-initialize values
        self.counts = Counter()
        self.object_pos = self.get_object_locations()
        self.players = self.get_init_player_info()
        self.phase_num = 0
        self.num_rounds = 0

    ###########################
    # GET STATE & SEND ACTION #
    ###########################

    def get_state(self):
        """
        Constructs a state representation of the game environment.
        :return: Dict
        """
        self.num_calls += 1
        state = {
            "command": "get_state",
            "status": "OK",
            "message": "Full State",
            "content": {
                "gameData": {
                    "boardWidth": len(self.curr_level[0]),
                    "boardHeight": len(self.curr_level),
                    "level": self.curr_level_num,
                    "num_repeats": self.num_repeats - self.lvl_repeats[self.curr_level_num],
                    "currentPhase": self.phases[self.phase_num],
                    # "game_over": self.terminated,
                    "restart_on_team_loss": self.restart_on_team_loss
                },
                "scene": []
            }
        }
        # Used to track when level restart is due to all characters dying
        if self.restart_on_team_loss:
            self.restart_on_team_loss = False

        for p in self.players:
            x = y = None
            if p in self.object_pos:
                x = self.object_pos[p]["x"]
                y = self.object_pos[p]["y"]
            # In this case, player is not on board (dead) so just use start position
            if x is None or y is None:
                x = self.players[p]["start_x"]
                y = self.players[p]["start_y"]

            state["content"]["scene"].append(
                {"name": self.players[p]["name"],
                 "characterId": int(p[0]),
                 "type": self.players[p]["type"],
                 "x": x,
                 "y": y,
                 "pinCursorX": self.players[p]["pin_path_x"],
                 "pinCursorY": self.players[p]["pin_path_y"],
                 "sightRange": self.players[p]["sight_range"],
                 "monsterDice": f"D{self.dice_rolls[p]['Monster']['val']}+{self.dice_rolls[p]['Monster']['const']}",
                 "trapDice": f"D{self.dice_rolls[p]['Trap']['val']}+{self.dice_rolls[p]['Trap']['const']}",
                 "stoneDice": f"D{self.dice_rolls[p]['Stone']['val']}+{self.dice_rolls[p]['Stone']['const']}",
                 "health": self.players[p]["health"],
                 "dead": self.players[p]["status"] == "dead",
                 "actionPoints": self.players[p]["action_points"],
                 "actionPlan": self.players[p]["action_plan"]
                 }
            )
            # Add goal information
            shrine = {
                "type": "shrine",
                "reached": self.players[p]["goal_reached"],
                "character": self.players[p]["name"]
            }
            shrine_name = p[0] + "G"
            if shrine_name in self.object_pos:
                shrine["x"] = self.object_pos[shrine_name]["x"]
                shrine["y"] = self.object_pos[shrine_name]["y"]
            else:
                shrine["x"] = None
                shrine["y"] = None
            state["content"]["scene"].append(shrine)

        size_mapping = {"1": "S", "2": "M", "3": "L", "4": "XL"}
        obj_info = deepcopy(self.config["OBJECT_INFO"])
        for i in range(len(self.curr_level)):
            for j in range(len(self.curr_level[0])):
                objs = self.curr_level[i][j].split("-")
                for obj in objs:
                    info = {}
                    # Get current info about players
                    if obj not in self.players and obj != self.empty:

                        # Check if object is a pin
                        # if re.match("(P(A|B|C|D)\\(\\dS\\))", obj):
                        if obj[0] == "P":
                            info.update({
                                "name": obj.split("(")[0],
                                "type": "pin",
                                "x": i,  # j
                                "y": j  # i
                            })
                            state["content"]["scene"].append(info)
                        else:
                            # Get info about other game objects
                            for obj_name in obj_info:
                                if re.match(obj_info[obj_name]["regex"], obj):
                                    if obj[0] == "M":
                                        info["type"] = size_mapping[obj[1]] + "_" + obj_info[obj_name].get("type")
                                    else:
                                        info["type"] = obj_info[obj_name].get("type")
                                    break

                            info["name"] = obj.split("(")[0]
                            info["x"] = i  # j
                            info["y"] = j  # i
                            state["content"]["scene"].append(info)
        return state

    def execute_action(self, player, action):
        """
        Applies an action to the player given.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        self.num_calls += 1
        # Check if need to save metrics
        if self.track_metrics:
            if self.num_calls % self.metrics_save_threshold == 0:
                self._save_metrics()

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
        dead = [p for p in self.config["PLAYER_CODES"] if not self.board.objects[p].alive]
        # If all players have died, reset level
        if len(dead) == 3:
            if self.track_metrics:
                self.metrics[f"Level{self.curr_level_num}"]["team_deaths"].append([self._timestamp()])
            self.restart_on_team_loss = True
            self.next_level()
            return
        # Otherwise, check if players need respawning
        else:
            for p in dead:
                # Check if they've waited enough game cycles
                if self.num_rounds - self.board.objects[p].death_round >= self.respawn_wait:
                    # Player has waited long enough
                    self.board.objects[p].alive = True
                    self.board.objects[p].death_round = None
                    self.place(p, x=self.board.objects[p].start_x, y=self.board.objects[p].start_y)

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
        # Player supplied invalid action
        # Player has already finalized pin planning
        # Player out of action points
        if not self.board.objects[player].alive or \
                action not in self.valid_pin_actions + self.valid_pin_types or \
                self.board.objects[player].pin_finalized:
            # No-op/invalid action
            return

        if action == "submit":
            self.board.objects[player].pin_finalized = True

            # Track pinning metrics
            # if self.track_metrics and self.players[player]["pin_type"] != "no-pin":
            #    self._track_player_metrics(self.players[player]["name"], metric_name="pins",
            #                               pin_type=self.players[player]["pin_type"].split("(")[0])
        # Can only take action if player has enough action points
        if self.board.objects[player].action_points > 0:
            # elif self.players[player]["pin_type"] is None:
            if action in self.directions:
                x, y = self.update_location_by_direction(action,
                                                         self.board.objects[player].pin_x,
                                                         self.board.objects[player].pin_y)
                self.board.objects[player].pin_x = x
                self.board.objects[player].pin_y = y

            elif action in self.valid_pin_types:
                # Place new pin
                self.place(self.pin_code_mapping[action],
                           self.board.objects[player].pin_x,
                           self.board.objects[player].pin_y)
                self.board.objects[player].action_points -= 1
                # Reset pin_x and pin_y location to player position
                self.board.objects[player].pin_x = self.board.objects[player].x
                self.board.objects[player].pin_y = self.board.objects[player].y

        self.check_phase()

    def action_planning(self, player, action):
        """
        Executes logic for the action planning phase.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # Player is dead, can not take actions at this time
        if not self.board.objects[player].alive \
                or action not in self.valid_move_actions \
                or self.board.objects[player].action_plan_finalized:
            # No-op/invalid action
            return

        # Set init values of action plan
        if not self.board.objects[player].action_plan:
            self.board.objects[player].action_path_x = self.board.objects[player].x
            self.board.objects[player].action_path_y = self.board.objects[player].y

        if action == "submit":
            self.board.objects[player].action_plan_finalized = True
            # Pad rest of action plan with 'wait' actions
            self.board.objects[player].action_plan += \
                ["wait"] * (self.config["ACTIONS"]["MAX_MOVES"] - len(self.board.objects[player].action_plan))
            # Pad rest of action plan positions with current position of player
            self.board.objects[player].action_positions += \
                [(self.board.objects[player].action_path_x, self.board.objects[player].action_path_y)] * \
                (self.config["ACTIONS"]["MAX_MOVES"] - len(self.board.objects[player].action_plan))
        else:
            # Check for 'undo' action
            if action == "undo":
                self.undo(player)

            elif self.board.objects[player].action_points > 0:
                curr_x = self.board.objects[player].action_path_x
                curr_y = self.board.objects[player].action_path_y
                # Test whether action supplied by agent was a valid move
                if not self.board.valid_move(curr_x, curr_y, action):
                    # No-op/invalid action
                    return
                else:
                    # get new cursor location
                    new_x, new_y = self.board.update_location_by_direction(action, curr_x, curr_y)
                    # Update player fields
                    self.board.objects[player].action_plan.append(action)
                    self.board.objects[player].action_positions.append((new_x, new_y))
                    self.board.objects[player].action_path_x = new_x
                    self.board.objects[player].action_path_y = new_y
                    self.board.objects[player].action_points -= 1

        self.check_phase()

    def check_phase(self):
        """
        Checks whether conditions have been met to end the current phase and apply the actions of the current phase.
        :return: N/A
        """
        curr_phase = self.phases[self.phase_num]

        # Need to end pinning phase, place pins, and begin planning phase
        if curr_phase == "pin_planning" and all([self.board.objects[p].pin_finalized
                                                 for p in self.config["PLAYER_CODES"]
                                                 if self.board.objects[p].alive]):
            for p in self.config["PLAYER_CODES"]:
                # Reset values
                self.board.objects[p].pin_x = None
                self.board.objects[p].pin_y = None
                self.board.objects[p].pin_finalized = False
            # Change to action planning phase
            self.update_phase()
        elif curr_phase == "action_planning" \
                and all([self.board.objects[p].action_plan_finalized
                         for p in self.config["PLAYER_CODES"]
                         if self.board.objects[p].alive]):
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
            self.num_rounds += 1
            # If a cap has been placed on the number of rounds per level and that cap has been exceeded,
            # move on to next level
            if self.round_cap and self.num_rounds > self.round_cap:
                self.next_level()

    def execute_plans(self):
        """
        Executes plans for each player by iterating over team until no actions remain in their plans.
        :return: N/A
        """
        for i in range(self.config["ACTIONS"]["MAX_MOVES"]):
            for p in self.config["PLAYER_CODES"]:
                # If player is alive, can move
                if self.board.objects[p].alive:
                    # Get action to make and move
                    # action = self.players[p]["action_plan"][self.players[p]["action_plan_step"]]
                    action = self.board.objects[p].action_plan[i]
                    self.board.move(p, action)

                    # Check if player has reached goal
                    goal_code = p[0] + "G"
                    if not self.board.objects[p].goal_reached and self.board.at(p, goal_code):
                        # Indicate goal reached
                        self.board.objects[p].goal_reached = True
                        # Destroy goal
                        self.board.remove(goal_code)
                    # Check if player has reached tower
                    if self.board.at(p, self.tower) and \
                            all([self.board.objects[p].goal_reached for i in self.config["PLAYER_CODES"]]):
                        self.next_level()
                        return "next_level"
                    # Render result of moves
                    if self.render_game:
                        self.render()
            # CHECK IF PLAYER AND MONSTER/TRAP/STONE IN SAME AREA AFTER
            # EACH PASS OF EACH CHARACTER MOVES
            self.check_combat(i)
        return None

    def execute_enemy_plans(self):
        """
        Executes plans for enemy monsters by iterating over enemy team until no actions remain in their plans.
        :return: N/A
        """
        monsters = [i for i in self.board.objects if re.match(self.config["OBJECT_INFO"]["Monster"]["regex"], i)]
        moves = self.config["OBJECT_INFO"]["Monster"]["moves"]
        max_moves = max(list(moves.values()))

        for i in range(1, max_moves + 1):
            if not monsters:
                break
            for m in monsters:
                # Monster can move on this turn
                if i <= moves[m[1]]:
                    self.board.move_monster(m)
            # Check to see if com at needs to be initiated
            self.check_combat()
            # Render result of moves
            if self.render_game:
                self.render()
            # Some monsters may have been defeated
            monsters = [i for i in self.board.objects if re.match(self.config["OBJECT_INFO"]["Monster"]["regex"], i)]
        self.update_phase()

    def undo(self, p):
        """
        Implements an undo feature for the given player.
        :param p: The player to apply an undo action to
        :return: N/A
        """
        curr_phase = self.phases[self.phase_num]

        """
            # During pin planning, can only undo if pin is finalized, but player has not submitted plan
            if self.board.objects[p].pin_finalized 
                    and not self.players[p]["pin_plan_finalized"] 
                    and self.players[p]["pin_plan"]:
                last_action = self.players[p]["pin_plan"].pop()
                # Use the reverse of the last action selected to step the pin back to the previous position
                self.update_plan_location(p, self.reverse_actions[last_action], "pin_path")
        """
        if curr_phase == "pin_planning":
            return
        elif curr_phase == "action_planning":
            # Can only undo during action planning if there is an action in the action plan and user has not submitted
            if self.board.objects[p].action_plan:
                self.board.objects[p].action_plan.pop()
                last_position = self.board.objects[p].action_positions.pop()
                self.board.objects[p].action_plan_x = last_position[0]
                self.board.objects[p].action_plan_y = last_position[1]
                self.board.objects[p].action_points += 1
        else:
            # No-op/invalid action
            return

    ##########
    # COMBAT #
    ##########

    def check_combat(self, step_index=None):
        """
        Checks if players and enemies are co-located which would initiate combat
        :param x: The x position of the grid to check
        :param y: The y position of the grid to check
        :return: N/A
        """
        # Gets location of all players. If multiple players end up on the same grid square, using a set will ensure
        # spot is only checked once for combat
        player_loc = set([(self.board.objects[p].x, self.board.objects[p].y) for p in self.config["PLAYER_CODES"]])

        # For each location where player is present, check if there are enemies. If so, initiate combat
        for loc in player_loc:
            players = [obj for obj in self.board.board[loc].values() if isinstance(obj, Player)]
            enemies = [obj for obj in self.board.board[loc].values() if isinstance(obj, Enemy)]
            # There are enemies at this position
            if enemies:
                self.combat(players, enemies, step_index)

    # def combat(self, players, enemy_regex, enemy_type, x, y):
    def combat(self, players, enemies, step_index):
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
        # Enemies are always all the same type
        enemy_type = enemies[0].type
        player_rolls = sum([p.get_dice_roll(enemy_type) for p in players])
        enemy_rolls = sum([e.get_dice_roll() for e in enemies])

        # Players win (players win ties)
        if player_rolls >= enemy_rolls:
            self.board.multi_remove(enemies)

            for p in players:
                # self.players[p]["combat_success"] = True
                pass
                """
                if self.track_metrics:
                    if enemy_type == "Monster":
                        sizes = [
                            self.config["OBJECT_INFO"]["Monster"]["size_mapping"][e.split("(")[0]].split("_")[0]
                            for e in enemies]
                        for size in sizes:
                            self._track_player_metrics(self.players[p]["name"], metric_name="combat",
                                                       combat_outcome="win", enemy_type=enemy_type, enemy_size=size)
                    else:
                        self._track_player_metrics(self.players[p]["name"], metric_name="combat",
                                                   combat_outcome="win",
                                                   enemy_type=enemy_type)
                """
        # Players lose
        else:
            for p in players:
                if enemy_type == "Monster":
                    # Lose a heart
                    p.health -= 1
                    # Go back a step if player has moved. Only applies to player movement phase, not enemy movement
                    # step_index is used to indicate if in player movement phase (could also check phase)
                    if step_index:
                        prev_pos = p.action_positions[step_index - 1]
                        self.board.place(p, x=prev_pos[0], y=prev_pos[1])
                        # Truncate action plan, meaning the rest of the player's moves are replaced with 'wait' actions
                        p.action_plan = p.action_plan[:step_index] + \
                                        ["wait"] * (self.config["ACTIONS"]["MAX_MOVES"] - step_index)

                    # Track health lost and combat loss metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                elif enemy_type == "Trap":
                    # Lose a heart
                    p.health -= 1
                    if step_index:
                        # Truncate action plan, meaning the rest of the player's moves are replaced with 'wait' actions
                        p.action_plan = p.action_plan[:step_index] + \
                                        ["wait"] * (self.config["ACTIONS"]["MAX_MOVES"] - step_index)

                    # Track health lost and combat lost metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                elif enemy_type == "Stone":
                    if step_index:
                        # Truncate action plan, meaning the rest of the player's moves are replaced with 'wait' actions
                        p.action_plan = p.action_plan[:step_index] + \
                                        ["wait"] * (self.config["ACTIONS"]["MAX_MOVES"] - step_index)
                    # Track combat lost metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                # If player dies, remove from board
                if p.health <= 0:
                    if self.track_metrics:
                        self._track_player_metrics(p.name, metric_name="deaths")
                    p.health = 0
                    p.alive = False
                    p.death_round = self.num_rounds
                    self.board.remove(p, delete=False)
                # self.players[p]["combat_success"] = False
            # Traps are destroyed
            if enemy_type == "Trap":
                self.board.multi_remove(enemies)

    def _metrics_combat_loss(self, player, enemy_type, enemies):
        if self.track_metrics:
            if enemy_type == "Monster":
                self._track_player_metrics(player.name, metric_name="health_loss")
                sizes = [
                    self.config["OBJECT_INFO"]["Monster"]["size_mapping"][e.split("(")[0]].split("_")[0]
                    for e in enemies]
                for size in sizes:
                    self._track_player_metrics(player.name, metric_name="combat", combat_outcome="lose",
                                               enemy_type=enemy_type, enemy_size=size)
            elif enemy_type == "Trap":
                self._track_player_metrics(player.name, metric_name="health_loss")
                self._track_player_metrics(player.name, metric_name="combat", combat_outcome="lose",
                                           enemy_type=enemy_type)
            elif enemy_type == "Stone":
                self._track_player_metrics(player.name, metric_name="combat", combat_outcome="lose",
                                           enemy_type=enemy_type)

    def _track_pins(self, player_name, pin_type):
        pass

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
                    objs[obj_id] = {"x": i, "y": j}  # {"x": j, "y": i}
                    # Set what's in grid to obj_id
                    self.curr_level[i][j] = obj_id
        return objs

    #############
    # RENDERING #
    #############

    def render(self):
        """
        Renders the game in the console as an ascii grid
        :return: N/A
        """
        self.board.print_board(self.render_verbose)

    ###########
    # METRICS #
    ###########

    def get_metrics_dict(self):
        d = {}
        for lvl in self.levels:
            d[f"Level{lvl}"] = {
                "team_deaths": [],
                "rounds": [],
                "Human": self._get_player_metrics_dict(),
                "Dwarf": self._get_player_metrics_dict(),
                "Giant": self._get_player_metrics_dict()
            }
        return d

    @staticmethod
    def _get_player_metrics_dict():
        return {
            "health_loss": [],
            "deaths": [],
            "pins": {"pinga": [], "pingb": [], "pingc": [], "pingd": []},
            "combat": {"win": {"Monster": {"S": [], "M": [], "L": [], "XL": []},
                               "Stone": [],
                               "Trap": []},
                       "lose": {"Monster": {"S": [], "M": [], "L": [], "XL": []},
                                "Stone": [],
                                "Trap": []}}
        }

    @staticmethod
    def _timestamp():
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')

    def _track_game_metrics(self, metric, metric_name):
        lvl_repeat = self.num_repeats - self.lvl_repeats[self.curr_level_num]
        record = [self._timestamp(), metric, lvl_repeat]
        self.metrics[f"Level{self.curr_level_num}"][metric_name].append(record)

    def _track_player_metrics(self, player_name, metric_name, pin_type=None, combat_outcome=None, enemy_type=None,
                              enemy_size=None):
        lvl_repeat = self.num_repeats - self.lvl_repeats[self.curr_level_num]
        record = [self._timestamp(), lvl_repeat]
        if metric_name == "pins":
            self.metrics[f"Level{self.curr_level_num}"][player_name][metric_name][pin_type].append(record)
        elif metric_name == "combat":
            if enemy_type == "Monster":
                self.metrics[f"Level{self.curr_level_num}"][player_name][metric_name][combat_outcome][enemy_type][
                    enemy_size].append(record)
            else:
                self.metrics[f"Level{self.curr_level_num}"][player_name][metric_name][combat_outcome][
                    enemy_type].append(record)
        else:
            self.metrics[f"Level{self.curr_level_num}"][player_name][metric_name].append(record)

    """
    {
        "health_loss": [],
        "deaths": [],
        "pins": {"pinga": [], "pingb": [], "pingc": [], "pingd": []},
        "combat": {"win": {"Monster": {"S": [], "M": [], "L": [], "XL": []},
                           "Stone": [],
                           "Trap": []},
                   "lose": {"Monster": {"S": [], "M": [], "L": [], "XL": []},
                            "Stone": [],
                            "Trap": []}}
    }
    """

    def _save_metrics(self):
        self._save_recursive(self.metrics)

    def _save_recursive(self, d, filename=""):
        for k in d:
            curr_filename = f"{filename}"

            if not curr_filename:
                curr_filename = k
            else:
                curr_filename += f"-{k}"
            if isinstance(d[k], dict):
                self._save_recursive(d[k], curr_filename)
            elif isinstance(d[k], list):
                if d[k]:
                    curr_filename += ".txt"

                    with open(f"{self.metrics_dir}/{curr_filename}", "a" if path.exists(filename) else "w") as file:
                        for i in d[k]:
                            file.write(",".join([str(ele) for ele in i]) + "\n")


class TerminationException(Exception):
    def __init__(self):
        pass
