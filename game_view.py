from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import actors
import terminal

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
        self.target        = point.to_int()
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
            fpos = (self.follow.GetPos()*globals.tile_dimensions).to_int()
            if not fpos:
                return
            target = fpos - (globals.screen*0.5).to_int()
            diff = target - self.pos
            #print diff.SquareLength(),self.follow_threshold
            direction = diff.direction()
            
            if abs(diff.x) < self.max_away.x and abs(diff.y) < self.max_away.y:
                adjust = diff*0.02
            else:
                adjust = diff*0.03
            #adjust = adjust.to_int()
            if adjust.x == 0 and adjust.y == 0:
                adjust = direction
            self.pos += adjust
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
    GRASS               = 1
    WALL                = 2
    DOOR_CLOSED         = 3
    DOOR_OPEN           = 4
    TILE                = 5
    PLAYER              = 6
    ROAD                = 7
    ROAD_MARKING        = 8
    CHAINLINK           = 9
    JODRELL_SIGN        = 10
    BARRIER             = 11
    ROAD_MARKING_HORIZ  = 13
    WOOD                = 15
    BATHROOM_TILE       = 16
    LAB_TILE            = 17
    DOOR_LOCKED_LAB     = 18
    DOOR_LOCKED_DISH    = 19
    LAB_WHITEBOARD      = 20
    QUARTERS_WHITEBOARD = 21

    Doors      = set((DOOR_CLOSED,DOOR_OPEN,DOOR_LOCKED_LAB,DOOR_LOCKED_DISH))
    Computers  = set()
    Whiteboards = set((LAB_WHITEBOARD,QUARTERS_WHITEBOARD))
    Impassable = set((WALL,DOOR_CLOSED,CHAINLINK,JODRELL_SIGN,BARRIER)) | Computers | Whiteboards

class TileData(object):
    texture_names = {TileTypes.GRASS         : 'grass.png',
                     TileTypes.ROAD          : 'road.png',
                     TileTypes.ROAD_MARKING  : 'marking.png',
                     TileTypes.ROAD_MARKING_HORIZ : 'marking1.png',
                     TileTypes.WALL          : 'wall.png',
                     TileTypes.PLAYER        : 'road.png',
                     TileTypes.DOOR_CLOSED   : 'door_closed.png',
                     TileTypes.DOOR_OPEN     : 'door_open.png',
                     TileTypes.TILE          : 'tile.png',
                     TileTypes.JODRELL_SIGN  : 'sign.png',
                     TileTypes.CHAINLINK     : 'chain.png',
                     TileTypes.BARRIER       : 'barrier.png',
                     TileTypes.WOOD          : 'wood.png',
                     TileTypes.BATHROOM_TILE : 'bathroom_tile.png',
                     TileTypes.LAB_TILE      : 'labtile.png',
                     TileTypes.LAB_WHITEBOARD :  'lab_whiteboard.png',
                     TileTypes.QUARTERS_WHITEBOARD :  'quarters_whiteboard.png',
                     }
    
    def __init__(self,type,pos):
        self.pos  = pos
        self.type = type
        try:
            self.name = self.texture_names[type]
        except KeyError:
            self.name = self.texture_names[TileTypes.GRASS]
        #How big are we?
        self.size = ((globals.atlas.TextureSubimage(self.name).size)/globals.tile_dimensions).to_int()
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.name))
        bl        = pos * globals.tile_dimensions
        tr        = bl + self.size*globals.tile_dimensions
        self.quad.SetVertices(bl,tr,0)
    def Delete(self):
        self.quad.Delete()
    def Interact(self,player):
        pass

class ObjectTypes:
    BED_UP   = 1
    BED_DOWN = 2
    DISH     = 3
    LOCKER   = 4
    CAR      = 5
    COMPUTER = 6

