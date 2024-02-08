from collections import Counter
from collections import defaultdict
from datetime import datetime
from os import makedirs
from time import time


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

    def pins(self, pin_type, timestamp):
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


class GameMetricsTracker:
    def __init__(self, level, model_number=1):
        self.level = level
        # Init values
        self.repeat_counter = Counter()
        self.num_agent_actions = 0
        self.num_rounds = 0
        self.num_games = 0
        self.num_phases = 0
        self.num_team_deaths = 0
        self.clock_start = time()
        # Time Series Lists
        self.agent_actions = defaultdict(list)
        self.team_deaths = []
        self.rounds = []
        self.games = []
        self.phases = []
        self.player_trackers = {"Dwarf": PlayerMetricsTracker("Dwarf"),
                                "Giant": PlayerMetricsTracker("Giant"),
                                "Human": PlayerMetricsTracker("Human")}
        self.metrics_dir = "train/{}/metrics/".format(model_number)
        makedirs(self.metrics_dir, exist_ok=True)

    def save(self):
        pass

    def update(self, target, **kwargs):
        if target == "game":
            self._update_game(**kwargs)
        else:
            self._update_player(**kwargs)

    def _update_player(self, player, metric_name, pin_type=None,
                       combat_outcome=None, enemy_type=None, enemy_size=None):
        timestamp = self._timestamp()
        if metric_name == "pins":
            self.player_trackers[player].pins(pin_type, timestamp)
        elif metric_name == "combat":
            self.player_trackers[player].combat(enemy_type, enemy_size,
                                                combat_outcome, timestamp)
        else:
            self.player_trackers[player].generics(metric_name, timestamp)

    def _update_game(self, metric_name, player=None, agent_action=None, level=None, phase=None):
        timestamp = self._timestamp()
        if metric_name == "new_phase":
            self.num_phases, time_elapsed = self._calculate_time_elapsed(self.num_phases, self.phases)
            self.phases.append([timestamp, phase, time_elapsed])

        elif metric_name == "new_round":
            self.num_rounds, time_elapsed = self._calculate_time_elapsed(self.num_rounds, self.rounds)
            self.rounds.append([timestamp, self.num_rounds, time_elapsed])

        elif metric_name == "game_over":
            self.num_games, time_elapsed = self._calculate_time_elapsed(self.num_games, self.games)
            self.games.append([timestamp, self.num_games, time_elapsed])
            self.save()
        elif metric_name == "new_level":
            self.level = level
            self.repeat_counter[self.level] += 1
            self.save()
        elif metric_name == "num_repeats":
            self.repeat_counter[self.level] += 1
            # self.save()
        elif metric_name == "agent_action":
            self.num_agent_actions += 1
            self.agent_actions[player].append([timestamp, self.level, self.num_rounds, phase, agent_action])
        elif metric_name == "team_death":
            self.num_team_deaths += 1
            self.team_deaths.append([timestamp, self.level, self.num_rounds])

    # new round vs new phase
    def _calculate_time_elapsed(self, counter, time_series):
        counter += 1
        if time_series:
            # Get time elapsed since last round
            time_elapsed = time() - time_series[-1][0]
        else:
            time_elapsed = time() - self.clock_start
        return counter, time_elapsed

    @staticmethod
    def _timestamp():
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')




