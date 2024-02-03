from copy import deepcopy
from datetime import datetime
from json import loads
from os import makedirs
from os import path
import re
from environment.classes.board import Board
from environment.classes.objects import *


class DiceAdventure:
    def __init__(self, level=1, limit_levels=None, render=False, render_verbose=False, num_repeats=0,
                 restart_on_finish=False, round_cap=0, level_sampling=False,
                 track_metrics=False, metrics_dir=None, metrics_save_threshold=10000):

        #################
        # GAME METADATA #
        #################
        self.config = loads(open("environment/config.json", "r").read())
        self.terminated = False

        ##############
        # LEVEL VARS #
        ##############
        # Level Setup
        self.levels = {}
        self.limit_levels = limit_levels if limit_levels else [int(i) for i in list(self.config["LEVELS"].keys())]
        self.get_levels()
        # Level Control
        self.curr_level_num = level if level in self.limit_levels else self.limit_levels[0]
        self.curr_level = deepcopy(self.levels[self.curr_level_num])
        self.num_repeats = num_repeats
        self.lvl_repeats = {lvl: self.num_repeats for lvl in self.levels}
        self.restart_on_finish = restart_on_finish
        self.restart_on_team_loss = False
        # Object codes
        self.empty = ".."
        self.tower = "**"
        self.wall = "##"

        # Places a cap on the number of rounds per level
        self.round_cap = round_cap
        # Determines whether levels should be randomly sampled
        self.level_sampling = level_sampling
        self.respawn_wait = 2

        ##########
        # BOARD #
        #########
        self.board = Board(width=len(self.curr_level[0]),
                           height=len(self.curr_level),
                           object_positions=self.curr_level,
                           config=self.config)

        ##############
        # PHASE VARS #
        ##############
        self.phase_num = 0
        self.phases = self.config["PHASES"]["PHASE_LIST"]
        # Pin Planning
        self.pinning_phase_name = self.config["PHASES"]["PINNING_PHASE_NAME"]
        self.valid_pin_actions = self.config["ACTIONS"]["VALID_PIN_ACTIONS"]
        self.valid_pin_types = self.config["ACTIONS"]["VALID_PIN_TYPES"]
        self.pin_code_mapping = self.config["OBJECT_INFO"]["Pin"]["code_mapping"]
        # Action Planning
        self.planning_phase_name = self.config["PHASES"]["PLANNING_PHASE_NAME"]
        self.valid_move_actions = self.config["ACTIONS"]["VALID_MOVE_ACTIONS"]
        self.reverse_actions = self.config["ACTIONS"]["REVERSE_ACTIONS"]
        # Actions
        self.directions = self.config["ACTIONS"]["DIRECTIONS"]
        # Enemy Execution
        self.enemy_execution_phase_name = self.config["PHASES"]["ENEMY_EXECUTION_PHASE_NAME"]
        #############
        # RENDERING #
        #############
        self.render_game = render
        self.render_verbose = render_verbose

        ###################
        # METRIC TRACKING #
        ###################
        self.track_metrics = track_metrics
        self.metrics = self.get_metrics_dict()
        self.metrics_dir = metrics_dir if metrics_dir is not None else "monitoring"
        makedirs(self.metrics_dir, exist_ok=True)
        # Number of calls to execute_action() or get_state() functions
        self.num_calls = 0
        # Number of rounds completed
        self.num_rounds = 0
        # After this number of calls to the game, save metrics in log files
        self.metrics_save_threshold = metrics_save_threshold

    #################
    # LEVEL CONTROL #
    #################
    def get_levels(self):
        levels = deepcopy(self.config["LEVELS"])
        # This makes sure positions are indexed with origin at "bottom left"
        self.levels = {
            int(k): [[row[i:i + 2] for i in range(0, len(row), 2)] for row in reversed(v.strip().split("\n"))]
            for k, v in levels.items()
            if int(k) in self.limit_levels
        }

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

        eligible_levels = [k for k, v in self.lvl_repeats.items() if v >= 0]
        if not eligible_levels:
            self.terminated = True
            if self.track_metrics:
                self._save_metrics()
            return

        self.get_next_level(eligible_levels)

        # If finished final level and set to restart, go back to first level
        if self.curr_level_num > len(self.levels) and not self.level_sampling:
            if self.restart_on_finish:
                # print(f"RESTARTING TO FIRST LEVEL!")
                self.curr_level_num = self.limit_levels[0]
            else:
                self.terminated = True
                if self.track_metrics:
                    self._save_metrics()
                return

        # Set current level
        self.curr_level = deepcopy(self.levels[self.curr_level_num])
        # Re-initialize values
        self.board = Board(width=len(self.curr_level[0]),
                           height=len(self.curr_level),
                           object_positions=self.curr_level,
                           config=self.config)
        self.phase_num = 0
        self.num_rounds = 0

    def get_next_level(self, eligible_levels):

        # If level sampling turned on, randomly sample for next level
        if self.level_sampling:
            self.curr_level_num = choice(list(eligible_levels))
        else:
            # Otherwise, move on to next level
            self.curr_level_num += 1
        print(f"CHANGING TO LEVEL: {self.curr_level_num}", self.lvl_repeats, self.num_calls)
        self.lvl_repeats[self.curr_level_num] -= 1


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
            "status": "OK" if not self.terminated else "Done",
            "message": "Full State",
            "content": {
                "gameData": {
                    "boardWidth": len(self.curr_level[0]),
                    "boardHeight": len(self.curr_level),
                    "level": self.curr_level_num,
                    "num_repeats": self.num_repeats - self.lvl_repeats[self.curr_level_num],
                    "currentPhase": self.phases[self.phase_num],
                },
                "scene": []
            }
        }
        # Used to track when level restart is due to all characters dying
        if self.restart_on_team_loss:
            self.restart_on_team_loss = False

        for pos, obj_dict in self.board.board.items():
            # Walls
            if obj_dict is None:
                state["content"]["scene"].append({"type": "wall", "x": int(pos[0]), "y": int(pos[1])})
            else:
                for o in obj_dict:
                    obj = obj_dict[o]

                    ele = {"type": obj.type, "x": obj.x, "y": obj.y}
                    if isinstance(obj, Player):
                        ele.update({
                            "name": obj.name,
                            "characterId": int(obj.obj_code[0]),
                            "pinCursorX": obj.pin_x,
                            "pinCursorY": obj.pin_y,
                            "sightRange": obj.sight_range,
                            "monsterDice": f"D{obj.dice_rolls['Monster']['val']}+{obj.dice_rolls['Monster']['const']}",
                            "trapDice": f"D{obj.dice_rolls['Trap']['val']}+{obj.dice_rolls['Trap']['const']}",
                            "stoneDice": f"D{obj.dice_rolls['Stone']['val']}+{obj.dice_rolls['Stone']['const']}",
                            "health": obj.health,
                            "dead": obj.dead,
                            "actionPoints": obj.action_points,
                            "actionPlan": obj.action_plan,
                            "action_plan_finalized": obj.action_plan_finalized
                        })
                    # Goals
                    elif isinstance(obj, Shrine):
                        ele.update({
                            "reached": obj.reached,
                            "character": obj.player
                        })
                    elif isinstance(obj, Tower):
                        ele.update({
                            "subgoalCount": obj.subgoal_count
                        })
                    # Enemies
                    elif isinstance(obj, Enemy):
                        ele.update({
                            "name": obj.index,
                            "actionPoints": self.config["OBJECT_INFO"]["Monster"]["moves"][obj.obj_code[1]],
                            "combatDice": f"D{obj.dice_rolls['val']}+{obj.dice_rolls['const']}"
                        })
                    # Pins
                    elif isinstance(obj, Pin):
                        ele.update({
                            "name": obj.name,
                            "placedBy": obj.placed_by
                        })
                    state["content"]["scene"].append(ele)
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

        if self.phases[self.phase_num] == self.pinning_phase_name:
            self.pin_planning(player, action)
        elif self.phases[self.phase_num] == self.planning_phase_name:
            self.action_planning(player, action)
        # If all characters have exhausted their action points, move phase along
        # If this is turned off, all players must submit first before progressing
        # if all([obj.action_points <= 0 for obj in self.board.objects.values() if isinstance(obj, Player)]):
        #     print("EXHAUSTED ACTION POINTS!")
        #    self.update_phase()
        # Render grid
        # if self.render_game:
        #    self.render()

    def check_player_status(self):
        """
        Checks whether players are dead or alive and respawn players if enough game cycles have passed
        :return: N/A
        """
        dead = [p for p in self.config["PLAYER_CODES"] if self.board.objects[p].dead]
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
                    self.board.objects[p].dead = False
                    self.board.objects[p].death_round = None
                    self.board.objects[p].prev_x = self.board.objects[p].start_x
                    self.board.objects[p].prev_y = self.board.objects[p].start_y
                    self.board.place(p, x=self.board.objects[p].start_x, y=self.board.objects[p].start_y)

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
        if self.board.objects[player].dead or \
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
                x, y = self.board.update_location_by_direction(action,
                                                               self.board.objects[player].pin_x,
                                                               self.board.objects[player].pin_y)
                self.board.objects[player].pin_x = x
                self.board.objects[player].pin_y = y

            elif action in self.valid_pin_types:
                # Place new pin
                self.board.place(self.pin_code_mapping[action],
                                 self.board.objects[player].pin_x,
                                 self.board.objects[player].pin_y,
                                 create=True,
                                 placed_by=player)
                self.board.objects[player].placed_pin = True
                self.board.objects[player].action_points -= 1
                # Reset pin_x and pin_y location to player position
                self.board.objects[player].pin_x = self.board.objects[player].x
                self.board.objects[player].pin_y = self.board.objects[player].y
        # If player is out of action points and has placed a pin, they are forced to submit
        if self.board.objects[player].placed_pin and self.board.objects[player].action_points <= 0:
            self.board.objects[player].pin_finalized = True

        self.check_phase()

    def action_planning(self, player, action):
        """
        Executes logic for the action planning phase.
        :param player: The player to apply an action to
        :param action: The action to apply
        :return: N/A
        """
        # Player is dead, can not take actions at this time
        if self.board.objects[player].dead \
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
                    self.board.objects[player].action_positions.append((new_y, new_x))
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
        if curr_phase == self.pinning_phase_name and all([self.board.objects[p].pin_finalized
                                                          for p in self.config["PLAYER_CODES"]
                                                          if not self.board.objects[p].dead]):
            for p in self.config["PLAYER_CODES"]:
                # Reset values
                self.board.objects[p].pin_x = None
                self.board.objects[p].pin_y = None
                self.board.objects[p].pin_finalized = False
            # Change to action planning phase
            self.update_phase()
        elif curr_phase == self.planning_phase_name \
                and all([self.board.objects[p].action_plan_finalized
                         for p in self.config["PLAYER_CODES"]
                         if not self.board.objects[p].dead]):
            # Update phase to player execution
            self.update_phase()

            if self.execute_plans():
                self.next_level()
                return
            # Change to enemy execution phase
            self.update_phase()
            # Remove pins and reset player values
            objs = list(self.board.objects.keys())
            for o in objs:
                if isinstance(self.board.objects[o], Player):
                    self.board.objects[o].reset_phase_values()
                elif isinstance(self.board.objects[o], Pin):
                    self.board.remove(o)

    def update_phase(self):
        """
        Moves the game to the next phase.
        :return: N/A
        """
        self.phase_num = (self.phase_num + 1) % len(self.phases)
        # Check if players need respawning
        self.check_player_status()
        # Trigger enemy movement
        if self.phases[self.phase_num] == self.enemy_execution_phase_name:
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
        # print("EXECUTING PLAYER MOVEMENT")
        max_moves = max([len(self.board.objects[p].action_plan) for p in self.config["PLAYER_CODES"]])
        for i in range(max_moves):
            for p in self.config["PLAYER_CODES"]:
                # If player is alive, can move
                if not self.board.objects[p].dead and i < len(self.board.objects[p].action_plan):
                    # Get action to make and move
                    # action = self.players[p]["action_plan"][self.players[p]["action_plan_step"]]
                    action = self.board.objects[p].action_plan[i]
                    self.board.move(p, action, delete=False)

                    # Check if player has reached goal
                    goal_code = p[0] + "G"
                    if not self.board.objects[p].goal_reached and self.board.at(p, goal_code):
                        # Indicate goal reached
                        self.board.objects[p].goal_reached = True
                        # Destroy goal
                        # self.board.remove(goal_code)
                        # Increment subgoal counter
                        self.board.objects[self.tower].subgoal_count += 1
                    # Check if player has reached tower
                    if self.board.at(p, self.tower) and \
                            all([self.board.objects[p].goal_reached for i in self.config["PLAYER_CODES"]]):
                        # self.update_phase()
                        return True
                    # Render result of moves
                    # if self.render_game:
                    #    self.render()
            # CHECK IF PLAYER AND MONSTER/TRAP/STONE IN SAME AREA AFTER
            # EACH PASS OF EACH CHARACTER MOVES
            self.check_combat(i)
        # self.update_phase()
        return False

    def execute_enemy_plans(self):
        """
        Executes plans for enemy monsters by iterating over enemy team until no actions remain in their plans.
        :return: N/A
        """
        # print("EXECUTING ENEMY MOVEMENT")
        monsters = [i for i in self.board.objects.values() if isinstance(i, Enemy) and i.name == "Monster"]
        if monsters:
            # for i in range(1, max_moves + 1):
            move_count = 0
            done = False
            while not done:
                done = True
                for m in monsters:
                    # Monster can move on this turn
                    if move_count < m.action_points:
                        done = False
                        self.board.move_monster(m.index, self.directions.copy())
                # Check to see if com at needs to be initiated
                self.check_combat()

                # Render result of moves
                # if self.render_game:
                #    self.render()
                # Some monsters may have been defeated
                monsters = [i for i in self.board.objects.values() if isinstance(i, Enemy) and i.name == "Monster"]
                move_count += 1
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
        if curr_phase == self.pinning_phase_name:
            return
        elif curr_phase == "action_planning":
            # Can only undo during action planning if there is an action in the action plan and user has not submitted
            if self.board.objects[p].action_plan:
                self.board.objects[p].action_plan.pop()
                last_position = self.board.objects[p].action_positions.pop()
                self.board.objects[p].action_plan_x = last_position[1]
                self.board.objects[p].action_plan_y = last_position[0]
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
        :param step_index: Determines the position in the action sequence
        :return: N/A
        """
        # Gets location of all players. If multiple players end up on the same grid square, using a set will ensure
        # spot is only checked once for combat
        player_loc = set([(self.board.objects[p].y, self.board.objects[p].x) for p in self.config["PLAYER_CODES"]])
        # For each location where player is present, check if there are enemies. If so, initiate combat
        for loc in player_loc:
            players = [obj for obj in self.board.board[loc].values() if isinstance(obj, Player)]
            enemies = [obj for obj in self.board.board[loc].values() if isinstance(obj, Enemy)]
            # There are enemies at this position
            if enemies and players:
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
        enemy_type = enemies[0].name
        player_rolls = sum([p.get_dice_roll(enemy_type) for p in players])
        enemy_rolls = sum([e.get_dice_roll() for e in enemies])

        # Players win (players win ties)
        if player_rolls >= enemy_rolls:
            # print("PLAYERS WIN!")
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
            # print("MONSTERS WIN!")
            # print(f"PLAYERS: {[p.index for p in players]}")
            for p in players:
                # print(p.index, enemy_type)
                if enemy_type == "Monster":
                    # Lose a heart
                    p.health -= 1
                    # Go back a step if player has moved. Only applies to player movement phase, not enemy movement
                    # step_index is used to indicate if in player movement phase (could also check phase)
                    if step_index and p.action_plan:
                        # print(f"CHARACTER: {p.index} STEPPING BACK")
                        # Truncate action plan
                        p.action_plan = []
                        # Get last position of player
                        prev_pos = p.action_positions[step_index - 1]
                        p.action_positions = []
                        self.board.place(p.index, x=prev_pos[1], y=prev_pos[0])

                    # Track health lost and combat loss metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                elif enemy_type == "Trap":
                    # Lose a heart
                    p.health -= 1
                    if step_index:
                        # Truncate action plan
                        p.action_plan = []
                        p.action_positions = []

                    # Track health lost and combat lost metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                elif enemy_type == "Stone":
                    if step_index:
                        # Truncate action plan
                        p.action_plan = []
                        p.action_positions = []
                    # Track combat lost metrics
                    self._metrics_combat_loss(p, enemy_type, enemies)
                # If player dies, remove from board
                if p.health <= 0:
                    if self.track_metrics:
                        self._track_player_metrics(p.name, metric_name="deaths")
                    # print(f"CHARACTER: {p.index} HAS DIED")
                    p.health = 0
                    p.dead = True
                    p.death_round = self.num_rounds
                    # self.board.remove(p.index, delete=False)
                # self.players[p]["combat_success"] = False
            # Traps are destroyed
            if enemy_type == "Trap":
                self.board.multi_remove(enemies)

    #############
    # RENDERING #
    #############

    def render(self):
        """
        Renders the game in the console as an ascii grid
        :return: N/A
        """
        self.board.print_board(self.render_verbose,
                               self.curr_level_num,
                               self.phases[self.phase_num],
                               self.num_rounds,
                               self.round_cap)

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
