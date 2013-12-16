
import random
import time

import pygame

DEBUG = False

BOARD_SIZE = 9
COLOR_LIST = ('red', 'yellow', 'purple', 'green', 'cyan', 'blue', 'brown')
SPAWN_BEADS = 3
MIN_BEADS_FOR_REMOVAL = 5
SCORE_FACTOR = 10
BONUS_FACTOR_1 = 1.1
BONUS_FACTOR_2 = 1.2
WINDOW_WIDTH = 300
WINDOW_HEIGHT = 300
BOARD_MARGIN = 20
CELL_PADDING = 3
EXT_LINE_WIDTH = 3
INT_LINE_WIDTH = 1
LINE_COLOR = 'white'
SCORE_COLOR = 'white'
SEL_COLOR = 'white'
BOARD_COLOR = 'black'
DESPAWN_COLOR = 'pink'
SCORE_FONTFACE = 'Courier'
SCORE_FONTSIZE = 16
TICK_RATE = 0.04
ANIMATE_SPAWN_FOR = 1.0
ANIMATE_DESPAWN_FOR = 0.75
MOVE_DELAY = 0.15
SEL_F1 = 5
SEL_F2 = 3
SPAWN_F1 = 6
SPAWN_F2 = 2
DESPAWN_F1 = 1
DESPAWN_F2 = 2

INIT = pygame.USEREVENT
TICK = INIT + 1
SPAWN = TICK + 1
UNSPAWN = SPAWN + 1
DESPAWN = UNSPAWN + 1
UNDESPAWN = DESPAWN + 1
GO = UNDESPAWN + 1

def addvec(a, b):
    return [x + y for x, y in zip(a, b)]

def mulvec(a, c):
    return [c * x for x in a]

class EvtStream(object):
    def __init__(self, handler, evts = []):
        self.handler = handler
        self.scheduled = {}
        for evt in evts:
            self.schedule(evt)
        self.loop()

    def stream(self):
        while True:
            yield pygame.event.poll()

    def loop(self):
        for evt in self.stream():
            self.handler.handle(self, evt)
            self.post_scheduled()
            
    def schedule(self, evt, t = 0.0):
        t += time.time()
        if t not in self.scheduled:
            self.scheduled[t] = []
        self.scheduled[t].append(evt)

    def post_scheduled(self):
        cur_t = time.time()
        rem = []
        for t in self.scheduled:
            if t <= cur_t:
                for evt in self.scheduled[t]:
                    pygame.event.post(evt)
                rem.append(t)
        for t in rem:
            del self.scheduled[t]

class QuitHandler(object):
    def handle(self, stream, evt):
        if evt.type == pygame.QUIT:
            pygame.quit()
            exit()

class DebugHandler(object):
    def handle(self, stream, evt):
        if evt.type not in (pygame.NOEVENT, TICK):
            if DEBUG:
                print evt

class LambdaHandler(object):
    def __init__(self, f, t = None):
        self.f = f
        self.t = t

    def handle(self, stream, evt):
        if self.t is None or evt.type == self.t:
            self.f(stream, evt)

class CompositeHandler(object):
    def __init__(self, handlers):
        self.handlers = handlers

    def handle(self, stream, evt):
        for h in self.handlers:
            h.handle(stream, evt)

class Board(object):
    def __init__(self, size, colors):
        self.size = size
        self.colors = colors
        self.erase()

    def erase(self):
        self.score = 0
        self.board = [[None for ix in range(self.size)] for jx in range(self.size)]

    def spawn(self, n):
        if n <= 0:
            return []
        ixs = self.free()
        if len(ixs) == 0:
            return []
        x, y = random.choice(ixs)
        c = random.choice(self.colors)
        self.board[x][y] = c
        return [(x, y)] + self.spawn(n - 1)

    def free(self):
        res = []
        for ix in range(self.size):
            for jx in range(self.size):
                if self.board[ix][jx] is None:
                    res.append((ix, jx))
        return res

    def valid(self, pt):
        return pt[0] >= 0 and pt[0] < self.size and pt[1] >= 0 and pt[1] < self.size

    def neighbors(self, pt, v):
        ns = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ns.append([(pt[0][0] + dx, pt[0][1] + dy)] + pt)
        return filter(lambda x: self.valid(x[0]) and not v[x[0][0]][x[0][1]] and self.board[x[0][0]][x[0][1]] is None, ns)
        
    def path(self, src, dst):
        if src == dst:
            return None
        visited = [[False for ix in range(self.size)] for jx in range(self.size)]
        visited[src[0]][src[1]] = True
        q = self.neighbors([src], visited)
        while len(q) > 0:
            pt = q[0]
            q = q[1:]
            visited[pt[0][0]][pt[0][1]] = True
            if pt[0] == dst:
                return list(reversed(pt))
            q.extend(self.neighbors(pt, visited))
        return None

    def check(self, pos):
        deleted = set() 
        factor = 1.0
        score = 0.0
        for delta in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            delta2 = mulvec(delta, -1)
            pos1 = pos[:]
            pos2 = pos[:]
            res = set()
            while True:
                pos1 = tuple(addvec(pos1, delta))
                pos2 = tuple(addvec(pos2, delta2))
                added = False
                if self.valid(pos1) and self.board[pos[0]][pos[1]] == self.board[pos1[0]][pos1[1]]:
                    added = True
                    res.add(pos1)
                else:
                    delta = (0, 0)
                if self.valid(pos2) and self.board[pos[0]][pos[1]] == self.board[pos2[0]][pos2[1]]:
                    added = True
                    res.add(pos2)
                else:
                    delta2 = (0, 0)
                if not added:
                    break
            if len(res) >= MIN_BEADS_FOR_REMOVAL - 1:
                score += SCORE_FACTOR * factor * (len(res) + 1) * (BONUS_FACTOR_1 ** max(len(res) - MIN_BEADS_FOR_REMOVAL, 0.0))
                factor *= BONUS_FACTOR_2
                deleted |= res
        if len(deleted) > 0:
            deleted.add(pos)
        return (deleted, int(score))

