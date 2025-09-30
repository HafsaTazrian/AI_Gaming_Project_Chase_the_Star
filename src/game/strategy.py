from random import randint, choice
from collections.abc import Sequence
from collections import deque
import heapq

from game import cfg
from game.action import Action
from grid import Grid
import game.map as gm
import game.role as gr

ActionLevels = dict[Action, float]


class _Spot:
    """
    Used by A* path-finding.
    """
    def __init__(self, x: int, y: int) -> None:
        self._pos: tuple[int, int] = (x, y)
        self.prev: '_Spot' = None
        self.g: float = 0
        self.h: float = 0
        self.neighbors: list['_Spot'] = []

    @property
    def pos(self) -> tuple[int, int]:
        return self._pos

    @property
    def x(self) -> int:
        return self._pos[0]

    @property
    def y(self) -> int:
        return self._pos[1]

    @property
    def f(self) -> float:
        return self.g + self.h

    def clear(self) -> None:
        self.prev = None
        self.g = 0
        self.h = 0

    def retrace(self) -> list['_Spot']:
        """
        Retrace the path to the current spot.
        """
        path = [self]
        spot = self
        while spot.prev:
            path.insert(0, spot.prev)
            spot = spot.prev
        return path


class Strategy:
    """
    The interface of action strategy.
    """
    MAX_ACTION_LVL: float = 10

    @staticmethod
    def new_init_lvls() -> ActionLevels:
        """
        Create an initial recommendation array.
        """
        return {action: 0 for action in Action}

    def __init__(self, role: 'gr.Role') -> None:
        self._role: 'gr.Role' = role

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        """
        Get an array containing the level of recommendation for every action.
        Subclasses should implement their logic.
        """
        assert False

    def _delete_invalid(self, lvls: ActionLevels) -> ActionLevels:
        """
        Delete invalid actions.
        """
        for action in Action:
            dest = action.dest(self._role.pos)
            invalid = not self._role.map.valid(*dest)
            wall = not invalid and self._role.revealed(dest) and self._role.map.wall(*dest)
            if invalid or wall:
                lvls[action] = 0
        return lvls


class ActionSelector:
    """
    Choose the action according to the specific weights.
    """
    @staticmethod
    def equality(strategy_num: int) -> 'ActionSelector':
        """
        Create a default selector with all weights equal to 1.
        """
        return ActionSelector([1] * strategy_num)

    def __init__(self, weights: Sequence[float]) -> None:
        self.weights: Sequence[float] = weights

    def highest(self, lvl_matrix: Sequence[ActionLevels]) -> Action:
        """
        Choose the action with the highest level of recommendation.
        """
        if len(lvl_matrix) == 0:
            return Action.STAY

        total = Strategy.new_init_lvls()

        def merge(lvls: ActionLevels, weight: float) -> None:
            """
            Merge two recommendation arrays.
            """
            assert len(lvls) == len(total)
            for action in Action:
                total[action] += lvls[action] * weight

        for i in range(len(self.weights)):
            merge(lvl_matrix[i], self.weights[i])

        # If two or more actions have the same level, get a random one.
        choices = []
        best = Action(0)
        for action in Action:
            if total[action] > total[best]:
                choices = [action]
                best = action
            elif total[action] == total[best]:
                choices.append(action)
        return choices[randint(0, len(choices) - 1)]


class Random(Strategy):
    """
    Choose an action randomly.
    """
    @staticmethod
    def name() -> str:
        return "random"

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        for action in Action:
            lvls[action] = randint(0, int(self.MAX_ACTION_LVL))
        self._delete_invalid(lvls)
        lvls[Action.STAY] = 0

        max_action = Action(0)
        for action in Action:
            if lvls[action] > lvls[max_action]:
                max_action = action
        lvls[max_action] = self.MAX_ACTION_LVL
        return lvls


