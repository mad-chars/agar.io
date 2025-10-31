# Pygame – Mini Agar.io (Starter didáctico)
# Autor: Prof. Luis (plantilla)
# Mecánica: círculo jugador que come comida y blobs pequeños, crece y se vuelve más lento.
# Mundo > pantalla con cámara centrada. Mouse para mover; SPACE = dash (–5% masa); R = reset; ESC = salir.

import pygame, sys, random, math

pygame.init()
WIDTH, HEIGHT = 960, 540            # tamaño de ventana
WORLD_W, WORLD_H = 3000, 2000       # tamaño del mundo
WINDOW = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Mini Agar.io – Starter")
CLOCK = pygame.time.Clock()
FPS = 60

def clamp(v, a, b): return max(a, min(v, b))

def draw_grid(surf, camx, camy):
    surf.fill((18,20,26))
    color = (28,32,40)
    step = 80
    sx = -((camx) % step)
    sy = -((camy) % step)
    for x in range(int(sx), WIDTH, step):
        pygame.draw.line(surf, color, (x, 0), (x, HEIGHT))
    for y in range(int(sy), HEIGHT, step):
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))

class Food:
    __slots__ = ("x","y","r","col","vx","vy")
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.r = random.randint(3, 6)
        self.col = random.choice([(255,173,72),(170,240,170),(150,200,255),(255,120,160),(255,220,120)])
        self.vx = 0.0
        self.vy = 0.0
    def draw(self, surf, camx, camy):
        pygame.draw.circle(surf, self.col, (int(self.x - camx), int(self.y - camy)), self.r)

