from draftsman.blueprintable import Blueprint
from draftsman.constants import Direction
from draftsman.utils import Vector
from draftsman.entity import ConstantCombinator, TransportBelt, Entity, Splitter, UndergroundBelt
from math import floor, ceil
from escapeable import escapable
import webbrowser

def dir_to_offset(direction: Direction) -> Vector:
    if(direction == Direction.NORTH):
        return Vector(0, -1)
    if(direction == Direction.EAST):
        return Vector(1, 0)
    if(direction == Direction.SOUTH):
        return Vector(0, 1)
    if(direction == Direction.WEST):
        return Vector(-1, 0)
    raise TypeError("Illegal direction!")

def dir_inverse(direction: Direction):
    if(direction == Direction.NORTH):
        return Direction.SOUTH
    if(direction == Direction.EAST):
        return Direction.WEST
    if(direction == Direction.SOUTH):
        return Direction.NORTH
    if(direction == Direction.WEST):
        return Direction.EAST
    raise TypeError("Illegal direction!")

def find_belt(tile_x: int, tile_y: int):
    for next_entity in bp.find_entities_filtered(position=[tile_x + 0.5, tile_y + 0.5]):
        if isinstance(next_entity, TransportBelt) or isinstance(next_entity, UndergroundBelt) or isinstance(next_entity, Splitter):
            return next_entity
    return None

# Returns the left and right tile
def get_both_splitter_tile_positions(splitter: Splitter):
    if(splitter.direction == Direction.NORTH):
        return [
            Vector(splitter.tile_position.x    , splitter.tile_position.y),
            Vector(splitter.tile_position.x + 1, splitter.tile_position.y),
        ]
    if(splitter.direction == Direction.SOUTH):
        return [
            Vector(splitter.tile_position.x + 1, splitter.tile_position.y),
            Vector(splitter.tile_position.x    , splitter.tile_position.y),
        ]  
    if(splitter.direction == Direction.EAST):
        return [
            Vector(splitter.tile_position.x, splitter.tile_position.y    ),
            Vector(splitter.tile_position.x, splitter.tile_position.y + 1),
        ]
    if(splitter.direction == Direction.WEST):
        return [
            Vector(splitter.tile_position.x, splitter.tile_position.y + 1),
            Vector(splitter.tile_position.x, splitter.tile_position.y    ),
        ]
    raise TypeError("Illegal!")

def is_feeding(source: TransportBelt | UndergroundBelt | Splitter, target: TransportBelt | UndergroundBelt | Splitter):
    # Check source and entity are connected
    if isinstance(source, Splitter):
        source_positions = get_both_splitter_tile_positions(source)
    else:
        source_positions = [source.tile_position]
    if isinstance(target, Splitter):
        target_positions = get_both_splitter_tile_positions(target)
    else:
        target_positions = [target.tile_position]
    valid_target_positions = [pos + dir_to_offset(source.direction) for pos in source_positions]
    found = False
    for pos_src in valid_target_positions:
        for pos_dst in target_positions:
            if pos_src == pos_dst:
                found = True
                break
    if not found:
        return False
    
    # Check for opposite belt directions
    if target.direction is dir_inverse(source.direction):
        return False
    # Splitters can only be fed from one direction, no sideloading
    if isinstance(target, Splitter) and target.direction is not source.direction:
        return False
    return True

def get_max_underground_belt_distance(underground_belt: UndergroundBelt):
    if underground_belt.name == "underground-belt":
        return 4
    if underground_belt.name == "fast-underground-belt":
        return 6
    if underground_belt.name == "express-underground-belt":
        return 8
    raise RuntimeError(f'Unknown underground belt type: {underground_belt}')

def find_input_belt(tile_x: int, tile_y: int, direction: Direction, neighbor_offsets: list[Vector]):
    entity = find_belt(x, y)
    if isinstance(entity, TransportBelt) and entity.direction == direction:
        neighbors = [find_belt(x + offset.x, y + offset.y) for offset in neighbor_offsets]
        found_feeding_neighbor = False
        for neighbor in neighbors:
            if neighbor is not None and is_feeding(neighbor, entity):
                found_feeding_neighbor = True
                break
        # If there isn't a neighboring belt that outputs into this belt
        if not found_feeding_neighbor:
            return entity
        else:
            # Since there is a belt in the search direction that is not an input belt, terminate search
            return "stop_search"
    return None

