import pygame
import math
import random
from collections import deque
import heapq

# --- Configuration ---
TILE_SIZE = 32
MAP_WIDTH = 25
MAP_HEIGHT = 15
SCREEN_WIDTH = MAP_WIDTH * TILE_SIZE
SCREEN_HEIGHT = MAP_HEIGHT * TILE_SIZE + 60
BACKGROUND_COLOR = (0, 0, 0)
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]  # Up, Down, Left, Right

# --- Particle Class for 3D Effect ---
class Particle:
    def __init__(self, width, height):
        self.x = random.randint(0, width)
        self.y = random.randint(0, height)
        self.z = random.randint(1, 100)
        self.speed = random.uniform(0.5, 2)
        self.color_base = random.choice([
            (138, 43, 226),   # Purple
            (75, 0, 130),     # Indigo
            (255, 20, 147),   # Deep Pink
            (0, 191, 255),    # Deep Sky Blue
            (255, 105, 180)   # Hot Pink
        ])
        
    def update(self, dt):
        self.z -= self.speed * 50 * dt
        if self.z <= 0:
            self.z = 100
            self.y = random.randint(0, SCREEN_HEIGHT)
    
    def draw(self, screen):
        # Calculate size and brightness based on depth
        scale = (100 - self.z) / 100
        size = int(1 + scale * 4)
        brightness = int(100 + scale * 155)
        
        # Calculate screen position with perspective
        screen_x = int(self.x + (self.x - SCREEN_WIDTH / 2) * (100 - self.z) / 100)
        screen_y = int(self.y + (self.y - SCREEN_HEIGHT / 2) * (100 - self.z) / 100)
        
        if 0 <= screen_x < SCREEN_WIDTH and 0 <= screen_y < SCREEN_HEIGHT:
            color = tuple(min(255, int(c * brightness / 255)) for c in self.color_base)
            pygame.draw.circle(screen, color, (screen_x, screen_y), size)

