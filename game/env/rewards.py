
#########
# GOALS #
#########

def goal_reached(g1, g2, state, next_state):
    # no goal in prev state, goal in next state
    # no goal in either state but next state is new level

    # Goal has now been reached since previous state
    # OR goal was not reached in previous state but either:
    # 1. level has changed meaning it would have been reached, OR
    # 2. The level is the same but has repeated, indicated by the num_repeats field incrementing
    # Repeating in this way does not apply to team losses and level resets
    return (not g1["reached"] and g2["reached"]) \
        or (not g1["reached"]
            and (state["content"]["gameData"]["level"] != next_state["content"]["gameData"]["level"]
                 or state["content"]["gameData"]["num_repeats"] < next_state["content"]["gameData"]["num_repeats"]))


def check_new_level(state, next_state):
    return state["content"]["gameData"]["level"] != next_state["content"]["gameData"]["level"]
    # or \
    #    (self.prev_state["content"]["gameData"]["level"] == next_state["content"]["gameData"]["level"] and
    #     self.prev_state["content"]["gameData"]["num_repeats"] < next_state["content"]["gameData"]["num_repeats"])


###################
# ACTION PLANNING #
###################

def has_moved(p1, p2):
    """
    Checks if player has moved since last state.
    :param p1: Player info from previous state.
    :param p2: Player info from current state.
    :return: True/False
    """
    return p1["x"] != p2["x"] or p1["y"] != p2["y"]


################
# PIN PLANNING #
################

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


##########
# COMBAT #
##########

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


def health_lost_or_dead(p1, p2):
    """
    Checks difference between previous and next state to determine if a player has lost health or died
    :param next_state: The state resulting from the previous action
    :return: True if a player has lost health or died, False otherwise
    """
    return (p1["health"] < p2["health"]) or p2["dead"]  # or (not p1["dead"] and p2["dead"])
def enemy_reduced(p1,p2):
    """
    Checks if there are less enemies in the next state compared to previous state
    :param p1: The json file for the first scene
    :param p2: The json file for the second scene
    :return: True if there are less enemies now, false otherwise
    """
    enemies1 = count_number_in_scene(p1, "Monster")
    enemies2 = count_number_in_scene(p2, "Monster")
    if(enemies1 > enemies2):
        return True
def count_number_in_scene(json_data, entity):
    """
    Helper method to count the number of an entity in the scene
    :param json_data: The json file for the first scene
    :param entity: A tag inside the entity type that we want to count
    :return: integer length of entity count
    """
    entity = {entity for entity in json_data['content']['scene'] if entity['type'].contains(entity)}
    return len(entity)