def handle_splitter_prio(previous: TransportBelt | UndergroundBelt | Splitter, splitter: Splitter):
    #print(f'# Handle splitter prio for {next_entity}, getting fed from {previous}')
    prio_left = False
    prio_right = False
    [left_tile, right_tile] = [pos - dir_to_offset(splitter.direction) for pos in get_both_splitter_tile_positions(splitter)]
    left = find_belt(left_tile.x, left_tile.y)
    right = find_belt(right_tile.x, right_tile.y)
    #print(f'# left: {left}, right: {right}')
    if left is not None and is_feeding(left, splitter) and (left == previous or (hasattr(left, "visited_by_belt_prio") and left.visited_by_belt_prio == True)):
        prio_left = True
    if right is not None and is_feeding(right, splitter) and (right == previous or (hasattr(right, "visited_by_belt_prio") and right.visited_by_belt_prio == True)):
        prio_right = True
    
    if prio_left and prio_right:
        splitter.input_priority = None
    elif prio_left and not prio_right:
        splitter.input_priority = "left"
    elif not prio_left and prio_right:
        splitter.input_priority = "right"
    else:
        raise RuntimeError("Invalid state!")

# input() seems to corrupt the input string? Newlines perhaps?
bp_str = input("Enter balancer blueprint string:")
bp = Blueprint()
bp.load_from_string(bp_str)
print(f'# Parsed blueprint!')

# positive x goes east, positive y goes south
(top_left_corner_x, top_left_corner_y) = (floor(bp.area.world_top_left[0]), floor(bp.area.world_top_left[1]))
(bottom_right_corner_x, bottom_right_corner_y) = (ceil(bp.area.world_bot_right[0]), ceil(bp.area.world_bot_right[1]))

print(f'# Blueprint dimension: {top_left_corner_x},{top_left_corner_y} -> {bottom_right_corner_x},{bottom_right_corner_y}')

# Search for input lanes
input_lanes: list[TransportBelt] = []

# Query top, looking for belts that face to the south
for x in range(top_left_corner_x, bottom_right_corner_x):
    with escapable() as label_a:
        for y in range(top_left_corner_y, bottom_right_corner_y):
            entity = find_input_belt(x, y, Direction.SOUTH, [Vector(1, 0), Vector(-1, 0)])
            if isinstance(entity, TransportBelt):
                print(f'# Found southern transport belt at {x},{y}!')
                input_lanes.append(entity)
            if not entity is None: # Found an TransportBelt or got "stop_search"
                label_a.escape() # break label_a


# Query bottom, looking for belts that face to the north
for x in range(top_left_corner_x, bottom_right_corner_x):
    with escapable() as label_a:
        for y in reversed(range(top_left_corner_y, bottom_right_corner_y)):
            entity = find_input_belt(x, y, Direction.NORTH, [Vector(1, 0), Vector(-1, 0)])
            if isinstance(entity, TransportBelt):
                print(f'# Found northern transport belt at {x},{y}!')
                input_lanes.append(entity)
            if not entity is None: # Found an entity or got "stop_search"
                label_a.escape() # break label_a

# Query left, looking for belts that face to the east
for y in range(top_left_corner_y, bottom_right_corner_y):
    with escapable() as label_a:
        for x in range(top_left_corner_x, bottom_right_corner_x):
            entity = find_input_belt(x, y, Direction.EAST, [Vector(0, 1), Vector(0, -1)])
            if isinstance(entity, TransportBelt):
                print(f'# Found eastern transport belt at {x},{y}!')
                input_lanes.append(entity)
            if not entity is None: # Found an entity or got "stop_search"
                label_a.escape() # break label_a

# Query right, looking for belts that face to the west
for y in range(top_left_corner_y, bottom_right_corner_y):
    with escapable() as label_a:
        for x in reversed(range(top_left_corner_x, bottom_right_corner_x)):
            entity = find_input_belt(x, y, Direction.WEST, [Vector(0, 1), Vector(0, -1)])
            if isinstance(entity, TransportBelt):
                print(f'# Found western transport belt at {x},{y}!')
                input_lanes.append(entity)
            if not entity is None: # Found an entity or got "stop_search"
                label_a.escape() # break label_a

