from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import actors

class Viewpos(object):
    follow_threshold = 0
    max_away = Point(100,60)
    def __init__(self,point):
        self.pos = point
        self.NoTarget()
        self.follow = None
        self.follow_locked = False
        self.t = 0

    def NoTarget(self):
        self.target        = None
        self.target_change = None
        self.start_point   = None
        self.target_time   = None
        self.start_time    = None

    def Set(self,point):
        self.pos = point.to_int()
        self.NoTarget()

    def SetTarget(self,point,t,rate=2,callback = None):
        #Don't fuck with the view if the player is trying to control it
        rate /= 4.0
        self.follow        = None
        self.follow_start  = 0
        self.follow_locked = False
        self.target        = point
        self.target_change = self.target - self.pos
        self.start_point   = self.pos
        self.start_time    = t
        self.duration      = self.target_change.length()/rate
        self.callback      = callback
        if self.duration < 200:
            self.duration  = 200
        self.target_time   = self.start_time + self.duration

    def Follow(self,t,actor):
        """
        Follow the given actor around.
        """
        self.follow        = actor
        self.follow_start  = t
        self.follow_locked = False

    def HasTarget(self):
        return self.target != None

    def Get(self):
        return self.pos

    def Skip(self):
        self.pos = self.target
        self.NoTarget()
        if self.callback:
            self.callback(self.t)
            self.callback = None

    def Update(self,t):
        try:
            return self.update(t)
        finally:
            self.pos = self.pos.to_int()

    def update(self,t):
        self.t = t
        if self.follow:
            #We haven't locked onto it yet, so move closer, and lock on if it's below the threshold
            fpos = self.follow.GetPos()*globals.tile_dimensions
            if not fpos:
                return
            target = fpos - globals.screen*0.5
            diff = target - self.pos
            #print diff.SquareLength(),self.follow_threshold
            if abs(diff.x) < self.max_away.x and abs(diff.y) < self.max_away.y:
                self.pos += diff*0.02
                return
            self.pos += diff*0.03
            return
                
        elif self.target:
            if t >= self.target_time:
                self.pos = self.target
                self.NoTarget()
                if self.callback:
                    self.callback(t)
                    self.callback = None
            elif t < self.start_time: #I don't think we should get this
                return
            else:
                partial = float(t-self.start_time)/self.duration
                partial = partial*partial*(3 - 2*partial) #smoothstep
                self.pos = (self.start_point + (self.target_change*partial)).to_int()

class TileTypes:
    GRASS             = 1
    WALL              = 2
    DOOR_CLOSED       = 3
    DOOR_OPEN         = 4
    TILE              = 5
    PLAYER            = 6
    ROAD              = 7
    ROAD_MARKING      = 8

    Doors      = set((DOOR_CLOSED,DOOR_OPEN))
    Computers  = set()
    Impassable = set((WALL,DOOR_CLOSED)) | Computers

class TileData(object):
    texture_names = {TileTypes.GRASS         : 'grass.png',
                     TileTypes.ROAD          : 'road.png',
                     TileTypes.ROAD_MARKING  : 'marking.png',
                     TileTypes.WALL          : 'wall.png',
                     TileTypes.DOOR_CLOSED   : 'door_closed.png',
                     TileTypes.DOOR_OPEN     : 'door_open.png',
                     TileTypes.TILE          : 'tile.png'}
    
    def __init__(self,type,pos):
        self.pos  = pos
        self.type = type
        try:
            self.name = self.texture_names[type]
        except KeyError:
            self.name = self.texture_names[TileTypes.GRASS]
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.name))
        bl        = pos * globals.tile_dimensions
        tr        = bl + globals.tile_dimensions
        self.quad.SetVertices(bl,tr,0)

class Door(TileData):
    def __init__(self,type,pos):
        super(Door,self).__init__(type,pos)
        
    def Toggle(self):
        if self.type == TileTypes.DOOR_CLOSED:
            self.type = TileTypes.DOOR_OPEN
        else:
            self.type = TileTypes.DOOR_CLOSED
        self.quad.SetTextureCoordinates(globals.atlas.TextureSpriteCoords(self.texture_names[self.type]))

def TileDataFactory(map,type,pos):
    if type in TileTypes.Doors:
        return Door(type,pos)
    else:
        return TileData(type,pos)

class GameMap(object):
    input_mapping = {' ' : TileTypes.GRASS,
                     '.' : TileTypes.TILE,
                     '|' : TileTypes.WALL,
                     '-' : TileTypes.WALL,
                     '+' : TileTypes.WALL,
                     'r' : TileTypes.ROAD,
                     'm' : TileTypes.ROAD_MARKING,
                     'p' : TileTypes.PLAYER,}
    def __init__(self,name):
        self.size   = Point(120,84)
        self.data   = [[TileTypes.GRASS for i in xrange(self.size.y)] for j in xrange(self.size.x)]
        self.actors = []
        self.doors  = []
        self.player = None
        y = self.size.y - 1
        with open(name) as f:
            for line in f:
                line = line.strip('\n')
                if len(line) < self.size.x:
                    line += ' '*(self.size.x - len(line))
                if len(line) > self.size.x:
                    line = line[:self.size.x]
                for x,tile in enumerate(line):
                    #try:
                    if 1:
                        td = TileDataFactory(self,self.input_mapping[tile],Point(x,y))
                        self.data[x][y] = td
                        if self.input_mapping[tile] == TileTypes.PLAYER:
                            self.player = actors.Player(self,Point(x+0.2,y))
                            self.actors.append(self.player)
                        if isinstance(td,Door):
                            self.doors.append(td)
                    #except KeyError:
                    #    raise globals.types.FatalError('Invalid map data')
                y -= 1
                if y < 0:
                    break

class GameView(ui.RootElement):
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.map = GameMap('level1.txt')
        self.map.world_size = self.map.size * globals.tile_dimensions
        self.viewpos = Viewpos(Point(915,0))
        self.player_direction = Point(0,0)   
        self.game_over = False
        #pygame.mixer.music.load('music.ogg')
        self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game
        self.mode = modes.Titles(self)
        #self.mode = modes.LevelOne(self)
        super(GameView,self).__init__(Point(0,0),Point(*self.map.world_size))
        #self.StartMusic()

    def StartMusic(self):
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

    def Draw(self):
        drawing.ResetState()
        #drawing.DrawAll(globals.backdrop_buffer,self.atlas.texture.texture)
        drawing.ResetState()
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture.texture)
        drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture.texture)
        
    def Update(self,t):
        #print self.viewpos.pos
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return
            
        self.t = t
        self.viewpos.Update(t)
        if self.viewpos.pos.x < 0:
            self.viewpos.pos.x = 0
        if self.viewpos.pos.y < 0:
            self.viewpos.pos.y = 0
        if self.viewpos.pos.x > (self.map.world_size.x - globals.screen.x):
            self.viewpos.pos.x = (self.map.world_size.x - globals.screen.x)
        if self.viewpos.pos.y > (self.map.world_size.y - globals.screen.y):
            self.viewpos.pos.y = (self.map.world_size.y - globals.screen.y)

        self.map.player.Move(self.player_direction)

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)
        
    def KeyDown(self,key):
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        self.mode.KeyUp(key)