class MoveAway(Strategy):
    """
    Choose an action to move away to the target.
    """
    @staticmethod
    def name() -> str:
        return "moveAway"

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        target = status.opponent(self._role)
        lvls = self.new_init_lvls()
        if self._role.pos[0] >= target.pos[0]:
            lvls[Action.RIGHT] = Strategy.MAX_ACTION_LVL
        else:
            lvls[Action.LEFT] = Strategy.MAX_ACTION_LVL

        if self._role.pos[1] >= target.pos[1]:
            lvls[Action.UP] = Strategy.MAX_ACTION_LVL
        else:
            lvls[Action.DOWN] = Strategy.MAX_ACTION_LVL
        return self._delete_invalid(lvls)


class MoveClose(Strategy):
    """
    Choose an action to move closer to the target.
    """
    @staticmethod
    def name() -> str:
        return "moveClose"

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        target = status.opponent(self._role)
        lvls = self.new_init_lvls()
        if self._role.pos[0] > target.pos[0]:
            lvls[Action.LEFT] = Strategy.MAX_ACTION_LVL
        elif self._role.pos[0] < target.pos[0]:
            lvls[Action.RIGHT] = Strategy.MAX_ACTION_LVL

        if self._role.pos[1] > target.pos[1]:
            lvls[Action.DOWN] = Strategy.MAX_ACTION_LVL
        elif self._role.pos[1] < target.pos[1]:
            lvls[Action.UP] = Strategy.MAX_ACTION_LVL
        return self._delete_invalid(lvls)


class WallDensity(Strategy):
    """
    Find a direction where the density of walls is lower.
    """
    _RANGE: int = 5

    @staticmethod
    def name() -> str:
        return "wallDensity"

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        for action in Action:
            lvls[action] = (1 - self._density(action)) * Strategy.MAX_ACTION_LVL
        lvls[Action.STAY] = 0
        return self._delete_invalid(lvls)

    def _density(self, action: Action) -> float:
        """
        Calculate the density of wall in a direction.
        """
        pos = self._role.pos
        if action == Action.LEFT:
            begin = (pos[0] - self._RANGE, pos[1] - self._RANGE)
            end = (pos[0], pos[1] + self._RANGE)
        elif action == Action.RIGHT:
            begin = (pos[0], pos[1] - self._RANGE)
            end = (pos[0] + self._RANGE, pos[1] + self._RANGE)
        elif action == Action.UP:
            begin = (pos[0] - self._RANGE, pos[1])
            end = (pos[0] + self._RANGE, pos[1] + self._RANGE)
        elif action == Action.DOWN:
            begin = (pos[0] - self._RANGE, pos[1] - self._RANGE)
            end = (pos[0] + self._RANGE, pos[1])
        else:
            return Strategy.MAX_ACTION_LVL

        total, wall = 1, 1
        for x in range(begin[0], end[0]):
            for y in range(begin[1], end[1]):
                total += 1
                if not self._role.map.valid(x, y) or (self._role.revealed((x, y)) and self._role.map.wall(x, y)):
                    wall += 1
        return round(wall / total, 2)