class GameObject(object):
    level = 1
    texture_names = {ObjectTypes.BED_UP   : ('bedup.png'   , Point(0,0)),
                     ObjectTypes.BED_DOWN : ('beddown.png' , Point(0,0)),
                     ObjectTypes.CAR      : ('car.png'     , Point(0,0)),
                     ObjectTypes.DISH     : ('dish.png'    , Point(0,0)),
                     ObjectTypes.COMPUTER : ('computer.png', Point(0,0)),
                     ObjectTypes.LOCKER   : ('locker.png',   Point(0,0))}
    def __init__(self,pos):
        self.name,self.offset = self.texture_names[self.type]
        self.pos = pos + self.offset
        self.size = ((globals.atlas.TextureSubimage(self.name).size.to_float())/globals.tile_dimensions)
        self.tr = self.pos + self.size
        self.quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords(self.name))
        bl        = self.pos * globals.tile_dimensions
        tr        = bl + self.size*globals.tile_dimensions
        self.quad.SetVertices(bl,tr,self.level)

    def CoveredTiles(self):
        bl = (self.pos + self.offset).to_int()
        tr = (bl + self.size + Point(1,1)).to_int()
        for x in xrange(bl.x,tr.x):
            for y in xrange(bl.y,tr.y):
                yield (x,y)

    def Contains(self,p):
        if p.x >= self.pos.x and p.y >= self.pos.y and p.x < self.tr.x and p.y < self.tr.y:
            return True
        return False

    def Interact(self,player):
        pass

class Dish(GameObject):
    type = ObjectTypes.DISH

class Bed(GameObject):
    num = 0
    def __init__(self,pos,direction = 'up'):
        self.sound = getattr(globals.sounds,'bed%d' % (self.num+1))
        Bed.num += 1
        if direction == 'up':
            self.type = ObjectTypes.BED_UP
        else:
            self.type = ObjectTypes.BED_DOWN
        super(Bed,self).__init__(pos)
        
    def Interact(self,player):
        globals.sounds.PlayVoice(self.sound)

class Locker(GameObject):
    type = ObjectTypes.LOCKER
    def __init__(self,pos,combination,parent):
        super(Locker,self).__init__(pos)
        self.combination = [c for c in combination[:4]]
        self.parent = parent
        self.screen = ui.Box(parent = globals.screen_root,
                             pos = Point(0.415,0.465),
                             tr = Point(0.585,0.54),
                             colour = drawing.constants.colours.white)
        self.current = ['0','0','0','0']
        self.screen.combo = ui.TextBox(parent = self.screen,
                                       bl     = Point(0,0) ,
                                       tr     = Point(1,1) ,
                                       text   = ''.join(self.current) ,
                                       textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                       colour = (0,0,0,1),
                                       scale  = 8)
        self.selected = 0
        self.screen.selected = ui.Box(parent = self.screen,
                                      pos = Point(0,-0.05),
                                      tr = Point(0.25,0.15),
                                      colour = drawing.constants.colours.red,
                                      extra = 2)
        self.screen.Disable()

    def Interact(self,player):
        print 'locker'
        self.screen.Enable()
        self.parent.computer = self
        self.current_key = None
        self.current_player = player

    def KeyDown(self,key):
        if key in (pygame.K_ESCAPE,):
            return
        if key >= pygame.K_KP0 and key <= pygame.K_KP9:
            key -= (pygame.K_KP0 - pygame.K_0)

        self.current_key = key
        if key == pygame.K_TAB:
            return
        elif key == pygame.K_RIGHT:
            self.SetSelected(self.selected + 1)
        elif key == pygame.K_LEFT:
            self.SetSelected(self.selected - 1)
        elif key == pygame.K_UP:
            self.AdjustSelected(1)
        elif key == pygame.K_DOWN:
            self.AdjustSelected(-1)
        elif key == pygame.K_RETURN:
            if self.current == self.combination:
                print 'correct!'
                self.screen.Disable()
                self.parent.CloseScreen()
                if self.current_player:
                    self.current_player.AddItem(actors.LabKey())
                    globals.sounds.PlayVoice(globals.sounds.getkey)
                self.parent.SetInfoText('You recieved a LabKey')
                self.current_player = None
                
            else:
                print 'incorrect!'

        
    def AdjustSelected(self,diff):
        print ''.join(self.current)
        self.current[self.selected] = '%d' % ((int(self.current[self.selected]) + diff)%10)
        print ''.join(self.current)
        self.screen.combo.SetText(''.join(self.current),(0,0,0,1))

    def SetSelected(self,n):
        if n < 0:
            n = 0
        if n > 3:
            n = 3
        self.selected = n
        self.screen.selected.bottom_left = Point(self.selected*0.25,-0.05)
        self.screen.selected.top_right = Point((self.selected+1)*0.25,0.15)
        self.screen.selected.UpdatePosition()

    def KeyUp(self,key):
        if key == pygame.K_ESCAPE:
            self.screen.Disable()
            self.parent.CloseScreen()
            self.current_player = None

        if self.current_key:
            self.current_key = None

    def Update(self,t):
        if not self.current_key:
            return
        elif self.current_key == pygame.K_TAB:
            self.current_key = None
            return

