from shop2.domain import Axiom
from shop2.domain import Method
from shop2.domain import Operator
# from py_rete import And
# from py_rete import Fact
# from py_rete import Not
"""
Methods: set_pin, move
Operators: decide
Misc: A* search to goal
Questions: 
1. Does the 'agent' have access to the state when HTN planning or must information from the state be explicitly passed
in as arguments?
2. Should operators have conditions or just arguments?
3.Note: Shop2 operators can add facts AND relations to state
"""

"""
Methods:
1. Get player to personal shrine/goal
2. Get player to tower once all shrines/goals have been reached
"""

#############
# OPERATORS #
#############

"""
Effects of operators for dice adventure must generate 'SAI' tuples. The code will check the working memory to determine
if an SAI tuple has been generated and submit it to the game, then remove the SAI tuple.

self.action_map = {0: 'left', 1: 'right', 2: 'up', 3: 'down', 4: 'wait',
                   5: 'submit', 6: 'pinga', 7: 'pingb', 8: 'pingc', 9: 'pingd', 10: 'undo'}
"""
move_left = Operator(
    head=('move-left', 'p', '?w'),
    conditions=[('type', '?w', 'wall'),
                ('not', ('left-of', '?w', 'p')),
                ('actionPoints', 'p', '?apv'),
                (lambda apv: apv > 0, '?apv')],
    effects=[('sai', 'p', 'left')]
)

move_right = Operator(
    head=('move-right', 'p', '?w'),
    conditions=[('not', ('right-of', '?w', 'p')), ('type', '?w', 'wall')],
    effects=[('sai', 'p', 'right')]
)

move_forward = Operator(
    head=('move-forward', 'p', '?w'),
    conditions=[('not', ('in-front-of', '?w', 'p')), ('type', '?w', 'wall')],
    effects=[('sai', 'p', 'up')]
)

move_backward = Operator(
    head=('move-backward', 'p', '?w'),
    conditions=[('not', ('behind', '?w', 'p')), ('type', '?w', 'wall')],
    effects=[('sai', 'p', 'down')]
)

##########
# AXIOMS #
##########

# Elements left of another share the same 'y' value, different 'x' values
left_of = Axiom(
    head=('left-of', '?a', '?b'),
    conditions=[('x', '?a', '?ax'),
                ('y', '?a', '?y'),
                ('x', '?b', '?bx'),
                ('y', '?b', '?y'),
                (lambda ax, bx: ax < bx, '?ax', '?bx')])

# Elements right of another share the same 'y' value, different 'x' values
right_of = Axiom(
    head=('right-of', '?a', '?b'),
    conditions=[('x', '?a', '?ax'),
                ('y', '?a', '?y'),
                ('x', '?b', '?bx'),
                ('y', '?b', '?y'),
                (lambda ax, bx: ax > bx, '?ax', '?bx')])

# Elements in front of another share the same 'x' value, different 'y' values
in_front_of = Axiom(
    head=('in-front-of', '?a', '?b'),
    conditions=[('x', '?a', '?x'),
                ('y', '?a', '?ay'),
                ('x', '?b', '?x'),
                ('y', '?b', '?by'),
                (lambda ay, by: ay < by, '?ay', '?by')])

# Elements behind another share the same 'x' value, different 'y' values
behind = Axiom(
    head=('behind', '?a', '?b'),
    conditions=[('x', '?a', '?x'),
                ('y', '?a', '?ay'),
                ('x', '?b', '?x'),
                ('y', '?b', '?by'),
                (lambda ay, by: ay > by, '?ay', '?by')])
