import pgzrun, pygame, pytmx
import pgzero.music as music
from pgzero.loaders import sounds
import os, time

##############################################################
# CONSTANTS

WIDTH = 320
HEIGHT = 240
TILE_SIZE = 16
MOVEMENT_COOLDOWN = 0.15

DEBUG_MODE_ON = False

LEVEL_SEQUENCE = [
 "level-1", "level-2",
]


##############################################################
# OPTIMIZED ANIMATION SYSTEM

class AnimationManager:
 """Lightweight animation manager optimized for Pi Zero"""
 _sprite_cache = {}  # Global cache for all spritesheets

 def __init__(self, spritesheet_path, tile_size=16, animations=None):
  self.tile_size = tile_size
  self.animations = animations or {}

  # Simple animation state
  self.current_anim = None
  self.frame_idx = 0
  self.last_update = 0
  self.finished = False

  # Use cached spritesheet or load new one
  if spritesheet_path not in AnimationManager._sprite_cache:
   AnimationManager._sprite_cache[spritesheet_path] = pygame.image.load(spritesheet_path)
  self.spritesheet = AnimationManager._sprite_cache[spritesheet_path]

  # Pre-cut frames (only when needed)
  self.frames = {}

 def _get_frame(self, anim_name, frame_idx):
  """Get frame surface, cutting it on demand and caching"""
  cache_key = f"{anim_name}_{frame_idx}"
  if cache_key not in self.frames:
   row, col = self.animations[anim_name]["frames"][frame_idx]
   x, y = col * self.tile_size, row * self.tile_size
   self.frames[cache_key] = self.spritesheet.subsurface(x, y, self.tile_size, self.tile_size)
  return self.frames[cache_key]

 def play(self, anim_name, reset=True):
  """Start animation"""
  if anim_name not in self.animations:
   return
  if self.current_anim != anim_name or reset:
   self.current_anim = anim_name
   self.frame_idx = 0
   self.last_update = time.time()
   self.finished = False

 def update(self):
  """Update animation - simplified logic"""
  if not self.current_anim or self.finished:
   return

  anim = self.animations[self.current_anim]
  now = time.time()

  if now - self.last_update >= anim["duration"]:
   self.frame_idx += 1
   self.last_update = now

   if self.frame_idx >= len(anim["frames"]):
    if anim.get("loop", True):
     self.frame_idx = 0
    else:
     self.frame_idx = len(anim["frames"]) - 1
     self.finished = True

 def get_frame(self):
  """Get current frame surface"""
  if not self.current_anim:
   return None

  # Ensure we don't go out of bounds, especially for finished animations
  frame_count = len(self.animations[self.current_anim]["frames"])
  safe_frame_idx = min(self.frame_idx, frame_count - 1)

  return self._get_frame(self.current_anim, safe_frame_idx)


##############################################################
# OPTIMIZED PLAYER CLASS

