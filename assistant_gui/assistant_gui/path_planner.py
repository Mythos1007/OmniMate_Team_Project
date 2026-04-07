from __future__ import annotations

import heapq
import math
from collections import deque

import cv2
import numpy as np
from PySide6.QtGui import QPixmap, QTransform, QImage


class RoutePathPlanner:
    """Map-space path planner for GUI route visualization."""

    def __init__(
        self,
        *,
        wall_threshold: int = 180,
        wall_inflate_pixels: int = 1,
        max_snap_distance: int = 40,
    ) -> None:
        self._wall_threshold = int(wall_threshold)
        self._wall_inflate_pixels = max(0, int(wall_inflate_pixels))
        self._max_snap_distance = max(1, int(max_snap_distance))
        self._walkable_cache_key: tuple[int, tuple[int, int]] | None = None
        self._walkable_cache_points: tuple[np.ndarray, np.ndarray] | None = None

    def build_obstacle_map(self, base_map: QPixmap, coord_tf: QTransform | None = None) -> np.ndarray | None:
        """Build enclosed free-space mask from original map pixels (1=walkable, 0=wall)."""
        qimg = base_map.toImage().convertToFormat(QImage.Format.Format_RGB32)
        width, height = qimg.width(), qimg.height()
        if width <= 0 or height <= 0:
            return None

        ptr = qimg.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)).copy()
        gray = cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY)

        wall = (gray < self._wall_threshold).astype(np.uint8) * 255
        if self._wall_inflate_pixels > 0:
            k = 2 * self._wall_inflate_pixels + 1
            kernel = np.ones((k, k), np.uint8)
            wall = cv2.dilate(wall, kernel, iterations=1)

        non_wall = cv2.bitwise_not(wall)
        flood = non_wall.copy()
        mask = np.zeros((height + 2, width + 2), np.uint8)
        cv2.floodFill(flood, mask, (0, 0), 128)

        outside = flood == 128
        free_mask = (non_wall > 0) & (~outside)
        return free_mask.astype(np.uint8)

    def _get_walkable_points(self, obstacle_map: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        cache_key = (id(obstacle_map), obstacle_map.shape)
        if self._walkable_cache_key != cache_key or self._walkable_cache_points is None:
            self._walkable_cache_points = np.where(obstacle_map == 1)
            self._walkable_cache_key = cache_key
        return self._walkable_cache_points

    def find_nearest_walkable_point(
        self,
        point: tuple[float, float],
        obstacle_map: np.ndarray,
        *,
        max_radius: int,
    ) -> tuple[float, float] | None:
        """Snap a point to the nearest walkable pixel within radius."""
        h, w = obstacle_map.shape
        sx = int(round(point[0]))
        sy = int(round(point[1]))

        if 0 <= sx < w and 0 <= sy < h and obstacle_map[sy, sx] == 1:
            return float(sx), float(sy)

        ys, xs = self._get_walkable_points(obstacle_map)
        if xs.size == 0:
            return None

        d2 = (xs - sx) ** 2 + (ys - sy) ** 2
        idx = int(np.argmin(d2))
        dist = math.sqrt(float(d2[idx]))
        if dist > float(max_radius):
            return None

        return float(xs[idx]), float(ys[idx])

    @staticmethod
    def _line_is_free(
        p1: tuple[float, float],
        p2: tuple[float, float],
        obstacle_map: np.ndarray,
    ) -> bool:
        h, w = obstacle_map.shape
        ax, ay = int(round(p1[0])), int(round(p1[1]))
        bx, by = int(round(p2[0])), int(round(p2[1]))
        steps = max(abs(bx - ax), abs(by - ay)) + 1
        if steps <= 1:
            if 0 <= ax < w and 0 <= ay < h:
                return bool(obstacle_map[ay, ax] == 1)
            return False

        xs = np.rint(np.linspace(ax, bx, steps)).astype(np.int32)
        ys = np.rint(np.linspace(ay, by, steps)).astype(np.int32)
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)
        return bool(np.all(obstacle_map[ys, xs] == 1))

    def _simplify_to_straight_segments(
        self,
        path: list[tuple[float, float]],
        obstacle_map: np.ndarray,
    ) -> list[tuple[float, float]]:
        if not path:
            return []

        simplified = [path[0]]
        i = 0
        while i < len(path) - 1:
            farthest = i + 1
            for j in range(i + 2, len(path)):
                if self._line_is_free(path[i], path[j], obstacle_map):
                    farthest = j
                else:
                    break
            simplified.append(path[farthest])
            i = farthest

        cleaned = [simplified[0]]
        for p in simplified[1:]:
            px, py = cleaned[-1]
            if math.hypot(p[0] - px, p[1] - py) >= 2.0:
                cleaned.append(p)
        if cleaned[-1] != simplified[-1]:
            cleaned.append(simplified[-1])

        return cleaned

    @staticmethod
    def _compress_orthogonal_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) <= 2:
            return points

        compressed = [points[0]]
        prev_dx = None
        prev_dy = None

        for i in range(1, len(points)):
            prev_x, prev_y = points[i - 1]
            curr_x, curr_y = points[i]
            dx = 0 if curr_x == prev_x else (1 if curr_x > prev_x else -1)
            dy = 0 if curr_y == prev_y else (1 if curr_y > prev_y else -1)

            if prev_dx is None:
                prev_dx, prev_dy = dx, dy
                continue

            if dx != prev_dx or dy != prev_dy:
                compressed.append(points[i - 1])
                prev_dx, prev_dy = dx, dy

        compressed.append(points[-1])
        return compressed

    def _find_grid_path(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
        obstacle_map: np.ndarray,
        *,
        grid_size: int,
        allow_diagonal: bool,
    ) -> list[tuple[float, float]]:
        h, w = obstacle_map.shape
        grid_h = (h + grid_size - 1) // grid_size
        grid_w = (w + grid_size - 1) // grid_size

        def is_walkable(gy: int, gx: int) -> bool:
            if not (0 <= gy < grid_h and 0 <= gx < grid_w):
                return False
            y0 = gy * grid_size
            x0 = gx * grid_size
            y1 = min(y0 + grid_size, h)
            x1 = min(x0 + grid_size, w)
            cell = obstacle_map[y0:y1, x0:x1]
            return bool(cell.all())

        start_grid = (int(start[1] / grid_size), int(start[0] / grid_size))
        goal_grid = (int(goal[1] / grid_size), int(goal[0] / grid_size))
        if not is_walkable(start_grid[0], start_grid[1]) or not is_walkable(goal_grid[0], goal_grid[1]):
            return []

        def ordered_neighbors(gy: int, gx: int) -> list[tuple[int, int]]:
            goal_dy = goal_grid[0] - gy
            goal_dx = goal_grid[1] - gx
            vertical_first = abs(goal_dy) >= abs(goal_dx)
            step_y = 1 if goal_dy > 0 else -1
            step_x = 1 if goal_dx > 0 else -1

            vertical_dirs = [(step_y, 0), (-step_y, 0)]
            horizontal_dirs = [(0, step_x), (0, -step_x)]
            dirs = vertical_dirs + horizontal_dirs if vertical_first else horizontal_dirs + vertical_dirs

            unique_dirs: list[tuple[int, int]] = []
            for direction in dirs:
                if direction not in unique_dirs:
                    unique_dirs.append(direction)

            if allow_diagonal:
                diagonal_dirs = [
                    (step_y, step_x),
                    (step_y, -step_x),
                    (-step_y, step_x),
                    (-step_y, -step_x),
                ]
                for direction in diagonal_dirs:
                    if direction not in unique_dirs:
                        unique_dirs.append(direction)
            return unique_dirs

        queue = deque([(start_grid, [start_grid])])
        visited = {start_grid}

        while queue:
            (gy, gx), path = queue.popleft()
            if (gy, gx) == goal_grid:
                pixel_path: list[tuple[float, float]] = [start]
                for cell_y, cell_x in path[1:-1]:
                    pixel_path.append(
                        (cell_x * grid_size + grid_size // 2, cell_y * grid_size + grid_size // 2)
                    )
                pixel_path.append(goal)
                return self._compress_orthogonal_path(pixel_path)

            for dy, dx in ordered_neighbors(gy, gx):
                ny, nx = gy + dy, gx + dx
                if (ny, nx) in visited:
                    continue
                if not is_walkable(ny, nx):
                    continue
                if dy != 0 and dx != 0:
                    if not is_walkable(gy + dy, gx) or not is_walkable(gy, gx + dx):
                        continue

                visited.add((ny, nx))
                queue.append(((ny, nx), path + [(ny, nx)]))

        return []

    def _find_pixel_path_astar(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
        obstacle_map: np.ndarray,
    ) -> list[tuple[float, float]]:
        h, w = obstacle_map.shape
        sx, sy = int(round(start[0])), int(round(start[1]))
        gx, gy = int(round(goal[0])), int(round(goal[1]))

        if not (0 <= sx < w and 0 <= sy < h and 0 <= gx < w and 0 <= gy < h):
            return []
        if obstacle_map[sy, sx] == 0 or obstacle_map[gy, gx] == 0:
            return []

        start_node = (sx, sy)
        goal_node = (gx, gy)

        def heuristic(node: tuple[int, int]) -> float:
            x, y = node
            return math.hypot(gx - x, gy - y)

        directions = [
            (-1, 0, 1.0),
            (1, 0, 1.0),
            (0, -1, 1.0),
            (0, 1, 1.0),
            (-1, -1, math.sqrt(2.0)),
            (-1, 1, math.sqrt(2.0)),
            (1, -1, math.sqrt(2.0)),
            (1, 1, math.sqrt(2.0)),
        ]

        open_heap: list[tuple[float, tuple[int, int]]] = []
        heapq.heappush(open_heap, (heuristic(start_node), start_node))

        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start_node: 0.0}
        closed: set[tuple[int, int]] = set()

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal_node:
                path_nodes = [current]
                while current in came_from:
                    current = came_from[current]
                    path_nodes.append(current)
                path_nodes.reverse()
                return [(float(x), float(y)) for (x, y) in path_nodes]

            closed.add(current)
            cx, cy = current
            for dx, dy, cost in directions:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                if obstacle_map[ny, nx] == 0:
                    continue

                neighbor = (nx, ny)
                tentative_g = g_score[current] + cost
                if tentative_g >= g_score.get(neighbor, float("inf")):
                    continue

                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor)
                heapq.heappush(open_heap, (f_score, neighbor))

        return []

    def plan(
        self,
        start_rot: tuple[float, float],
        goal_rot: tuple[float, float],
        obstacle_map: np.ndarray,
        *,
        start_radius: int = 80,
        goal_radius: int = 220,
    ) -> list[tuple[float, float]]:
        """Plan route in rotated map pixel space."""
        plan_start = self.find_nearest_walkable_point(start_rot, obstacle_map, max_radius=start_radius)
        plan_goal = self.find_nearest_walkable_point(goal_rot, obstacle_map, max_radius=goal_radius)
        if plan_start is None or plan_goal is None:
            return []

        def path_length(points: list[tuple[float, float]]) -> float:
            total = 0.0
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                total += abs(x2 - x1) + abs(y2 - y1)
            return total

        # Prioritize pixel-level A* for reliable visible paths in UI (same direction as standalone test script).
        pixel_path = self._find_pixel_path_astar(plan_start, plan_goal, obstacle_map)
        if pixel_path:
            return self._simplify_to_straight_segments(pixel_path, obstacle_map)

        best_path: list[tuple[float, float]] = []
        best_key = None
        for grid_size, allow_diagonal in ((8, False), (6, False), (4, False), (2, False), (1, True)):
            candidate = self._find_grid_path(
                plan_start,
                plan_goal,
                obstacle_map,
                grid_size=grid_size,
                allow_diagonal=allow_diagonal,
            )
            if not candidate:
                continue

            key = (path_length(candidate), len(candidate))
            if best_key is None or key < best_key:
                best_key = key
                best_path = candidate

        if best_path:
            return self._simplify_to_straight_segments(best_path, obstacle_map)
        return []