class AStar(Strategy):
    """
    A* path-finding (original implementation).
    """
    @staticmethod
    def name() -> str:
        return "aStar"

    def __init__(self, role: 'gr.Role') -> None:
        super().__init__(role)
        self._prev_path: list[_Spot] = []

        spots = [[None] * role.map.height for _ in range(role.map.width)]
        for x in range(role.map.width):
            for y in range(role.map.height):
                spots[x][y] = _Spot(x, y)
        self._grid: Grid = Grid(spots)
        self._init_neighbors()

    @property
    def prev_path(self) -> list[tuple[int, int]]:
        """
        Get the previous path.
        """
        return [spot.pos for spot in self._prev_path]

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        self._prev_path = self._path(status)
        if len(self._prev_path) > 1:
            action = Action.next(self._role.pos, self._prev_path[1].pos)
            lvls[action] = Strategy.MAX_ACTION_LVL
        elif len(self._prev_path) == 1:
            lvls[Action.STAY] = Strategy.MAX_ACTION_LVL
        return lvls

    def _path(self, status: 'gm.Status') -> list[_Spot]:
        """
        Find a path to the current target.
        """
        self._clear_spots()
        heuristic = cfg.heuristic
        open_set, closed_set = [], []

        def next_pos() -> _Spot:
            assert len(open_set) > 0
            pos = min(open_set, key=lambda s: s.f)
            open_set.remove(pos)
            return pos

        src = self._role.pos
        if isinstance(self._role, gr.Enemy):
            dest = status.enemy_target()
        else:
            dest = status.opponent(self._role).pos
        
        start_spot = self._grid.spot(*src)
        start_spot.h = heuristic(src, dest)
        open_set.append(start_spot)
        
        while len(open_set) > 0:
            spot = next_pos()
            if spot.pos == dest:
                return spot.retrace()
            closed_set.append(spot)

            for neighbor in spot.neighbors:
                if neighbor in closed_set:
                    continue
                new_g = spot.g + heuristic(spot.pos, neighbor.pos)
                if self._role.revealed(neighbor.pos):
                    if self._role.map.wall(*neighbor.pos):
                        continue
                    else:
                        new_g += self._role.map.move_cost(*neighbor.pos)
                else:
                    new_g += cfg.move_cost["grass"]

                new_path = False
                if neighbor in open_set:
                    if new_g < neighbor.g:
                        neighbor.g = new_g
                        new_path = True
                else:
                    neighbor.g = new_g
                    neighbor.h = heuristic(neighbor.pos, dest)
                    new_path = True
                    open_set.append(neighbor)

                if new_path:
                    neighbor.prev = spot
        return []

    def _init_neighbors(self) -> None:
        """
        Initialize the neighbors of each spot.
        """
        for x in range(self._role.map.width):
            for y in range(self._role.map.height):
                spot = self._grid.spot(x, y)
                spot.neighbors = self._grid.neighbors(x, y)

    def _clear_spots(self) -> None:
        """
        Clear the path-finding record.
        """
        for x in range(self._role.map.width):
            for y in range(self._role.map.height):
                if self._grid.valid(x, y):
                    self._grid.spot(x, y).clear()


class Dijkstra(Strategy):
    """
    Dijkstra's algorithm - finds shortest path without heuristic.
    Better when terrain costs vary significantly.
    """
    @staticmethod
    def name() -> str:
        return "dijkstra"

    def __init__(self, role: 'gr.Role') -> None:
        super().__init__(role)
        self._prev_path: list[tuple[int, int]] = []

    @property
    def prev_path(self) -> list[tuple[int, int]]:
        return self._prev_path

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        self._prev_path = self._find_path(status)
        if len(self._prev_path) > 1:
            action = Action.next(self._role.pos, self._prev_path[1])
            lvls[action] = Strategy.MAX_ACTION_LVL
        elif len(self._prev_path) == 1:
            lvls[Action.STAY] = Strategy.MAX_ACTION_LVL
        return lvls

    def _find_path(self, status: 'gm.Status') -> list[tuple[int, int]]:
        src = self._role.pos
        if isinstance(self._role, gr.Enemy):
            dest = status.enemy_target()
        else:
            dest = status.opponent(self._role).pos

        # Priority queue: (cost, position)
        pq = [(0, src)]
        costs = {src: 0}
        previous = {}
        visited = set()

        while pq:
            current_cost, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)

            if current == dest:
                # Reconstruct path
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(src)
                return list(reversed(path))

            # Check all 4 neighbors
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if not self._role.map.valid(nx, ny):
                    continue
                if self._role.revealed(neighbor) and self._role.map.wall(nx, ny):
                    continue

                move_cost = self._role.map.move_cost(nx, ny) if self._role.revealed(neighbor) else cfg.move_cost["grass"]
                new_cost = current_cost + move_cost

                if neighbor not in costs or new_cost < costs[neighbor]:
                    costs[neighbor] = new_cost
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_cost, neighbor))

        return []