class Car(GameObject):
    type = ObjectTypes.CAR
    def Interact(self,player):
        globals.sounds.PlayVoice(globals.sounds.cantleave)

class Computer(GameObject):
    key_repeat_time = 40
    initial_key_repeat = 300
    type = ObjectTypes.COMPUTER
    level = 10
    def __init__(self,pos,terminal_type,parent):
        super(Computer,self).__init__(pos)
        self.terminal = None
        self.parent = parent
        self.terminal_type = terminal_type
        self.last_keyrepeat = None
        bl = Point(0,0.45) + (Point(6,6).to_float()/globals.screen)
        tr = Point(1,1) - (Point(6,6).to_float()/globals.screen)
        self.screen = ui.Box(parent = globals.screen_root,
                             pos = Point(0,0),
                             tr = Point(1,1),
                             colour = drawing.constants.colours.black)
        self.screen.Disable()

    def SetScreen(self):
        #globals.sounds.terminal_on.play()
        if self.terminal == None:
            self.terminal = self.terminal_type(parent     = self.screen,
                                               gameview   = self.parent,
                                               computer   = self,
                                               background = drawing.constants.colours.black,
                                               foreground = drawing.constants.colours.green)
        self.terminal.StartMusic()
        #else:
        #    self.terminal.Enable()
        self.current_key = None
        globals.game_view.SetInfoText('Press ESC to return, and CTRL-C to kill running programs')

    def Interact(self,player):
        self.screen.Enable()
        self.SetScreen()
        self.parent.computer = self

    def KeyDown(self,key):
        if key in (pygame.K_ESCAPE,):
            return
        if key >= pygame.K_KP0 and key <= pygame.K_KP9:
            key -= (pygame.K_KP0 - pygame.K_0)

        self.current_key = key
        if key == pygame.K_TAB:
            return
        self.last_keyrepeat = None
        self.terminal.AddKey(key)

    def KeyUp(self,key):
        if key == pygame.K_ESCAPE:
            self.screen.Disable()
            self.parent.CloseScreen()
            if self.terminal.GameOver():
                self.parent.GameOver()
        if self.current_key:
            self.current_key = None

    def Update(self,t):
        self.terminal.Update(t)
        if not self.current_key:
            return
        if self.last_keyrepeat == None:
            self.last_keyrepeat = t+self.initial_key_repeat
            return
        if t - self.last_keyrepeat > self.key_repeat_time:
            self.terminal.AddKey(self.current_key,repeat=True)
            self.last_keyrepeat = t