# --- Entity (Original Logic) ---
class Entity:
    def __init__(self, x, y, image, speed):
        self.x = x
        self.y = y
        self.start_x = x
        self.start_y = y
        self.pos = pygame.Vector2(x * TILE_SIZE, y * TILE_SIZE)
        self.image = pygame.transform.scale(image, (TILE_SIZE - 2, TILE_SIZE - 2))
        self.speed = speed
        
    def get_grid_pos(self):
        return (int((self.pos.x + TILE_SIZE / 2) // TILE_SIZE),
                int((self.pos.y + TILE_SIZE / 2) // TILE_SIZE))

    def draw(self, screen):
        screen.blit(self.image, (self.pos.x + 1, self.pos.y + 1))

    def reset(self, x=None, y=None):
        if x is None: x = self.start_x
        if y is None: y = self.start_y
        self.x = x
        self.y = y
        self.pos = pygame.Vector2(x * TILE_SIZE, y * TILE_SIZE)

# --- Player (Original Logic) ---
class Player(Entity):
    def __init__(self, x, y, image):
        super().__init__(x, y, image, 160)
        self.last_move = pygame.Vector2(0, 0)

    def update(self, dt, maze):
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]: move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: move.x += 1

        if move.x != 0 or move.y != 0:
            self.last_move = move.normalize()
            if move.x != 0 and move.y != 0:
                move /= math.sqrt(2)

        next_pos = self.pos + move * self.speed * dt
        gx, gy = int((next_pos.x + TILE_SIZE / 2) // TILE_SIZE), int((next_pos.y + TILE_SIZE / 2) // TILE_SIZE)
        
        if 0 <= gx < MAP_WIDTH and 0 <= gy < MAP_HEIGHT and maze[gy][gx] != 1:
            self.pos = next_pos

# --- Base Ghost (Original Logic) ---
class Ghost(Entity):
    def __init__(self, x, y, image, speed, color):
        super().__init__(x, y, image, speed)
        self.color = color
        self.colorize_image()

    def colorize_image(self):
        """Tint the ghost image with its unique color"""
        self.image = self.image.copy()
        color_surface = pygame.Surface((TILE_SIZE - 2, TILE_SIZE - 2), pygame.SRCALPHA)
        color_surface.fill((*self.color, 128))
        self.image.blit(color_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def move_logic(self, dt, target_cell):
        """Unified movement helper to prevent ghosts from vibrating"""
        target_world = pygame.Vector2(target_cell[0] * TILE_SIZE, target_cell[1] * TILE_SIZE)
        dir_vec = target_world - self.pos
        if dir_vec.length() > 2:
            self.pos += dir_vec.normalize() * self.speed * dt
        else:
            self.pos = target_world

# --- RED GHOST: A* Pathfinding ---
class AStarGhost(Ghost):
    def __init__(self, x, y, image):
        super().__init__(x, y, image, 95, (255, 50, 50))

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def astar(self, start, target, maze):
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        while open_set:
            _, current = heapq.heappop(open_set)
            if current == target:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[-1] if path else start
            for d in DIRS:
                neighbor = (current[0] + d[0], current[1] + d[1])
                if 0 <= neighbor[0] < MAP_WIDTH and 0 <= neighbor[1] < MAP_HEIGHT and maze[neighbor[1]][neighbor[0]] != 1:
                    tg = g_score[current] + 1
                    if neighbor not in g_score or tg < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tg
                        f = tg + self.heuristic(neighbor, target)
                        heapq.heappush(open_set, (f, neighbor))
        return start

    def update_ai(self, dt, maze, player, other_ghosts):
        target = player.get_grid_pos()
        next_cell = self.astar(self.get_grid_pos(), target, maze)
        self.move_logic(dt, next_cell)

# --- ORANGE GHOST: Predicts (BFS) ---
class InterceptorGhost(Ghost):
    def __init__(self, x, y, image):
        super().__init__(x, y, image, 100, (255, 165, 0))

    def bfs(self, start, target, maze):
        q = deque([start])
        parent = {start: None}
        while q:
            c = q.popleft()
            if c == target: break
            for d in DIRS:
                nx, ny = c[0] + d[0], c[1] + d[1]
                if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT and maze[ny][nx] != 1 and (nx, ny) not in parent:
                    parent[(nx, ny)] = c
                    q.append((nx, ny))
        step = target if target in parent else start
        while step in parent and parent[step] is not None and parent[step] != start:
            step = parent[step]
        return step

    def update_ai(self, dt, maze, player, other_ghosts):
        px, py = player.get_grid_pos()
        target = (int(px + player.last_move.x * 4), int(py + player.last_move.y * 4))
        target = (max(0, min(MAP_WIDTH - 1, target[0])), max(0, min(MAP_HEIGHT - 1, target[1])))
        if maze[target[1]][target[0]] == 1: target = (px, py)
        next_cell = self.bfs(self.get_grid_pos(), target, maze)
        self.move_logic(dt, next_cell)

# --- GREEN GHOST: Flanker ---
class VectorGhost(Ghost):
    def __init__(self, x, y, image):
        super().__init__(x, y, image, 90, (50, 255, 50))

    def bfs(self, start, target, maze):
        q = deque([start])
        parent = {start: None}
        while q:
            c = q.popleft()
            if c == target: break
            for d in DIRS:
                nx, ny = c[0] + d[0], c[1] + d[1]
                if 0 <= nx < MAP_WIDTH and 0 <= ny < MAP_HEIGHT and maze[ny][nx] != 1 and (nx, ny) not in parent:
                    parent[(nx, ny)] = c
                    q.append((nx, ny))
        step = target if target in parent else start
        while step in parent and parent[step] is not None and parent[step] != start:
            step = parent[step]
        return step

    def update_ai(self, dt, maze, player, other_ghosts):
        p_pos = pygame.Vector2(player.get_grid_pos())
        others = [g for g in other_ghosts if g != self]
        if others:
            avg_g = pygame.Vector2(0, 0)
            for g in others: avg_g += pygame.Vector2(g.get_grid_pos())
            avg_g /= len(others)
            flank = p_pos + (p_pos - avg_g) * 0.5
            target = (int(max(0, min(MAP_WIDTH - 1, flank.x))), int(max(0, min(MAP_HEIGHT - 1, flank.y))))
        else:
            target = player.get_grid_pos()
        
        if maze[target[1]][target[0]] == 1: target = player.get_grid_pos()
        next_cell = self.bfs(self.get_grid_pos(), target, maze)
        self.move_logic(dt, next_cell)

# --- Button Class ---
class Button:
    def __init__(self, x, y, width, height, text, color, hover_color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        self.glow_intensity = 0

    def draw(self, screen, font):
        # Animated glow effect
        self.glow_intensity = (self.glow_intensity + 2) % 360
        glow_alpha = int(50 + 50 * math.sin(math.radians(self.glow_intensity)))
        
        # Draw glow layers
        if self.is_hovered:
            for i in range(3):
                glow_rect = self.rect.inflate(i * 6, i * 6)
                glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*self.hover_color, glow_alpha // (i + 1)), 
                               glow_surf.get_rect(), border_radius=15)
                screen.blit(glow_surf, glow_rect.topleft)
        
        # Draw main button
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        
        # Draw border with gradient effect
        border_color = tuple(min(255, c + 40) for c in color)
        pygame.draw.rect(screen, border_color, self.rect, 4, border_radius=12)
        
        # Draw text with shadow
        shadow_surf = font.render(self.text, True, (0, 0, 0))
        shadow_rect = shadow_surf.get_rect(center=(self.rect.centerx + 2, self.rect.centery + 2))
        screen.blit(shadow_surf, shadow_rect)
        
        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered:
                return True
        return False

# --- Game Loop ---
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Ghost Stalker")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.title_font = pygame.font.Font(None, 82)
        self.subtitle_font = pygame.font.Font(None, 42)
        self.create_images()
        self.state = "MENU"  # MENU, PLAYING, WIN, LOSE
        self.load_level()
        self.score = 0
        self.lives = 3
        
        # Create particles for background
        self.particles = [Particle(SCREEN_WIDTH, SCREEN_HEIGHT) for _ in range(150)]
        
        # Create buttons with unified color scheme
        button_width = 220
        button_height = 65
        button_x = SCREEN_WIDTH // 2 - button_width // 2
        button_color = (138, 43, 226)  # Purple
        button_hover = (168, 73, 255)  # Lighter purple
        
        self.play_button = Button(button_x, 260, button_width, button_height, 
                                   "PLAY", button_color, button_hover)
        self.exit_button = Button(button_x, 350, button_width, button_height, 
                                   "EXIT", button_color, button_hover)
        self.menu_button = Button(button_x, 380, button_width, button_height, 
                                   "MENU", button_color, button_hover)
        
        # Animation variables
        self.title_pulse = 0

    def create_images(self):
        # Original procedural Player
        self.player_img = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(self.player_img, (255, 255, 0), (TILE_SIZE // 2, TILE_SIZE // 2), TILE_SIZE // 2 - 2)
        pygame.draw.polygon(self.player_img, (0, 0, 0), [(TILE_SIZE // 2, TILE_SIZE // 2), (TILE_SIZE - 4, TILE_SIZE // 2 - 6), (TILE_SIZE - 4, TILE_SIZE // 2 + 6)])

        # Original procedural Ghost
        self.ghost_img = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(self.ghost_img, (255, 255, 255), (TILE_SIZE // 2, TILE_SIZE // 2 - 2), TILE_SIZE // 2 - 2)
        pygame.draw.rect(self.ghost_img, (255, 255, 255), (4, TILE_SIZE // 2 - 2, TILE_SIZE - 8, TILE_SIZE // 2))
        pygame.draw.circle(self.ghost_img, (255, 255, 255), (TILE_SIZE // 2 - 6, TILE_SIZE // 2 - 4), 4)
        pygame.draw.circle(self.ghost_img, (255, 255, 255), (TILE_SIZE // 2 + 6, TILE_SIZE // 2 - 4), 4)
        pygame.draw.circle(self.ghost_img, (0, 0, 100), (TILE_SIZE // 2 - 5, TILE_SIZE // 2 - 4), 2)
        pygame.draw.circle(self.ghost_img, (0, 0, 100), (TILE_SIZE // 2 + 7, TILE_SIZE // 2 - 4), 2)

        self.food_img = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.food_img, (255, 255, 255), (4, 4), 3)

    def load_level(self):
        # Redesigned connected maze (1=Wall, 2=Food, 0=Empty)
        self.original_maze = [
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            [1,2,2,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,2,2,1],
            [1,2,1,1,1,1,2,1,2,1,1,2,1,2,1,1,2,1,2,1,1,1,1,2,1],
            [1,2,1,2,2,2,2,2,2,2,2,2,0,2,2,2,2,2,2,2,2,2,1,2,1],
            [1,2,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1,2,1,1,2,1,2,1],
            [1,2,2,2,2,1,2,2,2,1,2,2,2,2,2,1,2,2,2,1,2,2,2,2,1],
            [1,2,1,2,1,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,1,2,1,2,1],
            [1,0,0,2,2,2,2,2,2,2,2,2,0,2,2,2,2,2,2,2,2,2,0,0,1],
            [1,2,1,2,1,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,1,2,1,2,1],
            [1,2,2,2,2,1,2,2,2,1,2,2,2,2,2,1,2,2,2,1,2,2,2,2,1],
            [1,2,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1,2,1,1,2,1,2,1],
            [1,2,1,2,2,2,2,2,2,2,2,2,0,2,2,2,2,2,2,2,2,2,1,2,1],
            [1,2,1,1,1,1,2,1,2,1,1,2,1,2,1,1,2,1,2,1,1,1,1,2,1],
            [1,2,2,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,2,2,1],
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
        ]
        self.reset_game()

    def reset_game(self):
        # Deep copy the original maze
        self.maze = [row[:] for row in self.original_maze]
        self.player = Player(12, 7, self.player_img)
        self.ghosts = [
            AStarGhost(1, 1, self.ghost_img),
            InterceptorGhost(23, 1, self.ghost_img),
            VectorGhost(1, 13, self.ghost_img)
        ]
        self.score = 0
        self.lives = 3
        self.total_food = sum(row.count(2) for row in self.maze)

    def draw_gradient_background(self):
        """Draw animated gradient background"""
        for y in range(SCREEN_HEIGHT):
            # Create color gradient from deep purple to dark blue
            ratio = y / SCREEN_HEIGHT
            r = int(25 + 40 * math.sin(ratio * math.pi + self.title_pulse / 50))
            g = int(0 + 30 * ratio)
            b = int(55 + 80 * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))

    def draw_menu(self):
        self.draw_gradient_background()
        
        # Draw particles
        for particle in self.particles:
            particle.draw(self.screen)
        
       
        # Main title
        title = self.title_font.render("GHOST STALKER", True, (255, 255, 0))
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 110))
        self.screen.blit(title, title_rect)
        
        # Subtitle with gradient color
        subtitle = self.subtitle_font.render("Pac-man", True, (255, 105, 180))
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 180))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Draw buttons
        self.play_button.draw(self.screen, self.font)
        self.exit_button.draw(self.screen, self.font)
        
        # Draw instructions with vibrant colors
        instructions = [
            ("Use WASD or Arrow Keys to move", (180, 220, 255)),
            ("Collect all dots to win!", (255, 200, 100)),
            ("Avoid the ghosts!", (255, 100, 150))
        ]
        y_pos = 460
        for text, color in instructions:
            instruction = self.font.render(text, True, color)
            text_rect = instruction.get_rect(center=(SCREEN_WIDTH // 2, y_pos))
            self.screen.blit(instruction, text_rect)
            y_pos += 35

    def draw_end_screen(self, won):
        self.draw_gradient_background()
        
        # Draw particles
        for particle in self.particles:
            particle.draw(self.screen)
        
        # Animated title pulse
        self.title_pulse += 1
        
        if won:
            # Win screen with celebration colors
            for i in range(2):
                glow_font = pygame.font.Font(None, 82 + i * 10)
                title_glow = glow_font.render("CONGRATULATIONS!", True, (255, 215, 0))
                title_glow.set_alpha(60 - i * 20)
                glow_rect = title_glow.get_rect(center=(SCREEN_WIDTH // 2, 110))
                self.screen.blit(title_glow, glow_rect)
            
            title = self.title_font.render("CONGRATULATIONS!", True, (255, 215, 0))
            subtitle = self.subtitle_font.render("You Won!", True, (0, 255, 150))
        else:
            
            title = self.title_font.render("GAME OVER!", True, (255, 50, 80))
            subtitle = self.subtitle_font.render("You Lost!", True, (255, 100, 120))
        
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 110))
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, subtitle_rect)
        
        # Draw final score with glow
        score_text = self.subtitle_font.render(f"Final Score: {self.score}", True, (255, 255, 100))
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, 290))
        self.screen.blit(score_text, score_rect)
        
        # Draw menu button
        self.menu_button.draw(self.screen, self.font)

    def check_win_condition(self):
        """Check if all food has been collected"""
        food_remaining = sum(row.count(2) for row in self.maze)
        return food_remaining == 0

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            
            # 1. ALWAYS update particles so the screen looks alive
            for particle in self.particles:
                particle.update(dt)
            
            # 2. EVENT HANDLING (Fixed logic)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # Check button clicks based on state
                if self.state == "MENU":
                    if self.play_button.handle_event(event):
                        self.reset_game()
                        self.state = "PLAYING"
                    if self.exit_button.handle_event(event):
                        running = False
                
                elif self.state in ["WIN", "LOSE"]:
                    if self.menu_button.handle_event(event):
                        self.state = "MENU"

            # 3. STATE RENDERING & LOGIC
            if self.state == "MENU":
                self.draw_menu()
            
            elif self.state == "PLAYING":
                self.player.update(dt, self.maze)
                px, py = self.player.get_grid_pos()
                
                if self.maze[py][px] == 2:
                    self.maze[py][px] = 0
                    self.score += 10

                if self.check_win_condition():
                    self.state = "WIN"

                for g in self.ghosts:
                    g.update_ai(dt, self.maze, self.player, self.ghosts)
                    if (self.player.pos - g.pos).length() < 20:
                        self.lives -= 1
                        self.player.reset()
                        [gh.reset() for gh in self.ghosts]
                        if self.lives <= 0:
                            self.state = "LOSE"

                # Draw the Gameplay
                self.screen.fill(BACKGROUND_COLOR)
                for y, row in enumerate(self.maze):
                    for x, cell in enumerate(row):
                        if cell == 1:
                            pygame.draw.rect(self.screen, (0, 0, 180), 
                                           (x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE), 2)
                        elif cell == 2:
                            self.screen.blit(self.food_img, (x*TILE_SIZE+12, y*TILE_SIZE+12))

                self.player.draw(self.screen)
                for g in self.ghosts:
                    g.draw(self.screen)
                
                # Draw HUD
                pygame.draw.rect(self.screen, (20,20,20), (0, SCREEN_HEIGHT-60, SCREEN_WIDTH, 60))
                txt = self.font.render(f"Score: {self.score}   Lives: {self.lives}  Red: A* Orange: Predict  Green: Flank", 
                                     True, (250,255,0))
                self.screen.blit(txt, (15, SCREEN_HEIGHT-40))
            
            elif self.state in ["WIN", "LOSE"]:
                # This ensures the end screen keeps drawing even if you aren't moving the mouse
                self.draw_end_screen(self.state == "WIN")

            # 4. FINALLY flip the display
            pygame.display.flip()
        
        pygame.quit()

if __name__ == "__main__":
    Game().run()