import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import random, math, os, time

# ---------------- Settings ----------------
SCREEN_W, SCREEN_H = 640, 840
FPS = 60

LANE_COUNT = 3
PLAYER_SIZE = 90
ITEM_SIZE = 44
LANE_W = SCREEN_W // LANE_COUNT
PLAYER_Y = SCREEN_H - PLAYER_SIZE - 40
BG_COLOR = (18/255, 20/255, 35/255, 1.0)

# Gameplay
BASE_SPEED = 3.2
POWERUP_DURATION_MS = {"magnet": 6000, "double": 5000, "shield": 4000}
COIN_RATE = 1/70.0
BOMB_RATE = 1/160.0
SHIELD_RATE = 1/900.0
MAGNET_RATE = 1/1200.0
DOUBLE_RATE = 1/1400.0
LANE_SHIFT_INTERVAL = 480
LANE_SHIFT_DURATION = 48
MAX_SHIFT = 1

# Sounds (optional)
def try_load_sound(name):
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if os.path.exists(name):
            return pygame.mixer.Sound(name)
    except Exception:
        return None
    return None

SND_PICKUP = try_load_sound("pickup.wav")
SND_EXPLODE = try_load_sound("explosion.wav")
SND_POWER = try_load_sound("powerup.wav")

def psnd(snd, vol=0.6):
    if snd:
        try:
            snd.set_volume(vol)
            snd.play()
        except Exception:
            pass

# ---------------- Utility ----------------
def lane_x(l):
    return l * LANE_W + (LANE_W - PLAYER_SIZE) // 2

def ease_cosine(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))

# ---------------- OpenGL 2D helpers ----------------
def gl_init_2d(w, h):
    glViewport(0,0,w,h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0, w, h, 0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(*BG_COLOR)

def gl_rect(x,y,w,h,color):
    r,g,b,a = color
    glColor4f(r,g,b,a)
    glBegin(GL_QUADS)
    glVertex2f(x, y)
    glVertex2f(x+w, y)
    glVertex2f(x+w, y+h)
    glVertex2f(x, y+h)
    glEnd()

def gl_circle(x, y, radius, color, segments=24):
    r,g,b,a = color
    glColor4f(r,g,b,a)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(x,y)
    for i in range(segments+1):
        ang = i/segments * math.tau
        glVertex2f(x + math.cos(ang)*radius, y + math.sin(ang)*radius)
    glEnd()

def gl_ring_arc(cx, cy, radius, thickness, start_frac, frac, color, segments=48):
    r,g,b,a = color
    glColor4f(r,g,b,a)
    inner = radius - thickness/2
    outer = radius + thickness/2
    start_ang = start_frac * 2*math.pi
    end_ang = (start_frac + frac) * 2*math.pi
    steps = max(4, int(abs(frac)*segments))
    glBegin(GL_TRIANGLE_STRIP)
    for i in range(steps+1):
        t = i/steps
        ang = start_ang + t*(end_ang - start_ang)
        glVertex2f(cx + math.cos(ang)*outer, cy + math.sin(ang)*outer)
        glVertex2f(cx + math.cos(ang)*inner, cy + math.sin(ang)*inner)
    glEnd()

# ---------------- Game objects ----------------
class Player:
    def __init__(self):
        self.lane = LANE_COUNT//2
        self.x = float(lane_x(self.lane))
        self.y = PLAYER_Y
        self.w = PLAYER_SIZE
        self.h = PLAYER_SIZE
        self.magnet_until = 0
        self.doubler_until = 0
        self.shield_until = 0
        self.combo = 0
        self.score_multiplier = 1.0
        self.target_x = self.x  # For smooth sliding

    def update(self, dt, lane_offset):
        # update target_x based on lane
        self.target_x = lane_x(self.lane) + lane_offset * LANE_W
        # smooth slide using easing
        t = 0.2  # slide speed factor
        self.x += (self.target_x - self.x) * t

    def draw(self, lane_offset, now):
        gl_rect(self.x+8, self.y+self.h-10, self.w, 12, (0,0,0,0.18))
        gl_rect(self.x, self.y, self.w, self.h, (60/255,200/255,80/255,1.0))
        if now < self.shield_until:
            pulse = 4 + 2*math.sin(now/180)
            gl_ring_arc(self.x+self.w/2, self.y+self.h/2, self.w*0.7, pulse, 0.0, 1.0, (80/255,180/255,255/255,0.9))

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

class Item:
    def __init__(self, lane, type_):
        self.lane = lane
        self.type = type_
        self.base_x = lane * LANE_W + (LANE_W - ITEM_SIZE)//2
        self.x = float(self.base_x)
        self.y = -ITEM_SIZE - random.uniform(0, 80)
        self.w = ITEM_SIZE
        self.h = ITEM_SIZE
        self.speed = BASE_SPEED
        self.spawn_ms = pygame.time.get_ticks()

    def update(self, dt):
        self.y += self.speed

    def draw(self, lane_offset):
        vx = self.x + lane_offset*LANE_W
        cy = int(self.y + self.h/2)
        cx = int(vx + self.w/2)
        if self.type == "coin":
            gl_circle(cx, cy, self.w/2, (255/255,223/255,60/255,1.0))
        elif self.type == "bomb":
            gl_circle(cx, cy, self.w/2, (180/255,30/255,30/255,1.0))
        elif self.type == "shield":
            gl_circle(cx, cy, self.w/2, (80/255,180/255,255/255,1.0))
        elif self.type == "magnet":
            gl_rect(vx, self.y, self.w, self.h, (160/255,80/255,220/255,1.0))
        elif self.type == "double":
            gl_rect(vx, self.y, self.w, self.h, (255/255,180/255,60/255,1.0))

    def visual_rect(self, lane_offset):
        return pygame.Rect(int(self.x + lane_offset*LANE_W), int(self.y), self.w, self.h)

# ---------------- LaneShift ----------------
class LaneShift:
    def __init__(self):
        self.offset = 0.0
        self.target = 0.0
        self.timer = LANE_SHIFT_DURATION + 1

    def start(self):
        self.target = random.choice([-MAX_SHIFT, MAX_SHIFT])
        self.timer = 0
        psnd(SND_POWER, 0.4)

    def update(self):
        if self.timer <= LANE_SHIFT_DURATION:
            p = (self.timer+1) / LANE_SHIFT_DURATION
            self.offset = self.target * ease_cosine(p)
            self.timer += 1
            if self.timer > LANE_SHIFT_DURATION:
                self.target = 0
                self.timer = LANE_SHIFT_DURATION+1
        else:
            self.offset *= 0.94
            if abs(self.offset) < 0.002:
                self.offset = 0.0

# ---------------- Pygame text over GL ----------------
def draw_text_pygame(glscreen, text, pos, color=(255,255,255), size=18):
    font = pygame.font.SysFont("consolas", size)
    surf = font.render(text, True, color)
    tex = pygame.image.tostring(surf, "RGBA", True)
    w,h = surf.get_size()
    texid = glGenTextures(1)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, tex)
    x,y = pos
    glColor4f(1,1,1,1)
    glBegin(GL_QUADS)
    glTexCoord2f(0,0); glVertex2f(x,y)
    glTexCoord2f(1,0); glVertex2f(x+w,y)
    glTexCoord2f(1,1); glVertex2f(x+w,y+h)
    glTexCoord2f(0,1); glVertex2f(x,y+h)
    glEnd()
    glDeleteTextures([texid])
    glDisable(GL_TEXTURE_2D)