if len(input_lanes) == 0:
    print("Found no input belts. Exiting!")
    exit(1)

for i, input_lane in enumerate(input_lanes):
    constant_combinator = ConstantCombinator(id=f'input_lane_marker_{i}')
    constant_combinator.tile_position = input_lane.tile_position + dir_to_offset(dir_inverse(input_lane.direction))
    constant_combinator.direction = input_lane.direction
    for j, c in enumerate(str(i)):
        letter_signal = "signal-{}".format(c)
        constant_combinator.set_signal(index=j, signal=letter_signal, count=0)
    bp.entities.append(constant_combinator)

webbrowser.open_new(f'https://fbe.teoxoy.com/?source={bp.to_string()}')
print(f'Opened webpage for input belt selection. If this didnt work, instead import this blueprint: \n{bp.to_string()}')
_in = input("Enter comma-seperated list of prioritized input belts:\n")
prioritized_indices = [int(e) for e in _in.split(',') if e.strip().isdigit() and int(e) < len(input_lanes) and int(e) >= 0]
if len(prioritized_indices) > 0:
    print(f'Selected belts {prioritized_indices}')
else:
    print(f'Invalid selection; Exiting!')
    exit(1)

# Delete input belt markers again
for i in range(0, len(input_lanes)):
    # Cursed, but all other ways just didn't work :(
    bp.entities.recursive_remove(bp.entities[f'input_lane_marker_{i}'])

# Do the actual prioritization
queue: list[TransportBelt | UndergroundBelt | Splitter] = [input_lanes[i] for i in prioritized_indices]
while(len(queue) > 0):
    # current_entity is either a TransportBelt, UndergroundBelt or Splitter
    current_entity: Entity = queue.pop()

    # Skip entities since that already have been processed
    if hasattr(current_entity, "visited_by_belt_prio") and current_entity.visited_by_belt_prio == True:
        continue
    

    # If TransportBelt or output underground belt, just look for next entity
    if isinstance(current_entity, TransportBelt) or (isinstance(current_entity, UndergroundBelt) and current_entity.io_type == "output"):
        # Look for next belt
        next_entity_pos = current_entity.tile_position + dir_to_offset(current_entity.direction)
        next_entity = find_belt(next_entity_pos.x, next_entity_pos.y)
        if next_entity is not None and is_feeding(current_entity, next_entity):
            if isinstance(next_entity, Splitter):
                handle_splitter_prio(current_entity, next_entity)
            queue.append(next_entity)

    # Input underground belt, search for output...
    elif isinstance(current_entity, UndergroundBelt) and current_entity.io_type == "input":
        # search for output belt
        current_pos = current_entity.position + dir_to_offset(current_entity.direction)
        distance_searched = 0
        max_distance = get_max_underground_belt_distance(current_entity) + 1
        while(distance_searched < max_distance):
            for next_entity in bp.find_entities_filtered(position=current_pos):
                if isinstance(next_entity, UndergroundBelt) and next_entity.io_type == "output" and next_entity.name == current_entity.name and not next_entity.direction == dir_inverse(current_entity.direction):
                    # Found the output, exit loop
                    queue.append(next_entity)
                    distance_searched = 999999
                    break
            current_pos += dir_to_offset(current_entity.direction)
            distance_searched += 1

    # Handle splitter
    elif isinstance(current_entity, Splitter):
        next_tiles = [pos + dir_to_offset(current_entity.direction) for pos in get_both_splitter_tile_positions(current_entity)]
        for next_entity in [find_belt(pos.x, pos.y) for pos in next_tiles]:
            if next_entity is not None and is_feeding(current_entity, next_entity):
                if isinstance(next_entity, Splitter):
                    handle_splitter_prio(current_entity, next_entity)
                queue.append(next_entity)

    # Unexpected entity
    else:
        raise RuntimeError(f'Got weird entity: {current_entity}')
    
    # Done here
    current_entity.visited_by_belt_prio = True

# Done with prioritization!
print(f'Done!\n{bp.to_string()}')








    
    