class Door(TileData):
    def __init__(self,type,pos):
        self.keytype = None
        if type in (TileTypes.DOOR_LOCKED_LAB,TileTypes.DOOR_LOCKED_DISH):
            self.locked = True
            if type == TileTypes.DOOR_LOCKED_LAB:
                self.keytype = actors.LabKey
            else:
                self.keytype = actors.DishKey
            type = TileTypes.DOOR_CLOSED
        else:
            self.locked = False
        super(Door,self).__init__(type,pos)
        
    def Toggle(self):
        if self.type == TileTypes.DOOR_CLOSED:
            self.type = TileTypes.DOOR_OPEN
            globals.sounds.dooropen.play()
            if self.keytype == actors.LabKey:
                globals.sounds.PlayVoice(globals.sounds.lab)
        else:
            self.type = TileTypes.DOOR_CLOSED
            globals.sounds.doorclosed.play()
        self.quad.SetTextureCoordinates(globals.atlas.TextureSpriteCoords(self.texture_names[self.type]))

    def Interact(self,player):
        if not self.locked:
            self.Toggle()
        else:
            if any(isinstance(item,self.keytype) for item in player.inventory.items):
                self.Toggle()
                globals.game_view.SetInfoText('You used "%s"' % self.keytype.name)
            else:
                #play locked sound or what have you
                #print 'locked!'
                globals.sounds.PlayVoice(globals.sounds.locked)

class WhiteBoard(TileData):
    fulltexture_names = {TileTypes.LAB_WHITEBOARD : 'labwb_full.png',
                         TileTypes.QUARTERS_WHITEBOARD : 'quarterswb_full.png'}
    def __init__(self,type,pos):
        super(WhiteBoard,self).__init__(type,pos)
        try:
            self.full_name = self.fulltexture_names[type]
        except KeyError:
            self.full_name = self.fulltexture_names[TileTypes.GRASS]
        self.guide = ui.UIElement(parent = globals.screen_root,
                                  pos = Point(0.15,0.15),
                                  tr = Point(0.85,0.85))
        self.quad = drawing.Quad(globals.screen_texture_buffer,tc = globals.atlas.TextureSpriteCoords(self.full_name))
        self.quad.SetVertices(self.guide.absolute.bottom_left,self.guide.absolute.top_right,drawing.constants.DrawLevels.ui + 800)
        self.quad.Disable()

    def Interact(self,player):
        print 'wb'
        if player.pos.y > self.pos.y:
            return
        self.quad.Enable()
        globals.game_view.computer = self
        if self.type == TileTypes.LAB_WHITEBOARD:
            hint = 'Hint: You need to do some maths. You might need a calculator.'
            globals.sounds.PlayVoice(globals.sounds.lab_wb)
        else:
            hint = 'Press ESC to return'
            globals.sounds.PlayVoice(globals.sounds.quarters_wb)
        globals.game_view.SetInfoText(hint)

    def KeyDown(self,key):
        pass

    def KeyUp(self,key):
        if key == pygame.K_ESCAPE:
            self.quad.Disable()
            globals.game_view.CloseScreen()
            globals.game_view.SetInfoText(' ')

    def Update(self,t):
        return

