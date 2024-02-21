from collections import Counter
from collections import defaultdict
from datetime import datetime
from dateutil.parser import parse
from os import makedirs
from os import path
from time import time
import tensorflow as tf


class GameMetricsTracker:
    def __init__(self, level, metrics_config, instance_id=1, model_number=1):
        self.id = instance_id
        self.model_number = model_number
        self.level = level
        self.save_threshold = 10000
        self.num_records = 0
        self.metrics_config = metrics_config
        # Init values
        self.repeat_counter = Counter()
        self.num_agent_actions = 0
        self.num_rounds = 0
        self.num_games = 0
        self.num_phases = 0
        self.num_team_deaths = 0
        self.clock_start = self._timestamp(as_string=False)
        self.level_start = self._timestamp(as_string=False)
        # Time Series Lists
        self.agent_actions = defaultdict(list)
        self.levels = defaultdict(list)
        self.team_deaths = []
        self.rounds = []
        self.games = []
        self.phases = []
        self.player_trackers = {"Dwarf": PlayerMetricsTracker("Dwarf"),
                                "Giant": PlayerMetricsTracker("Giant"),
                                "Human": PlayerMetricsTracker("Human")}
        # Time series counter
        self.metric_counter = Counter()
        self.metrics_dir = self.metrics_config["DIRECTORIES"]["LOGFILES"].format(self.model_number)
        makedirs(self.metrics_dir, exist_ok=True)
        self.tb_dir = self.metrics_config["DIRECTORIES"]["TENSORBOARD"]
        self.tf_writer = tf.summary.create_file_writer(self.tb_dir)

    def save(self):
        print("SAVING!")
        ##############
        # GAME LEVEL #
        ##############
        # Levels
        for level in self.levels:
            print(self.levels.keys())
            self._save_records(records=self.levels[level], component="GAME",
                               metric="LEVEL", metric_counter_name=f"LEVEL{level}", params=[level],
                               graph_name=self.metrics_config["GAME"]["LEVEL"]["GRAPH_NAME"].format(level),
                               metric_index=-1)

        self._reset()

    def _get_filepath(self, component, metric, params=None):
        if params is None:
            params = []
        return self.metrics_dir + \
            self.metrics_config[component][metric]["FILENAME"].format(*params) + \
            self.metrics_config["EXTENSION"].format(self.id)

    def _save_records(self, records, component, metric, metric_counter_name,
                      params, graph_name=None, metric_index=None):
        filepath = self._get_filepath(component, metric, params)

        mode = "a" if path.exists(filepath) else "w"
        with open(filepath, mode) as file:
            # Need to write columns if first time
            if mode == "w":
                file.write("\t".join(self.metrics_config[component][metric]["COLUMNS"])+"\n")
            for rec in records:
                self.metric_counter[metric_counter_name] += 1

                file.write("\t".join([str(i) for i in rec])+"\n")
                if graph_name:
                    with self.tf_writer.as_default():
                        tf.summary.scalar(name=graph_name,
                                          data=float(rec[metric_index]),
                                          step=self.metric_counter[metric])
                    self.tf_writer.flush()

    def _reset(self):
        self.levels = defaultdict(list)

    def update(self, target, **kwargs):
        self.num_records += 1
        if target == "game":
            self._update_game(**kwargs)
        else:
            self._update_player(**kwargs)
        if self.num_records >= self.save_threshold:
            self.num_records = 0
            self.save()

    def _update_player(self, player, metric_name, pin_type=None,
                       combat_outcome=None, enemy_type=None, enemy_size=None):
        timestamp = self._timestamp()

        if metric_name == "pins":
            self.player_trackers[player].pin(pin_type, timestamp)
        elif metric_name == "combat":
            self.player_trackers[player].combat(enemy_type, enemy_size,
                                                combat_outcome, timestamp)
        else:
            self.player_trackers[player].generics(metric_name, timestamp)

    def _update_game(self, metric_name, player=None, agent_action=None, level=None, phase=None):
        timestamp = self._timestamp()

        if metric_name == "new_phase":
            self.num_phases += 1
            self.phases.append([timestamp, phase, self._calculate_time_elapsed(self.phases)])

        elif metric_name == "new_round":
            self.num_rounds += 1
            self.rounds.append([timestamp, self.num_rounds, self._calculate_time_elapsed(self.rounds)])

        elif metric_name == "game_over":
            self.num_games += 1
            self.games.append([timestamp, self.num_games, self._calculate_time_elapsed(self.games)])
            self.save()
        elif metric_name == "new_level":
            print("LEVEL HAS CHANGED!")
            print(F"level is: {self.level}")
            # Track time to complete last level
            self.levels[self.level].append([timestamp, self.level, self.repeat_counter[self.level],
                                            (self._timestamp(as_string=False) - self.level_start).seconds])
            # Update level
            self.level = level
            self.level_start = self._timestamp(as_string=False)
            self.repeat_counter[self.level] += 1
        elif metric_name == "num_repeats":
            # Track time to complete last level
            self.levels[self.level].append([timestamp, self.level, self.repeat_counter[self.level],
                                            (self._timestamp(as_string=False) - self.level_start).seconds])

            self.repeat_counter[self.level] += 1
            self.level_start = self._timestamp(as_string=False)
            # self.save()
        elif metric_name == "agent_action":
            self.num_agent_actions += 1
            self.agent_actions[player].append([timestamp, self.level, self.num_rounds, phase, agent_action])
        elif metric_name == "team_death":
            self.num_team_deaths += 1
            self.team_deaths.append([timestamp, self.level, self.num_rounds])

    # new round vs new phase
    def _calculate_time_elapsed(self, time_series):
        if time_series:
            # Get time elapsed since last round
            time_elapsed = self._timestamp(as_string=False) - parse(time_series[-1][0])
        else:
            time_elapsed = self._timestamp(as_string=False) - self.clock_start
        return time_elapsed.seconds

    @staticmethod
    def _timestamp(as_string=True):
        timestamp = datetime.utcnow()
        if as_string:
            timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')

        return timestamp


class PlayerMetricsTracker:
    def __init__(self, player):
        self.player = player
        self.health_loss = []
        self.deaths = []
        self.pins = {"pinga": [], "pingb": [], "pingc": [], "pingd": []}
        # Combat Tracking
        self.total_wins = 0
        self.total_losses = 0
        self.wins = self._get_enemy_tracker()
        self.losses = self._get_enemy_tracker()

    def pin(self, pin_type, timestamp):
        self.pins[pin_type].append(timestamp)

    def combat(self, enemy_type, enemy_size, outcome, timestamp):
        if outcome == "win":
            self.total_wins += 1
            self.wins[enemy_type][enemy_size].append(timestamp)
        else:
            self.total_losses += 1
            self.losses[enemy_type][enemy_size].append(timestamp)

    def generics(self, metric_name, timestamp):
        if metric_name == "death":
            self.deaths.append(timestamp)
        elif metric_name == "health_loss":
            self.health_loss.append(timestamp)

    @staticmethod
    def _get_enemy_tracker():
        return {"Monster": {"S": [], "M": [], "L": [], "XL": []},
                "Stone": {"S": [], "M": [], "L": []},
                "Trap": {"S": [], "M": [], "L": []}}