class Ui(object):
    def __init__(self, board):
        self.tick_cnt = 0
        self.margin = BOARD_MARGIN
        self.pad = CELL_PADDING
        self.board = board
        self.font = pygame.font.SysFont(SCORE_FONTFACE, SCORE_FONTSIZE)
        self.reset()

    def reset(self):
        self.selected = None
        self.recently_spawned = []
        self.deleted = []
        self.gameover = False

    def calc_bounds(self, frame):
        (x1, y1), (x2, y2) = frame
        width = x2 - x1
        height = y2 - y1
        cell_width = float(width) / self.board.size
        cell_height = float(height) / self.board.size
        return x1, y1, x2, y2, width, height, cell_width, cell_height

    def get_board_frame(self, frame):
        x1, y1, x2, y2, width, height, cell_width, cell_height = self.calc_bounds(frame)
        return ((self.margin, self.margin), (width - self.margin, height - self.margin))

    def draw(self, surface, frame):
        (x1, y1), (x2, y2) = frame
        pygame.draw.rect(surface, pygame.Color(BOARD_COLOR), [x1, y1, x2 - x1, y2 - y1], 0)
        overlay = self.font.render('Score: ' + str(self.board.score) + \
                (' ** GAME OVER **' if self.gameover else ''), True, pygame.Color(SCORE_COLOR))
        surface.blit(overlay, (self.margin, 0))
        board_frame = self.get_board_frame(frame)
        x1, y1, x2, y2, width, height, cell_width, cell_height = self.calc_bounds(board_frame)
        pygame.draw.rect(surface, pygame.Color(LINE_COLOR), [x1, y1, x2 - x1, y2 - y1], EXT_LINE_WIDTH)
        def bead(color, ix, jx, width):
            pygame.draw.ellipse(surface, color, \
                    [x1 + cell_width * ix + self.pad + 1, \
                    y1 + cell_height * jx + self.pad + 1, \
                    cell_width - 2 * self.pad + 1, \
                    cell_height - 2 * self.pad + 1], \
                    width)
        for ix in range(1, self.board.size):
            pygame.draw.line(surface, pygame.Color(LINE_COLOR), \
                    [x1, y1 + cell_height * ix], [x2, y1 + cell_height * ix], INT_LINE_WIDTH)
            pygame.draw.line(surface, pygame.Color(LINE_COLOR), \
            [x1 + cell_width * ix, y1], [x1 + cell_width * ix, y2], INT_LINE_WIDTH)
        for ix in range(self.board.size):
            for jx in range(self.board.size):
                if self.board.board[ix][jx] is None:
                    continue
                if (ix, jx) in self.deleted:
                    if ((self.tick_cnt / DESPAWN_F1) % DESPAWN_F2) == 0:
                        bead(self.board.board[ix][jx], ix, jx, 0)
                    else:
                        bead(pygame.Color(DESPAWN_COLOR), ix, jx, 0)
                elif (ix, jx) not in self.recently_spawned or ((self.tick_cnt / SPAWN_F1) % SPAWN_F2) == 0:
                    bead(self.board.board[ix][jx], ix, jx, 0)
                if self.selected == (ix, jx):
                    bead(pygame.Color(SEL_COLOR), ix, jx, ((self.tick_cnt / SEL_F1) % SEL_F2) + 1)
        pygame.display.flip()

    def get_coords(self, frame, pos):
        x, y = pos
        x1, y1, x2, y2, width, height, cell_width, cell_height = \
                self.calc_bounds(self.get_board_frame(frame))
        if x < x1 or x >= x2 or y < y1 or y >= y2:
            return None
        return (int((x - x1) / cell_width), int((y - y1) / cell_height))

    def tick(self):
        self.tick_cnt += 1