class BFS(Strategy):
    """
    Breadth-First Search - finds path with minimum number of steps.
    Ignores terrain costs. Fast and simple.
    """
    @staticmethod
    def name() -> str:
        return "bfs"

    def __init__(self, role: 'gr.Role') -> None:
        super().__init__(role)
        self._prev_path: list[tuple[int, int]] = []

    @property
    def prev_path(self) -> list[tuple[int, int]]:
        return self._prev_path

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        self._prev_path = self._find_path(status)
        if len(self._prev_path) > 1:
            action = Action.next(self._role.pos, self._prev_path[1])
            lvls[action] = Strategy.MAX_ACTION_LVL
        elif len(self._prev_path) == 1:
            lvls[Action.STAY] = Strategy.MAX_ACTION_LVL
        return lvls

    def _find_path(self, status: 'gm.Status') -> list[tuple[int, int]]:
        src = self._role.pos
        if isinstance(self._role, gr.Enemy):
            dest = status.enemy_target()
        else:
            dest = status.opponent(self._role).pos

        queue = deque([src])
        visited = {src}
        previous = {}

        while queue:
            current = queue.popleft()

            if current == dest:
                # Reconstruct path
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(src)
                return list(reversed(path))

            # Check all 4 neighbors
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if neighbor in visited:
                    continue
                if not self._role.map.valid(nx, ny):
                    continue
                if self._role.revealed(neighbor) and self._role.map.wall(nx, ny):
                    continue

                visited.add(neighbor)
                previous[neighbor] = current
                queue.append(neighbor)

        return []


class Greedy(Strategy):
    """
    Greedy Best-First Search - uses only heuristic (no path cost).
    Fast but not optimal. Good for quick reactions.
    """
    @staticmethod
    def name() -> str:
        return "greedy"

    def __init__(self, role: 'gr.Role') -> None:
        super().__init__(role)
        self._prev_path: list[tuple[int, int]] = []

    @property
    def prev_path(self) -> list[tuple[int, int]]:
        return self._prev_path

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        self._prev_path = self._find_path(status)
        if len(self._prev_path) > 1:
            action = Action.next(self._role.pos, self._prev_path[1])
            lvls[action] = Strategy.MAX_ACTION_LVL
        elif len(self._prev_path) == 1:
            lvls[Action.STAY] = Strategy.MAX_ACTION_LVL
        return lvls

    def _find_path(self, status: 'gm.Status') -> list[tuple[int, int]]:
        src = self._role.pos
        if isinstance(self._role, gr.Enemy):
            dest = status.enemy_target()
        else:
            dest = status.opponent(self._role).pos

        heuristic = cfg.heuristic

        # Priority queue: (heuristic_value, position)
        pq = [(heuristic(src, dest), src)]
        visited = set()
        previous = {}

        while pq:
            _, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)

            if current == dest:
                # Reconstruct path
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(src)
                return list(reversed(path))

            # Check all 4 neighbors
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if neighbor in visited:
                    continue
                if not self._role.map.valid(nx, ny):
                    continue
                if self._role.revealed(neighbor) and self._role.map.wall(nx, ny):
                    continue

                previous[neighbor] = current
                h = heuristic(neighbor, dest)
                heapq.heappush(pq, (h, neighbor))

        return []