class Blob:
    def __init__(self, x, y, mass, color):
        self.x, self.y = x, y
        self.mass = mass              # masa ~ área
        self.color = color
        self.vx = 0.0; self.vy = 0.0
        self.target = None
        self.alive = True
        self.split_time = 0  # tiempo para fusionar después de split
        self.parent = None   # referencia al blob original si es un split
        self.gradient = None  # cache para el gradiente

    @property
    def r(self):
        # radio ~ sqrt(masa) (crecimiento "realista" para área ~ masa)
        return max(6, int(math.sqrt(self.mass)))

    @property
    def speed(self):
        # más masa -> más lento
        base = 260.0
        return max(60.0, base / (1.0 + 0.04*self.r))

    def move_towards(self, tx, ty, dt):
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 1e-3:
            vx = (dx / dist) * self.speed
            vy = (dy / dist) * self.speed
        else:
            vx = vy = 0.0
        # inercia ligera
        self.vx = self.vx*0.85 + vx*0.15
        self.vy = self.vy*0.85 + vy*0.15
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = clamp(self.x, 0, WORLD_W)
        self.y = clamp(self.y, 0, WORLD_H)

    def create_gradient(self):
        if self.gradient is None:
            size = max(32, self.r * 2)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            center = (size//2, size//2)
            for r in range(size//2, -1, -1):
                alpha = min(255, int(255 * (1 - r/(size/2))))
                color = (*self.color, alpha)
                pygame.draw.circle(surf, color, center, r)
            self.gradient = surf
        return self.gradient

    def draw(self, surf, camx, camy, outline=True):
        x, y = int(self.x - camx), int(self.y - camy)
        
        # Dibujar gradiente
        gradient = self.create_gradient()
        pos = (x - gradient.get_width()//2, y - gradient.get_height()//2)
        surf.blit(gradient, pos, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Borde con efecto de brillo
        if outline:
            for width in range(3, 0, -1):
                alpha = 100 if width == 3 else 180 if width == 2 else 255
                color = (*self.color[:3], alpha)
                pygame.draw.circle(surf, color, (x, y), self.r + width - 1, 1)

class Game:
    def __init__(self):
        self.reset()

    def reset(self):
        random.seed()
        self.player = Blob(WORLD_W/2, WORLD_H/2, mass=600, color=(120,200,255))
        self.split_cells = []  # células divididas del jugador
        self.last_eject_time = 0  # cooldown para expulsión de masa
        self.bots = []
        for _ in range(18):
            bx = random.randint(50, WORLD_W-50)
            by = random.randint(50, WORLD_H-50)
            mass = random.randint(200, 900)
            col = random.choice([(255,140,120),(255,200,90),(170,240,170),(160,200,255),(255,120,180)])
            self.bots.append(Blob(bx, by, mass, col))
        self.food = [Food(random.randint(0,WORLD_W), random.randint(0,WORLD_H)) for _ in range(1200)]
        self.camx, self.camy = 0, 0
        self.time = 0.0
        self.state = "PLAY" # PLAY / GAMEOVER / WIN

    def spawn_food_ring(self, cx, cy, count=40, radius=120):
        for i in range(count):
            ang = (i / count) * math.tau
            fx = cx + math.cos(ang) * radius + random.uniform(-10,10)
            fy = cy + math.sin(ang) * radius + random.uniform(-10,10)
            fx = clamp(fx, 0, WORLD_W); fy = clamp(fy, 0, WORLD_H)
            self.food.append(Food(fx, fy))

    def update_player(self, dt):
        # Control con mouse: dirigir hacia el cursor
        mx, my = pygame.mouse.get_pos()
        tx = self.camx + mx
        ty = self.camy + my
        self.player.move_towards(tx, ty, dt)

    def update_bots(self, dt):
        # IA muy simple: huye de amenazas, persigue presas cercanas; si no, vaga
        for b in self.bots:
            if not b.alive: continue
            threat = None; prey = None; mind = 1e9
            for other in self.bots + [self.player]:
                if other is b or not other.alive: continue
                d = abs(other.x - b.x) + abs(other.y - b.y)
                if other.mass > b.mass*1.35 and d < 480:
                    if d < mind: mind = d; threat = other
                elif other.mass*1.35 < b.mass and d < 420:
                    prey = other
            if threat is not None:
                tx = b.x - (threat.x - b.x) # huir (vector opuesto)
                ty = b.y - (threat.y - b.y)
            elif prey is not None:
                tx, ty = prey.x, prey.y
            else:
                if b.target is None or random.random() < 0.005:
                    b.target = (random.randint(0,WORLD_W), random.randint(0,WORLD_H))
                tx, ty = b.target
            b.move_towards(tx, ty, dt)

    def eat_collisions(self):
        # player come food
        pr = self.player.r
        px, py = self.player.x, self.player.y
        remain_food = []
        for f in self.food:
            if abs(f.x - px) <= pr+12 and abs(f.y - py) < pr+12:
                if (f.x - px)**2 + (f.y - py)**2 < (pr + f.r)**2:
                    self.player.mass += f.r * 0.9
                else:
                    remain_food.append(f)
            else:
                remain_food.append(f)
        self.food = remain_food

        # player come bots pequeños
        for b in self.bots:
            if not b.alive: continue
            # primero comprobar que el jugador es claramente más masivo (evita comparaciones engañosas)
            if self.player.mass <= b.mass * 1.10:
                continue
            dist2 = (b.x - px)**2 + (b.y - py)**2
            # comprobar que el radio visible del jugador es mayor y que están lo bastante cerca
            if self.player.r > b.r * 1.05 and dist2 < (self.player.r - b.r*0.6)**2:
                self.player.mass += b.mass * 0.80
                b.alive = False
                self.spawn_food_ring(b.x, b.y, count=50, radius=140)  # suelta comida al morir

        # bots comen player (si son muy grandes y tocan)
        for b in self.bots:
            if not b.alive: continue
            if b.mass > self.player.mass * 1.20:
                dist2 = (b.x - px)**2 + (b.y - py)**2
                if b.r > self.player.r * 1.05 and dist2 < (b.r - self.player.r*0.9)**2:
                    self.state = "GAMEOVER"

    def update_camera(self, dt):
        # cámara con lerp suave
        target_x = self.player.x - WIDTH/2
        target_y = self.player.y - HEIGHT/2
        self.camx += (target_x - self.camx) * 0.08
        self.camy += (target_y - self.camy) * 0.08
        self.camx = clamp(self.camx, 0, WORLD_W - WIDTH)
        self.camy = clamp(self.camy, 0, WORLD_H - HEIGHT)

    def dash(self):
        # dash: pierde 5% masa y gana impulso hacia el ratón
        loss = self.player.mass * 0.05
        if self.player.mass - loss < 200:
            return
        self.player.mass -= loss
        mx, my = pygame.mouse.get_pos()
        mx, my = self.camx + mx, self.camy + my
        dx, dy = mx - self.player.x, my - self.player.y
        dist = math.hypot(dx, dy) + 1e-5
        self.player.vx += (dx/dist) * 900
        self.player.vy += (dy/dist) * 900
        
    def split_player(self):
        # División del jugador en 2 células
        if len(self.split_cells) >= 1 or self.player.mass < 400:
            return
            
        # Crear nueva célula con la mitad de la masa
        split_mass = self.player.mass / 2
        self.player.mass = split_mass
        
        # Calcular dirección hacia el ratón
        mx, my = pygame.mouse.get_pos()
        mx, my = self.camx + mx, self.camy + my
        dx, dy = mx - self.player.x, my - self.player.y
        dist = math.hypot(dx, dy) + 1e-5
        
        # Crear nueva célula y darle impulso
        new_cell = Blob(self.player.x, self.player.y, split_mass, self.player.color)
        # Aumentar velocidad inicial y separar un poco del jugador
        new_cell.x += (dx/dist) * (self.player.r + 5)  # Separar un poco para evitar superposición
        new_cell.y += (dy/dist) * (self.player.r + 5)
        new_cell.vx = (dx/dist) * 1500  # Velocidad aumentada
        new_cell.vy = (dy/dist) * 1500
        new_cell.parent = self.player
        new_cell.split_time = self.time + 6.0  # fusionar después de 6 segundos
        self.split_cells.append(new_cell)
        
    def eject_mass(self):
        # Expulsar masa como comida
        current_time = self.time
        if current_time - self.last_eject_time < 0.5:  # cooldown de 0.5 segundos
            return
            
        if self.player.mass < 200:  # masa mínima para expulsar
            return
            
        # Calcular dirección hacia el ratón
        mx, my = pygame.mouse.get_pos()
        mx, my = self.camx + mx, self.camy + my
        dx, dy = mx - self.player.x, my - self.player.y
        dist = math.hypot(dx, dy) + 1e-5
        
        # Crear comida en la dirección del ratón
        ejected_mass = min(50, self.player.mass * 0.1)
        self.player.mass -= ejected_mass
        
        # Posición inicial ligeramente adelante del jugador
        food_x = self.player.x + (dx/dist) * (self.player.r + 10)
        food_y = self.player.y + (dy/dist) * (self.player.r + 10)
        
        # Crear comida con velocidad
        food = Food(food_x, food_y)
        food.vx = (dx/dist) * 800  # añadimos vx, vy dinámicamente
        food.vy = (dy/dist) * 800
        self.food.append(food)
        
        self.last_eject_time = current_time

    def update(self, dt):
        if self.state != "PLAY":
            return
        self.time += dt
        self.update_player(dt)
        self.update_bots(dt)
        
        # Actualizar células divididas
        for cell in self.split_cells[:]:
            cell.move_towards(self.player.x, self.player.y, dt)
            # Fusionar si ha pasado el tiempo
            if self.time >= cell.split_time:
                self.player.mass += cell.mass
                self.split_cells.remove(cell)
                
        # Actualizar comida expulsada
        for f in self.food:
            if hasattr(f, 'vx'):  # solo comida expulsada tiene velocidad
                f.x += f.vx * dt
                f.y += f.vy * dt
                f.vx *= 0.95  # fricción
                f.vy *= 0.95
                f.x = clamp(f.x, 0, WORLD_W)
                f.y = clamp(f.y, 0, WORLD_H)
                
        self.eat_collisions()
        # respawn de comida
        if len(self.food) < 1000:
            for _ in range(50):
                self.food.append(Food(random.randint(0, WORLD_W), random.randint(0, WORLD_H)))
        # ganar: todos los bots muertos
        if all(not b.alive for b in self.bots):
            self.state = "WIN"
        self.update_camera(dt)

    def draw(self):
        draw_grid(WINDOW, self.camx, self.camy)

        # comida
        for f in self.food:
            fx, fy = int(f.x - self.camx), int(f.y - self.camy)
            if -10 <= fx <= WIDTH+10 and -10 <= fy <= HEIGHT+10:
                f.draw(WINDOW, self.camx, self.camy)

        # bots
        for b in self.bots:
            if b.alive:
                b.draw(WINDOW, self.camx, self.camy)

        # células divididas del jugador
        for cell in self.split_cells:
            cell.draw(WINDOW, self.camx, self.camy)

        # jugador al final
        self.player.draw(WINDOW, self.camx, self.camy)

        # HUD
        pygame.draw.rect(WINDOW, (25,28,36), (10, 10, 300, 70), border_radius=8)
        font = pygame.font.SysFont(None, 24)
        WINDOW.blit(font.render(f"Masa: {int(self.player.mass)}", True, (235,235,245)), (20, 18))
        WINDOW.blit(font.render("Mouse = move | SPACE = dash (−5% masa)", True, (200,220,255)), (20, 44))

        if self.state == "GAMEOVER":
            t = pygame.font.SysFont(None, 48).render("GAME OVER", True, (255,120,120))
            r = t.get_rect(center=(WIDTH//2, HEIGHT//2-10))
            WINDOW.blit(t, r)
            s = pygame.font.SysFont(None, 28).render("[R] reiniciar — [ESC] salir", True, (235,235,245))
            WINDOW.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 + 26))

        if self.state == "WIN":
            t = pygame.font.SysFont(None, 48).render("¡GANASTE!", True, (180,255,180))
            r = t.get_rect(center=(WIDTH//2, HEIGHT//2-10))
            WINDOW.blit(t, r)
            s = pygame.font.SysFont(None, 28).render("Todos los bots derrotados — [R] reiniciar", True, (235,235,245))
            WINDOW.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 + 26))

    def run(self):
        running = True
        while running:
            dt = CLOCK.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT: running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: running = False
                    elif e.key == pygame.K_r: self.reset()
                    elif e.key == pygame.K_SPACE and self.state == "PLAY": self.dash()
                    elif e.key == pygame.K_q and self.state == "PLAY": self.split_player()
                    elif e.key == pygame.K_e and self.state == "PLAY": self.eject_mass()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()

def main():
    Game().run()

if __name__ == "__main__":
    main()
