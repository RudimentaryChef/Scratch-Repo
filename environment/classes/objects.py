from random import choice


class GameObject:
    def __init__(self, obj_code, index, x, y):
        self.obj_code = obj_code
        self.index = index
        self.x = x
        self.y = y


class Goal(GameObject):
    def __init__(self, obj_code, index, name, type_, x, y):
        super().__init__(obj_code, index, x, y)
        self.name = name
        self.type = type_
        self.reached = False


class Shrine(Goal):
    def __init__(self, obj_code, index, name, type_, x, y, player_code):
        super().__init__(obj_code, index, name, type_, x, y)
        self.player = self.get_player(player_code)

    @staticmethod
    def get_player(player_code):
        player_goal_map = {"1": "Dwarf", "2": "Giant", "3": "Human"}
        return player_goal_map[player_code]


class Tower(Goal):
    def __init__(self, obj_code, index, name, type_, x, y):
        super().__init__(obj_code, index, name, type_, x, y)


class Enemy(GameObject):
    def __init__(self, obj_code, index, name, type_, x, y, dice_rolls):
        super().__init__(obj_code, index, x, y)
        self.name = name
        self.type = type_
        self.dice_rolls = dice_rolls

    def get_dice_roll(self, enemy_code):
        val = self.dice_rolls["val"]
        const = self.dice_rolls["const"]
        if val > 0:
            roll = choice(range(val))
        else:
            roll = 0
        return roll + const


class Player(GameObject):
    def __init__(self, obj_code, index, name, x, y, action_points, health, sight_range, dice_rolls):
        super().__init__(obj_code, index, x, y)
        # Indexing
        self.name = name
        self.type = name
        # Stats
        self.action_points = action_points
        self.health = health
        self.sight_range = sight_range
        self.dice_rolls = dice_rolls
        # Location
        self.start_x = x
        self.start_y = y
        # Status
        self.alive = True
        self.respawn_counter = None
        self.death_round = None
        self.goal_reached = False
        self.combat_success = False
        # Pinning
        self.pin_x = x
        self.pin_y = y
        self.pin_finalized = False
        # Action planning
        self.action_plan = []
        self.action_positions = []
        self.action_plan_x = None
        self.action_path_y = None
        self.action_plan_step = None
        self.action_plan_finalized = False

    def get_dice_roll(self, enemy_type):
        val = self.dice_rolls[enemy_type]["val"]
        const = self.dice_rolls[enemy_type]["const"]
        if val > 0:
            roll = choice(range(val))
        else:
            roll = 0
        return roll + const


class Pin(GameObject):
    def __init__(self, obj_code, index, x, y, placed_by):
        super().__init__(obj_code, index, x, y)
        self.placed_by = placed_by