# ---------------- Main Game ----------------
def main():
    pygame.init()
    screen_mode = DOUBLEBUF | OPENGL
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), screen_mode)
    pygame.display.set_caption("OpenGL Lane Collector - Smooth Slide")
    gl_init_2d(SCREEN_W, SCREEN_H)
    clock = pygame.time.Clock()

    player = Player()
    items = []
    lane_shift = LaneShift()
    score = 0
    lives = 3
    game_over = False

    while True:
        dt = clock.tick(FPS)
        now = pygame.time.get_ticks()
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit(); return
            if ev.type == KEYDOWN:
                if ev.key == K_LEFT and not game_over and player.lane > 0:
                    player.lane -= 1
                if ev.key == K_RIGHT and not game_over and player.lane < LANE_COUNT-1:
                    player.lane += 1
                if ev.key == K_SPACE and game_over:
                    score = 0; lives=3; items.clear(); game_over=False
                if ev.key == K_ESCAPE:
                    pygame.quit(); return

        # --- Game logic here (spawning items, powerups, collisions) ---
        lane_shift.update()
        player.update(dt, lane_shift.offset)

        # ---------- Render ----------
        glClear(GL_COLOR_BUFFER_BIT)
        # lane lines
        for i in range(1, LANE_COUNT):
            gl_rect(i*LANE_W + int(lane_shift.offset*LANE_W), 0, 2, SCREEN_H, (0.24,0.24,0.27,1.0))
        # draw items
        for it in items:
            it.draw(lane_shift.offset)
        # draw player
        player.draw(lane_shift.offset, pygame.time.get_ticks())
        # HUD
        draw_text_pygame(screen, f"Score: {score}", (18,18), color=(230,230,210), size=22)
        draw_text_pygame(screen, f"Lives: {lives}", (18,48), color=(250,200,200), size=20)
        pygame.display.flip()

if __name__ == "__main__":
    main()