class Game(object):
    def __init__(self):
        pygame.init()
        self.width = WINDOW_WIDTH
        self.height = WINDOW_HEIGHT
        self.surface = pygame.display.set_mode((self.width, self.height))
        self.board = Board(BOARD_SIZE, map(lambda x: pygame.Color(x), \
                COLOR_LIST))
        self.ui = Ui(self.board)
        self.unhandler = LambdaHandler(lambda stream, evt: None)
        self.select_handler = LambdaHandler(lambda stream, evt: \
                self.handle_select(stream, evt), pygame.MOUSEBUTTONDOWN)
        self.move_handler = LambdaHandler(lambda stream, evt: \
                self.handle_move(stream, evt), GO)
        self.restart_handler = LambdaHandler(lambda stream, evt: \
                self.handle_init(stream, evt), pygame.MOUSEBUTTONDOWN)
        self.evt_handler = self.unhandler
        self.handler = CompositeHandler([ \
                DebugHandler(), \
                LambdaHandler(lambda stream, evt: self.handle_init(stream, evt), INIT), \
                LambdaHandler(lambda stream, evt: self.handle_ui_tick(stream, evt), TICK), \
                LambdaHandler(lambda stream, evt: self.handle_spawn(stream, evt), SPAWN), \
                LambdaHandler(lambda stream, evt: self.handle_unspawn(stream, evt), UNSPAWN), \
                LambdaHandler(lambda stream, evt: self.handle_despawn(stream, evt), DESPAWN), \
                LambdaHandler(lambda stream, evt: self.handle_undespawn(stream, evt), UNDESPAWN), \
                LambdaHandler(lambda stream, evt: self.evt_handler.handle(stream, evt)), \
                LambdaHandler(lambda stream, evt: self.ui.draw(self.surface, self.get_frame())), \
                QuitHandler() \
                ])
        EvtStream(self, [pygame.event.Event(INIT, {})])

    def get_frame(self):
        return ((0, 0), (self.width - 1, self.height - 1))

    def handle(self, stream, evt):
        self.handler.handle(stream, evt)

    def handle_init(self, stream, evt):
        self.board.erase()
        self.ui.reset()
        self.evt_handler = self.select_handler
        stream.schedule(pygame.event.Event(TICK, {}))
        stream.schedule(pygame.event.Event(SPAWN, {}))

    def handle_select(self, stream, evt):
        coords = self.ui.get_coords(self.get_frame(), evt.pos)
        if coords is not None and self.ui.selected and self.board.path(self.ui.selected, coords) is not None:
            self.evt_handler = self.move_handler
            stream.schedule(pygame.event.Event(GO, {'path': self.board.path(self.ui.selected, coords)}))
            self.ui.selected = None
        elif coords is not None:
            x, y = coords
            if self.board.board[x][y] is not None:
                self.ui.selected = (x, y)

    def handle_ui_tick(self, stream, evt):
        self.ui.tick()
        stream.schedule(pygame.event.Event(TICK, {}), TICK_RATE)

    def handle_spawn(self, stream, evt):
        self.ui.recently_spawned = self.board.spawn(SPAWN_BEADS)
        all_deleted = set()
        for x in self.ui.recently_spawned:
            deleted, score = self.board.check(x)
            all_deleted |= deleted
        if len(all_deleted) > 0:
            self.ui.deleted = all_deleted
            stream.schedule(pygame.event.Event(UNDESPAWN, {}), ANIMATE_DESPAWN_FOR)
            self.evt_handler = self.unhandler
        stream.schedule(pygame.event.Event(UNSPAWN, {}), ANIMATE_SPAWN_FOR)

    def handle_unspawn(self, stream, evt):
        if len(self.board.free()) == 0:
            self.ui.gameover = True
            self.evt_handler = self.restart_handler
        self.ui.recently_spawned = []

    def handle_despawn(self, stream, evt):
        stream.schedule(pygame.event.Event(UNDESPAWN, {}), ANIMATE_DESPAWN_FOR)

    def handle_undespawn(self, stream, evt):
        for x, y in self.ui.deleted:
            self.board.board[x][y] = None
        self.ui.deleted = []
        self.evt_handler = self.select_handler

    def handle_move(self, stream, evt):
        if len(evt.path) == 1:
            deleted, score = self.board.check(evt.path[0])
            if len(deleted) == 0:
                stream.schedule(pygame.event.Event(SPAWN, {}))
                self.evt_handler = self.select_handler
            else:
                self.board.score += score
                self.ui.deleted = deleted
                stream.schedule(pygame.event.Event(DESPAWN, {}))
                self.evt_handler = self.unhandler
        else:
            self.board.board[evt.path[0][0]][evt.path[0][1]], self.board.board[evt.path[1][0]][evt.path[1][1]] = \
                    self.board.board[evt.path[1][0]][evt.path[1][1]], self.board.board[evt.path[0][0]][evt.path[0][1]]
            stream.schedule(pygame.event.Event(GO, {'path': evt.path[1:]}), MOVE_DELAY)

Game()