class JPS(Strategy):
    """
    Jump Point Search - optimized A* for uniform-cost grids.
    Reduces nodes explored by "jumping" over straight paths.
    Very fast on open maps.
    """
    @staticmethod
    def name() -> str:
        return "jps"

    def __init__(self, role: 'gr.Role') -> None:
        super().__init__(role)
        self._prev_path: list[tuple[int, int]] = []

    @property
    def prev_path(self) -> list[tuple[int, int]]:
        return self._prev_path

    def action_lvls(self, status: 'gm.Status') -> ActionLevels:
        lvls = self.new_init_lvls()
        self._prev_path = self._find_path(status)
        if len(self._prev_path) > 1:
            action = Action.next(self._role.pos, self._prev_path[1])
            lvls[action] = Strategy.MAX_ACTION_LVL
        elif len(self._prev_path) == 1:
            lvls[Action.STAY] = Strategy.MAX_ACTION_LVL
        return lvls

    def _is_walkable(self, x: int, y: int) -> bool:
        if not self._role.map.valid(x, y):
            return False
        if self._role.revealed((x, y)) and self._role.map.wall(x, y):
            return False
        return True

    def _jump(self, x: int, y: int, dx: int, dy: int, dest: tuple[int, int]) -> tuple[int, int] | None:
        """
        Recursively search for jump points in direction (dx, dy).
        """
        nx, ny = x + dx, y + dy
        
        if not self._is_walkable(nx, ny):
            return None
        if (nx, ny) == dest:
            return (nx, ny)

        # Check for forced neighbors
        if dx != 0 and dy != 0:  # Diagonal movement
            if (self._is_walkable(nx - dx, ny) and not self._is_walkable(nx - dx, ny - dy)) or \
               (self._is_walkable(nx, ny - dy) and not self._is_walkable(nx - dx, ny - dy)):
                return (nx, ny)
            # Check horizontal and vertical
            if self._jump(nx, ny, dx, 0, dest) or self._jump(nx, ny, 0, dy, dest):
                return (nx, ny)
        else:  # Straight movement
            if dx != 0:  # Horizontal
                if (self._is_walkable(nx, ny + 1) and not self._is_walkable(nx - dx, ny + 1)) or \
                   (self._is_walkable(nx, ny - 1) and not self._is_walkable(nx - dx, ny - 1)):
                    return (nx, ny)
            else:  # Vertical
                if (self._is_walkable(nx + 1, ny) and not self._is_walkable(nx + 1, ny - dy)) or \
                   (self._is_walkable(nx - 1, ny) and not self._is_walkable(nx - 1, ny - dy)):
                    return (nx, ny)

        # Continue jumping
        return self._jump(nx, ny, dx, dy, dest)

    def _find_path(self, status: 'gm.Status') -> list[tuple[int, int]]:
        src = self._role.pos
        if isinstance(self._role, gr.Enemy):
            dest = status.enemy_target()
        else:
            dest = status.opponent(self._role).pos

        heuristic = cfg.heuristic

        # Priority queue: (f_score, g_score, position)
        pq = [(0, 0, src)]
        g_scores = {src: 0}
        previous = {}
        visited = set()

        while pq:
            _, current_g, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)

            if current == dest:
                # Reconstruct path
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(src)
                return list(reversed(path))

            # Identify successors (jump points)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                jump_point = self._jump(current[0], current[1], dx, dy, dest)
                if jump_point and jump_point not in visited:
                    new_g = current_g + heuristic(current, jump_point)
                    
                    if jump_point not in g_scores or new_g < g_scores[jump_point]:
                        g_scores[jump_point] = new_g
                        f_score = new_g + heuristic(jump_point, dest)
                        previous[jump_point] = current
                        heapq.heappush(pq, (f_score, new_g, jump_point))

        # Fallback to simple BFS if JPS fails
        return self._bfs_fallback(src, dest)

    def _bfs_fallback(self, src: tuple[int, int], dest: tuple[int, int]) -> list[tuple[int, int]]:
        """Simple BFS as fallback."""
        queue = deque([src])
        visited = {src}
        previous = {}

        while queue:
            current = queue.popleft()
            if current == dest:
                path = []
                while current in previous:
                    path.append(current)
                    current = previous[current]
                path.append(src)
                return list(reversed(path))

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if neighbor not in visited and self._is_walkable(*neighbor):
                    visited.add(neighbor)
                    previous[neighbor] = current
                    queue.append(neighbor)
        return []