class Player:
 # Class-level animation definitions to reduce memory
 ANIMATIONS = {
  "idle_right": {"frames": [(0, 0), (0, 1), (0, 2)], "duration": 0.6, "loop": True},
  "idle_left": {"frames": [(1, 0), (1, 1), (1, 2)], "duration": 0.6, "loop": True},
  "walk_right": {"frames": [(2, 0), (2, 1), (2, 2), (2, 3)], "duration": 0.6, "loop": True},
  "walk_left": {"frames": [(3, 0), (3, 1), (3, 2), (3, 3)], "duration": 0.6, "loop": True},
  "hurt_right": {"frames": [(4, 1), (4, 2), (4, 3), (4, 4), (4, 5)], "duration": 0.6, "loop": False},
  "hurt_left": {"frames": [(5, 1), (5, 2), (5, 3), (5, 4), (5, 5)], "duration": 0.6, "loop": False},
  "die_right": {"frames": [(6, 1), (6, 2), (6, 3)], "duration": 0.6, "loop": False},
  "die_left": {"frames": [(7, 1), (7, 2), (7, 3)], "duration": 0.6, "loop": False},
 }

 SWORD_ANIMATIONS = {
  "attack_left": {"frames": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)], "duration": 0.1, "loop": False},
  "attack_right": {"frames": [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)], "duration": 0.1, "loop": False},
 }

 def __init__(self, x, y):
  # Grid-snap position
  self.x = (x // TILE_SIZE) * TILE_SIZE
  self.y = (y // TILE_SIZE) * TILE_SIZE

  # Basic state
  self.facing = "right"
  self.last_move = 0

  # Combat state - simplified
  self.health = 3
  self.max_health = 3

  # State flags with timers
  self.state = "idle"  # idle, moving, attacking, hurt, dying
  self.state_timer = 0
  self.invincible_timer = 0

  # Animation managers
  self.anim = AnimationManager("images/player.png", TILE_SIZE, self.ANIMATIONS)
  self.sword_anim = AnimationManager("images/weapons_animated.png", 48, self.SWORD_ANIMATIONS)
  self.anim.play("idle_right")

 def update(self):
  """Simplified update logic"""
  now = time.time()

  # Update state timers
  if self.invincible_timer > 0:
   self.invincible_timer = max(0, self.invincible_timer - (now - getattr(self, '_last_update', now)))

  # State machine
  if self.state == "dying":
   # Keep updating animation until it finishes, then stop
   if not self.anim.finished:
    self.anim.update()
    print(f"Death animation frame: {self.anim.frame_idx}, finished: {self.anim.finished}")  # Debug
   else:
    print("Death animation finished, staying on last frame")  # Debug
   # Stay in dying state but don't update animation anymore (keeps last frame)
  elif self.state == "hurt":
   if now - self.state_timer >= 1.0:
    self.state = "idle"
   self.anim.update()
  elif self.state == "attacking":
   if now - self.state_timer >= 0.5:
    self.state = "idle"
   self.sword_anim.update()
   self.anim.update()
  else:
   # Update animation based on state for idle/moving
   if self.state in ["idle", "moving"]:
    anim_name = f"{'walk' if self.state == 'moving' else 'idle'}_{self.facing}"
    self.anim.play(anim_name, False)
   self.anim.update()

  self._last_update = now

 def move(self, dx, dy, level_width, level_height, current_time):
  """Simplified movement"""
  if self.state in ["attacking", "hurt", "dying"] or not self._can_move(current_time):
   return False

  # Update facing
  if dx > 0:
   self.facing = "right"
  elif dx < 0:
   self.facing = "left"

  # Calculate new position
  new_x = self.x + (dx * TILE_SIZE)
  new_y = self.y + (dy * TILE_SIZE)

  # Boundary check
  if 0 <= new_x <= level_width - TILE_SIZE and 0 <= new_y <= level_height - TILE_SIZE:
   self.x, self.y = new_x, new_y
   self.last_move = current_time
   self.state = "moving"
   return True
  return False

 def _can_move(self, current_time):
  return current_time - self.last_move >= MOVEMENT_COOLDOWN

 def start_attack(self):
  """Start attack"""
  if self.state in ["attacking", "hurt", "dying"]:
   return False

  self.state = "attacking"
  self.state_timer = time.time()
  sounds.sword_2.play()
  self.sword_anim.play(f"attack_{self.facing}", True)
  return True

 def take_damage(self, damage=1):
  """Take damage"""
  if self.invincible_timer > 0 or self.state in ["hurt", "dying"]:
   return False

  self.health -= damage
  if self.health <= 0:
   self._start_death()
  else:
   self._start_hurt()
  return True

 def _start_hurt(self):
  """Start hurt state"""
  self.state = "hurt"
  self.state_timer = time.time()
  self.invincible_timer = 1.8
  sounds.hit_7.play()
  self.anim.play(f"hurt_{self.facing}", True)

 def _start_death(self):
  """Start death"""
  print("Player starting death sequence...")  # Debug
  self.state = "dying"
  self.state_timer = time.time()
  music.stop()
  sounds.game_over.play()
  self.anim.play(f"die_{self.facing}", True)
  print(f"Death animation started: die_{self.facing}")  # Debug

 def get_rect(self):
  return pygame.Rect(self.x, self.y, TILE_SIZE, TILE_SIZE)

 def is_dead(self):
  return self.health <= 0

 def draw(self, screen, camera_x, camera_y):
  """Optimized drawing"""
  screen_x, screen_y = self.x - camera_x, self.y - camera_y

  # Flashing effect during invincibility (but NOT when dying)
  if self.invincible_timer > 0 and self.state not in ["hurt", "dying"]:
   if int(time.time() * 10) % 2:  # Flash every 0.1 seconds
    return

  # Draw player (always draw when dying to show final frame)
  frame = self.anim.get_frame()
  if frame:
   screen.blit(frame, (screen_x, screen_y))
   if self.state == "dying":
    print(f"Drawing dying player at frame {self.anim.frame_idx}")  # Debug
  else:
   if self.state == "dying":
    print("ERROR: No frame to draw for dying player!")  # Debug

  # Draw sword during attack (but not when dying)
  if self.state == "attacking" and self.state != "dying":
   sword_frame = self.sword_anim.get_frame()
   if sword_frame:
    screen.blit(sword_frame, (screen_x - 16, screen_y - 16))


##############################################################
# OPTIMIZED ENEMY CLASS

class Enemy:
 # Shared animation definitions
 ANIMATIONS = {
  "idle_right": {"frames": [(0, 0), (0, 1)], "duration": 0.6, "loop": True},
  "idle_left": {"frames": [(1, 0), (1, 1)], "duration": 0.6, "loop": True},
  "walk_right": {"frames": [(2, 0), (2, 1), (2, 2)], "duration": 0.4, "loop": True},
  "walk_left": {"frames": [(3, 0), (3, 1), (3, 2)], "duration": 0.4, "loop": True},
  "hurt_right": {"frames": [(4, 0), (4, 1), (4, 2), (4, 3)], "duration": 0.2, "loop": False},
  "hurt_left": {"frames": [(5, 0), (5, 1), (5, 2), (5, 3)], "duration": 0.2, "loop": False},
 }

 def __init__(self, x, y, enemy_type="rat", movement="horizontal", blocks=2):
  # Grid-snap position
  self.x = (x // TILE_SIZE) * TILE_SIZE
  self.y = (y // TILE_SIZE) * TILE_SIZE
  self.start_x, self.start_y = self.x, self.y

  # Movement
  self.facing = "right"
  self.movement_type = movement
  self.blocks = blocks
  self.blocks_moved = 0
  self.last_move = 0
  self.move_cooldown = 0.3

  # State machine
  self.state = "moving"  # moving, idle, hurt, dying
  self.state_timer = 0

  # Animation
  spritesheet_path = f"images/enemy_{enemy_type}.png"
  self.anim = AnimationManager(spritesheet_path, TILE_SIZE, self.ANIMATIONS)
  self.anim.play("walk_right")

 def update(self, level_loader=None):
  """Simplified enemy AI"""
  now = time.time()

  if self.state == "dying":
   if now - self.state_timer >= 1.0:
    return  # Mark for removal
  elif self.state == "hurt":
   if now - self.state_timer >= 0.8:
    self.state = "moving"
    self.anim.play(f"walk_{self.facing}")
  elif self.state == "moving":
   self._update_movement(now, level_loader)
  elif self.state == "idle":
   if now - self.state_timer >= 3.0:
    self.facing = "left" if self.facing == "right" else "right"
    self.state = "moving"
    self.blocks_moved = 0
    self.anim.play(f"walk_{self.facing}")

  self.anim.update()

 def _update_movement(self, now, level_loader):
  """Handle movement logic"""
  if now - self.last_move < self.move_cooldown:
   return

  # Calculate movement direction
  dx = dy = 0
  if self.movement_type == "horizontal":
   dx = 1 if self.facing == "right" else -1
  else:  # vertical
   dy = 1 if self.facing == "right" else -1

  # Try to move
  new_x = self.x + (dx * TILE_SIZE)
  new_y = self.y + (dy * TILE_SIZE)

  can_move = True
  if level_loader:
   can_move = not level_loader.is_position_blocked(new_x, new_y)

  if can_move:
   self.x, self.y = new_x, new_y
   self.blocks_moved += 1
   self.last_move = now

   if self.blocks_moved >= self.blocks:
    self.state = "idle"
    self.state_timer = now
    self.anim.play(f"idle_{self.facing}")
  else:
   # Hit wall, go idle and turn around
   self.state = "idle"
   self.state_timer = now
   self.anim.play(f"idle_{self.facing}")

 def take_damage(self):
  """Take damage"""
  if self.state in ["hurt", "dying"]:
   return False

  self.state = "hurt"
  self.state_timer = time.time()
  self.anim.play(f"hurt_{self.facing}", True)
  return True

 def start_death(self):
  """Start death"""
  self.state = "dying"
  self.state_timer = time.time()
  sounds.hit_7.play()

 def should_be_removed(self):
  """Check if should be removed"""
  return (self.state == "dying" and
          time.time() - self.state_timer >= 1.0)

 def get_rect(self):
  return pygame.Rect(self.x, self.y, TILE_SIZE, TILE_SIZE)

 def draw(self, screen, camera_x, camera_y):
  """Draw enemy with death flashing"""
  screen_x, screen_y = self.x - camera_x, self.y - camera_y

  # Flash during death
  if self.state == "dying":
   if int(time.time() * 10) % 2:
    return

  frame = self.anim.get_frame()
  if frame:
   screen.blit(frame, (screen_x, screen_y))


##############################################################
# OPTIMIZED UI CLASS

class UI:
 def __init__(self):
  self.spritesheet = pygame.image.load("images/ui_hud.png")
  self.full_heart = self.spritesheet.subsurface(0, 0, TILE_SIZE, TILE_SIZE)
  self.empty_heart = self.spritesheet.subsurface(2 * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE)

 def draw(self, screen, player):
  """Draw health hearts"""
  for i in range(player.max_health):
   x = 16 + (i * TILE_SIZE)
   heart = self.full_heart if i < player.health else self.empty_heart
   screen.blit(heart, (x, 16))


##############################################################
# DOOR SYSTEM

class Door:
 def __init__(self, x, y, width, height, locked=True):
  self.rect = pygame.Rect(x, y, width, height)
  self.locked = locked

 def can_enter(self):
  return not self.locked

 def check_collision(self, player_rect):
  return self.rect.colliderect(player_rect)


##############################################################
# OPTIMIZED LEVEL LOADER

class LevelLoader:
 def __init__(self, level_sequence):
  self.level_sequence = level_sequence
  self.current_level_index = 0
  self.tmx_data = None
  self.bg_surface = None
  self.camera_x = self.camera_y = 0
  self.objects = []
  self.player = None
  self.collision_grid = []
  self.animated_tiles = []
  self.doors = []  # List of doors in the level
  self.ui = UI()

  # Transition system
  self.transitioning = False
  self.transition_timer = 0
  self.transition_duration = 0.5  # Half second fade
  self.transition_surface = pygame.Surface((WIDTH, HEIGHT))

  self.load_current_level()

 def load_current_level(self):
  """Load current level"""
  if self.current_level_index >= len(self.level_sequence):
   return False

  level_name = self.level_sequence[self.current_level_index]
  tmx_path = os.path.join("data", "tmx", f"{level_name}.tmx")

  try:
   self.tmx_data = pytmx.load_pygame(tmx_path)
   self._create_collision_grid()
   self._render_background()
   self._load_objects()
   self._load_animated_tiles()
   return True
  except Exception as e:
   print(f"Error loading level: {e}")
   return False

 def _create_collision_grid(self):
  """Create collision grid"""
  if not self.tmx_data:
   return

  w, h = self.tmx_data.width, self.tmx_data.height
  self.collision_grid = [[False] * w for _ in range(h)]

  # Find colliders layer
  for layer in self.tmx_data.layers:
   if layer.name == "colliders" and hasattr(layer, "data"):
    for x, y, gid in layer:
     if gid and 0 <= y < h and 0 <= x < w:
      self.collision_grid[y][x] = True
    break

 def _render_background(self):
  """Pre-render background"""
  if not self.tmx_data:
   return

  w = self.tmx_data.width * self.tmx_data.tilewidth
  h = self.tmx_data.height * self.tmx_data.tileheight
  self.bg_surface = pygame.Surface((w, h))

  # Render background and colliders layers
  for layer_name in ["background", "colliders"]:
   for layer in self.tmx_data.layers:
    if layer.name == layer_name and hasattr(layer, "data"):
     for x, y, gid in layer:
      if gid:
       tile = self.tmx_data.get_tile_image_by_gid(gid)
       if tile:
        self.bg_surface.blit(tile, (x * self.tmx_data.tilewidth,
                                    y * self.tmx_data.tileheight))
     break

 def _load_objects(self):
  """Load objects from level"""
  self.objects = []
  self.player = None
  self.doors = []  # Reset doors for new level

  if not self.tmx_data:
   return

  # Find objects layer
  for layer in self.tmx_data.layers:
   if layer.name == "objects":
    for obj in layer:
     name = obj.name.lower() if obj.name else ""

     if name == "player":
      player = Player(obj.x, obj.y)
      self.objects.append(player)
      self.player = player
     elif name == "door":
      # Get locked property with default
      locked = getattr(obj, "locked", True)
      if hasattr(obj, "properties"):
       locked = obj.properties.get("locked", locked)

      door = Door(obj.x, obj.y, obj.width, obj.height, locked)
      self.doors.append(door)
     elif name == "enemy":
      # Get properties with defaults
      enemy_type = getattr(obj, "enemy_type", "rat")
      movement = getattr(obj, "enemy_movement", "horizontal")
      blocks = getattr(obj, "blocks", 2)

      if hasattr(obj, "properties"):
       enemy_type = obj.properties.get("enemy_type", enemy_type)
       movement = obj.properties.get("enemy_movement", movement)
       blocks = obj.properties.get("blocks", blocks)

      enemy = Enemy(obj.x, obj.y, enemy_type, movement, int(blocks))
      self.objects.append(enemy)
     elif name == "info":
      # Handle music
      music_file = getattr(obj, "music", None)
      if hasattr(obj, "properties"):
       music_file = obj.properties.get("music", music_file)
      if music_file:
       self._load_music(music_file)
    break

 def _load_music(self, filename):
  """Load background music"""
  try:
   music.stop()
   if os.path.exists(f"music/{filename}.ogg"):
    music.play(filename)
  except:
   pass

 def _load_animated_tiles(self):
  """Load animated tiles - simplified"""
  self.animated_tiles = []

  if not self.tmx_data:
   return

  # Find animated layer
  for layer in self.tmx_data.layers:
   if layer.name == "animated" and hasattr(layer, "data"):
    for x, y, gid in layer:
     if gid:
      frames = self._get_tile_frames(gid)
      if frames and len(frames) > 1:  # Only store truly animated tiles
       self.animated_tiles.append({
        'x': x * self.tmx_data.tilewidth,
        'y': y * self.tmx_data.tileheight,
        'frames': frames
       })
    break

 def _get_tile_frames(self, gid):
  """Extract animation frames for a tile"""
  try:
   props = self.tmx_data.get_tile_properties_by_gid(gid)
   if props and "frames" in props:
    frames = []
    for frame in props["frames"]:
     surface = self.tmx_data.get_tile_image_by_gid(frame.gid)
     if surface:
      frames.append(surface)
    return frames
   else:
    # Static tile
    surface = self.tmx_data.get_tile_image_by_gid(gid)
    return [surface] if surface else []
  except:
   surface = self.tmx_data.get_tile_image_by_gid(gid)
   return [surface] if surface else []

 def start_transition(self):
  """Start level transition"""
  if self.transitioning:
   return False

  self.transitioning = True
  self.transition_timer = time.time()
  return True

 def next_level(self):
  """Load next level in sequence"""
  self.current_level_index += 1
  if self.current_level_index >= len(self.level_sequence):
   # No more levels - could show victory screen or loop back
   print("All levels completed!")
   self.current_level_index = len(self.level_sequence) - 1  # Stay on last level
   return False

  return self.load_current_level()

 def is_position_blocked(self, x, y):
  """Check if position is blocked"""
  tile_x, tile_y = int(x // TILE_SIZE), int(y // TILE_SIZE)
  if (tile_x < 0 or tile_y < 0 or
    tile_y >= len(self.collision_grid) or
    tile_x >= len(self.collision_grid[0])):
   return True
  return self.collision_grid[tile_y][tile_x]

 def update(self):
  """Update game logic"""
  # Handle transition
  if self.transitioning:
   elapsed = time.time() - self.transition_timer
   print(f"Transition progress: {elapsed:.2f}/{self.transition_duration}")  # Debug
   if elapsed >= self.transition_duration:
    # Transition complete, load next level
    print("Transition complete, loading next level")  # Debug
    self.transitioning = False
    success = self.next_level()
    print(f"Next level loaded: {success}")  # Debug
   return  # Don't update game during transition

  # Update entities
  for entity in self.objects:
   if hasattr(entity, 'update'):
    if isinstance(entity, Enemy):
     entity.update(self)
    else:
     entity.update()

  # Collision checks
  self._check_collisions()

  # Remove dead enemies
  self.objects = [obj for obj in self.objects
                  if not (isinstance(obj, Enemy) and obj.should_be_removed())]

 def _check_collisions(self):
  """Check all collisions"""
  if not self.player:
   return

  player_rect = self.player.get_rect()

  # Door collisions (check first, highest priority) - but only if not already transitioning
  if not self.transitioning:
   for door in self.doors:
    if door.check_collision(player_rect) and door.can_enter():
     # Player entered an unlocked door!
     print("Player entered door - starting transition")  # Debug
     self.start_transition()
     return  # Exit early, don't check other collisions during transition

  # Player-enemy collisions
  if self.player.invincible_timer <= 0:
   for obj in self.objects:
    if isinstance(obj, Enemy) and obj.state not in ["hurt", "dying"]:
     if player_rect.colliderect(obj.get_rect()):
      self.player.take_damage(1)
      break

  # Sword-enemy collisions
  if self.player.state == "attacking":
   sword_rect = self._get_sword_rect()
   if sword_rect:
    for obj in self.objects:
     if isinstance(obj, Enemy) and obj.state not in ["hurt", "dying"]:
      if sword_rect.colliderect(obj.get_rect()):
       if obj.take_damage():
        obj.start_death()
       break

 def _get_sword_rect(self):
  """Get sword attack rectangle"""
  if not self.player or self.player.state != "attacking":
   return None

  if self.player.facing == "right":
   return pygame.Rect(self.player.x + TILE_SIZE, self.player.y, TILE_SIZE, TILE_SIZE)
  else:
   return pygame.Rect(self.player.x - TILE_SIZE, self.player.y, TILE_SIZE, TILE_SIZE)

 def draw(self, screen):
  """Draw everything"""
  # Background
  if self.bg_surface:
   screen_rect = pygame.Rect(self.camera_x, self.camera_y, WIDTH, HEIGHT)
   screen.blit(self.bg_surface, (0, 0), screen_rect)

  # Animated tiles (simplified)
  if self.animated_tiles:
   frame_time = pygame.time.get_ticks() // 600  # 600ms per frame
   for tile in self.animated_tiles:
    if len(tile['frames']) > 1:
     frame_idx = frame_time % len(tile['frames'])
     screen_x = tile['x'] - self.camera_x
     screen_y = tile['y'] - self.camera_y
     if -TILE_SIZE <= screen_x <= WIDTH and -TILE_SIZE <= screen_y <= HEIGHT:
      screen.blit(tile['frames'][frame_idx], (screen_x, screen_y))

  # Entities
  for obj in self.objects:
   obj.draw(screen, self.camera_x, self.camera_y)

  # UI
  if self.player:
   self.ui.draw(screen, self.player)

  # Debug (including doors)
  if DEBUG_MODE_ON:
   self._draw_debug(screen)

  # Transition overlay (draw last)
  if self.transitioning:
   self._draw_transition(screen)

 def _draw_transition(self, screen):
  """Draw retro fade transition"""
  elapsed = time.time() - self.transition_timer
  progress = elapsed / self.transition_duration

  # Fade to black
  alpha = int(255 * progress)
  self.transition_surface.fill((0, 0, 0))
  self.transition_surface.set_alpha(alpha)
  screen.blit(self.transition_surface, (0, 0))

 def _draw_debug(self, screen):
  """Draw debug info"""
  # Draw collision tiles in red
  for y, row in enumerate(self.collision_grid):
   for x, blocked in enumerate(row):
    if blocked:
     screen_x = (x * TILE_SIZE) - self.camera_x
     screen_y = (y * TILE_SIZE) - self.camera_y
     if -TILE_SIZE <= screen_x <= WIDTH and -TILE_SIZE <= screen_y <= HEIGHT:
      red_surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
      red_surf.set_alpha(128)
      red_surf.fill((255, 0, 0))
      screen.blit(red_surf, (screen_x, screen_y))

  # Draw doors in green/yellow
  for door in self.doors:
   screen_x = door.rect.x - self.camera_x
   screen_y = door.rect.y - self.camera_y
   if -door.rect.width <= screen_x <= WIDTH and -door.rect.height <= screen_y <= HEIGHT:
    door_surf = pygame.Surface((door.rect.width, door.rect.height))
    door_surf.set_alpha(128)
    # Green if unlocked, yellow if locked
    color = (0, 255, 0) if door.can_enter() else (255, 255, 0)
    door_surf.fill(color)
    screen.blit(door_surf, (screen_x, screen_y))

 def move_player(self, dx, dy):
  """Move player with collision check"""
  if self.player:
   new_x = self.player.x + (dx * TILE_SIZE)
   new_y = self.player.y + (dy * TILE_SIZE)

   if not self.is_position_blocked(new_x, new_y):
    level_width, level_height = self.get_level_size()
    current_time = pygame.time.get_ticks() / 1000.0
    return self.player.move(dx, dy, level_width, level_height, current_time)
  return False

 def get_level_size(self):
  """Get level size in pixels"""
  if self.tmx_data:
   return (self.tmx_data.width * self.tmx_data.tilewidth,
           self.tmx_data.height * self.tmx_data.tileheight)
  return (0, 0)


##############################################################
# GAME LOOP

def toggle_debug_mode():
 global DEBUG_MODE_ON
 DEBUG_MODE_ON = not DEBUG_MODE_ON
 print(f"Debug mode: {'ON' if DEBUG_MODE_ON else 'OFF'}")


# Global level loader
level_loader = LevelLoader(LEVEL_SEQUENCE)


def draw():
 screen.clear()
 level_loader.draw(screen.surface)


def update():
 level_loader.update()

 # Debug toggle
 if keyboard.d:
  toggle_debug_mode()
  time.sleep(0.2)

 # Attack
 if keyboard.space:
  if level_loader.player:
   level_loader.player.start_attack()
  time.sleep(0.1)

 # Movement (one direction at a time, no diagonal, no movement while attacking or transitioning)
 if not (level_loader.player and level_loader.player.state == "attacking") and not level_loader.transitioning:
  if keyboard.left and not any([keyboard.right, keyboard.up, keyboard.down]):
   level_loader.move_player(-1, 0)
  elif keyboard.right and not any([keyboard.left, keyboard.up, keyboard.down]):
   level_loader.move_player(1, 0)
  elif keyboard.up and not any([keyboard.left, keyboard.right, keyboard.down]):
   level_loader.move_player(0, -1)
  elif keyboard.down and not any([keyboard.left, keyboard.right, keyboard.up]):
   level_loader.move_player(0, 1)


pgzrun.go()