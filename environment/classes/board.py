from collections import Counter
from collections import defaultdict
import re
from tabulate import tabulate
from environment.classes.objects import *


class Board:
    def __init__(self, width, height, object_positions, config):
        self.width = None
        self.height = None
        self.board = None
        self.objects = None
        self.config = config
        # Keeps track of object counts for indexing purposes
        self.obj_counts = None
        # Initialize board
        self.reset_board(width, height, object_positions)

    def reset_board(self, width, height, object_positions):
        self.board = defaultdict(dict)
        self.objects = {}
        # Keeps track of object counts for indexing purposes
        self.obj_counts = Counter()

        if width or height:
            self.width = width
            self.height = height
        for i in range(self.width):
            for j in range(self.height):
                if object_positions[i][j] == "##":
                    self.board[(i,j)] = None
                elif object_positions[i][j] == "..":
                    self.board[(i,j)] = {}
                else:
                    obj = self.create_object(i, j, object_positions[i][j])
                    self.board[(i,j)][obj.index] = obj
                    self.objects[obj.index] = obj

    def create_object(self, x_pos, y_pos, obj_code, placed_by=None):
        """

        :param x_pos:
        :param y_pos:
        :param obj_code:
        :param placed_by: Special parameter for pins. Determines which player placed pin
        :return:
        """
        self.obj_counts[obj_code] += 1
        index = obj_code
        if self.obj_counts[obj_code] > 1:
            index += f"({self.obj_counts[obj_code]})"
        # Player objects
        if re.match("\\dS", obj_code):
            obj = Player(obj_code=obj_code,
                         index=index,
                         name=self.config["OBJECT_CODES"][obj_code]["name"],
                         x=x_pos,
                         y=y_pos,
                         action_points=self.config["OBJECT_CODES"][obj_code]["action_points"],
                         health=self.config["OBJECT_CODES"][obj_code]["health"],
                         sight_range=self.config["OBJECT_CODES"][obj_code]["sight_range"],
                         dice_rolls=self.config["OBJECT_CODES"][obj_code]["dice_rolls"])
        # Enemy objects
        elif re.match("(M\\d|S\\d|T\\d)", obj_code):
            obj = Enemy(obj_code=obj_code,
                        index=index,
                        name=self.config["OBJECT_CODES"][obj_code]["name"],
                        type_=self.config["OBJECT_CODES"][obj_code]["type"],
                        x=x_pos,
                        y=y_pos,
                        dice_rolls=self.config["OBJECT_CODES"][obj_code]["dice_rolls"])
        # Special objects
        else:
            # Walls and empty spaces don't get their own python objects
            if obj_code in ["##", ".."]:
                obj = None
            # Tower object
            elif obj_code == "**":
                obj = Tower(obj_code=obj_code,
                            index=index,
                            name=self.config["OBJECT_CODES"][obj_code]["name"],
                            type_=self.config["OBJECT_CODES"][obj_code]["type"],
                            x=x_pos,
                            y=y_pos)
            # Shrine objects
            elif re.match("\\dG", obj_code):
                obj = Shrine(obj_code=obj_code,
                             index=index,
                             name=self.config["OBJECT_CODES"][obj_code]["name"],
                             type_=self.config["OBJECT_CODES"][obj_code]["type"],
                             x=x_pos,
                             y=y_pos,
                             player_code=obj_code[0])
            # Pin objects
            else:
                obj = Pin(obj_code=obj_code,
                          index=index,
                          x=x_pos,
                          y=y_pos,
                          placed_by=placed_by)

        return obj


    ##########################
    # POSITIONING & MOVEMENT #
    ##########################

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

    def valid_move(self, x, y, action):
        mapping = {"left": (x, y-1), "right": (x, y+1), "up": (x-1, y), "down": (x+1, y), "wait": (x, y)}
        return self.check_valid_move(*mapping[action])

    def update_location_by_direction(self, action, x, y):
        """
        Updates character location based on given directional action. Note that when a 2D array is printed,
        moving "up" is equivalent to going down one index in the list of rows and vice versa for
        moving "down". Therefore, "up" decreases the x coordinate by 1 and "down" increases the
        x coordinate by 1.
        :param action:
        :param x:
        :param y:
        :return:
        """
        if action == "wait":
            pass
        elif action == "left" and self.check_valid_move(x, y - 1):
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

        options = [("left", x, y - 1), ("right", x, y + 1), ("up", x - 1, y), ("down", x + 1, y)]
        shuffle(options)
        while options:
            op = options.pop()
            if self.check_valid_move(op[1], op[2],
                                     avoid=[self.enemy_regexes["Stone"], self.enemy_regexes["Trap"]],
                                     as_regex=True):
                self.move(m, action=op[0], x=op[1], y=op[2], old_pos=old_pos)
                break

    def move(self, obj, action, x=None, y=None, old_pos=None):
        """
        Moves the given object according to the given action
        :param object: The object to move
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
            x = self.objects[obj].x
            y = self.objects[obj].y
            old_pos = (x, y)

            x, y = self.update_location_by_direction(action, x, y)

        self.place(obj, x, y, old_x=old_pos[0], old_y=old_pos[1])

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
        # if index:
        #     obj = f"{obj}({index})"
        # Update location of object
        self.objects[obj].x = x
        self.objects[obj].y = y
        self.board[(x,y)][obj] = obj

        # Remove obj from old position if it was previously on the grid
        if old_x is not None:
            self.remove(obj, old_x, old_y, delete=False)


        if obj not in self.object_pos:
            self.object_pos[obj] = {"x": x, "y": y}
        else:
            self.object_pos[obj]["x"] = x
            self.object_pos[obj]["y"] = y

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
            x = self.objects[obj].x
            y = self.objects[obj].y
        # Delete object from board
        del self.board[(x,y)][obj]
        # In this case, should delete object entirely (from game)
        if delete:
            del self.objects[obj]

    def multi_remove(self, objs):
        """
        Removes the given objects from the grid
        :param objs: A list of objects to remove
        :return: N/A
        """
        for o in objs:
            if isinstance(o, GameObject):
                obj_index = o.index
            else:
                obj_index = o
            self.remove(obj_index)

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
        return self.objects[player].x == self.objects[obj].x \
            and self.objects[player].y == self.objects[obj].y

    def print_board(self, render_verbose=False):
        if render_verbose:
            info = [
                ["Level:", self.curr_level_num],
                ["Phase:", self.phases[self.phase_num]]
            ]
            print("Game Info:")
            print(tabulate(info, tablefmt="grid"))

        table = []
        for i in range(self.width):
            row = []
            for j in range(self.height):
                # Wall
                if self.board[(i,j)] is None:
                    row.append("##")
                # Empty dict == empty space
                elif not self.board[(i,j)]:
                    row.append(" ")
                else:
                    string = "-".join([o.index for o in self.board[(i,j)].values()])
                    row.append(string)
            table.append(row)
        print("Grid:")
        print(tabulate(table, tablefmt="grid"), end="\n\n")