def TileDataFactory(map,type,pos):
    if type in TileTypes.Whiteboards:
        return WhiteBoard(type,pos)
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
                     'd' : TileTypes.DOOR_CLOSED,
                     'L' : TileTypes.DOOR_LOCKED_LAB,
                     'x' : TileTypes.DOOR_LOCKED_DISH,
                     'o' : TileTypes.DOOR_OPEN,
                     'm' : TileTypes.ROAD_MARKING,
                     'M' : TileTypes.ROAD_MARKING_HORIZ,
                     'c' : TileTypes.CHAINLINK,
                     's' : TileTypes.JODRELL_SIGN,
                     'p' : TileTypes.PLAYER,
                     'w' : TileTypes.WOOD,
                     'W' : TileTypes.LAB_WHITEBOARD,
                     '3' : TileTypes.QUARTERS_WHITEBOARD,
                     't' : TileTypes.BATHROOM_TILE,
                     'b' : TileTypes.BARRIER,
                     'l' : TileTypes.LAB_TILE}
    def __init__(self,name,parent):
        self.size   = Point(89,49)
        self.data   = [[TileTypes.GRASS for i in xrange(self.size.y)] for j in xrange(self.size.x)]
        self.object_cache = {}
        self.object_list = []
        self.actors = []
        self.doors  = []
        self.player = None
        self.parent = parent
        y = self.size.y - 1
        with open(name) as f:
            for line in f:
                line = line.strip('\n')
                if len(line) < self.size.x:
                    line += ' '*(self.size.x - len(line))
                if len(line) > self.size.x:
                    line = line[:self.size.x]
                for inv_x,tile in enumerate(line[::-1]):
                    x = self.size.x-1-inv_x
                    #try:
                    if 1:
                        td = TileDataFactory(self,self.input_mapping[tile],Point(x,y))
                        for tile_x in xrange(td.size.x):
                            for tile_y in xrange(td.size.y):
                                if self.data[x+tile_x][y+tile_y] != TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y].Delete()
                                    self.data[x+tile_x][y+tile_y] = TileTypes.GRASS
                                if self.data[x+tile_x][y+tile_y] == TileTypes.GRASS:
                                    self.data[x+tile_x][y+tile_y] = td
                        if self.input_mapping[tile] == TileTypes.PLAYER:
                            self.player = actors.Player(self,Point(x+0.2,y))
                            self.actors.append(self.player)
                        if isinstance(td,Door):
                            if self.input_mapping[tile] == TileTypes.DOOR_LOCKED_DISH:
                                parent.dish_door = td
                            self.doors.append(td)
                    #except KeyError:
                    #    raise globals.types.FatalError('Invalid map data')
                y -= 1
                if y < 0:
                    break

        self.AddObject(Dish(Point(42,31)))
        self.AddObject(Bed(Point(62,22)))
        self.AddObject(Bed(Point(71,22)))
        self.AddObject(Bed(Point(62,17),direction='down'))
        self.AddObject(Car(Point(55,2)))
        self.AddObject(Locker(Point(67,23),'2212',self.parent))
        self.AddObject(Computer(Point(75,17),terminal.DomsComputer,self.parent))
        self.AddObject(Computer(Point(39,23),terminal.LabComputer,self.parent))
        self.AddObject(Computer(Point(36,23),terminal.SignalComputer,self.parent))
        self.AddObject(Computer(Point(50,31),terminal.FinalComputer,self.parent))

    def AddObject(self,obj):
        self.object_list.append(obj)
        #Now for each tile that the object touches, put it in the cache
        for tile in obj.CoveredTiles():
            self.object_cache[tile] = obj

class GameView(ui.RootElement):
    def __init__(self):
        self.dish_door = None
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.map = GameMap('level1.txt',self)
        self.map.world_size = self.map.size * globals.tile_dimensions
        self.viewpos = Viewpos(Point(915,0))
        self.player_direction = Point(0,0)   
        self.game_over = False
        self.computer = None
        self.info_box = ui.Box(parent = globals.screen_root,
                               pos = Point(0,0),
                               tr = Point(1,0.05),
                               colour = (0,0,0,0.9))
        self.info_box.text = ui.TextBox(self.info_box,
                                        bl = Point(0,0),
                                        tr = Point(1,0.7),
                                        text = 'Space to interact, I for inventory',
                                        textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                        colour = (1,1,0,1),
                                        scale = 3,
                                        alignment = drawing.texture.TextAlignments.CENTRE)
        self.info_box.Disable()
        #pygame.mixer.music.load('music.ogg')
        self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game
        self.mode = modes.Titles(self)
        #self.mode = modes.LevelOne(self)
        super(GameView,self).__init__(Point(0,0),Point(*self.map.world_size))
        #self.StartMusic()

    def SetInfoText(self,text):
        self.info_box.text.SetText(text,colour=(1,1,0,1))

    def OpenDish(self):
        print self.dish_door
        if self.dish_door:
            print 'toggling jim'
            self.dish_door.Toggle()

    def StartMusic(self):
        pygame.mixer.music.load('music.ogg')
        pygame.mixer.music.set_volume(0.1)
        pygame.mixer.music.play(-1)
        self.music_playing = True

    def Draw(self):
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

        if self.computer:
            return self.computer.Update(t)
            
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
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(0.1)
        self.mode.KeyUp(key)

    def CloseScreen(self):
        if isinstance(self.computer,Computer):
            self.computer.terminal.StopMusic()
        self.computer = None
        self.SetInfoText(' ')
