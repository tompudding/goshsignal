from globals.types import Point
import globals
import ui
import drawing
import os
import game_view
import random
import pygame

class Directions:
    UP    = 0
    DOWN  = 1
    RIGHT = 2
    LEFT  = 3

class Items:
    ROMANCE_NOVEL = 1

class Item(object):
    def __init__(self):
        self.enabled = False
        self.quad = drawing.Quad(globals.screen_texture_buffer,tc = globals.atlas.TextureTextureCoords(self.texture_name))
        self.quad.SetTextureCoordinates(globals.atlas.TextureTextureCoords(self.texture_name))
        self.quad.Disable()
        self.sound = getattr(globals.sounds,self.sound)

    def Disable(self):
        if self.enabled:
            self.quad.Disable()
            self.enabled = False

    def Enable(self):
        if not self.enabled:
            self.quad.Enable()
            self.enabled = True

    def SetCoords(self,bl,tr):
        self.quad.SetVertices(bl,tr,drawing.constants.DrawLevels.ui + 800)
        if not self.enabled:
            self.Disable()
        #self.Enable()

    def Describe(self):
        globals.sounds.PlayVoice(self.sound)

class RomanceNovel(Item):
    name         = 'Well thumbed romance novel'
    description  = 'jim'
    texture_name = 'romance_novel.png'
    sound        = 'romance'

class LabKey(Item):
    name         = 'Key to the Laboratory building'
    description  = 'jim'
    texture_name = 'labkey.png'
    sound        = 'keycard'

class DishKey(Item):
    name         = 'Key to the Dish admin building'
    description  = 'jim'
    texture_name = 'labkey.png'
    sounds       = 'keycard'


class Actor(object):
    texture = None
    width = None
    height = None
    def __init__(self,map,pos):
        self.map  = map
        self.dirsa = ((Directions.UP   ,'back' ),
                      (Directions.DOWN ,'front'),
                      (Directions.LEFT ,'left' ),
                      (Directions.RIGHT,'right'))
        self.dirs_pos = {Directions.UP    : Point(0,1),
                         Directions.DOWN  : Point(0,-1),
                         Directions.LEFT  : Point(-1,0),
                         Directions.RIGHT : Point(1,0)}
        self.dirs = {}
        for dir,name in self.dirsa:
            try:
                tc = globals.atlas.TextureSpriteCoords('%s_%s.png' % (self.texture,name))
            except KeyError:
                tc = globals.atlas.TextureSpriteCoords('%s_front.png' % self.texture)
            self.dirs[dir] = tc
        #self.dirs = dict((dir,globals.atlas.TextureSpriteCoords('%s_%s.png' % (self.texture,name))) for (dir,name) in self.dirs)
        self.dir = Directions.DOWN
        self.quad = drawing.Quad(globals.quad_buffer,tc = self.dirs[self.dir])
        self.size = Point(float(self.width)/16,float(self.height)/16)
        self.corners = Point(0,0),Point(self.size.x,0),Point(0,self.size.y),self.size
        self.SetPos(pos)
        self.current_sound = None

    def SetPos(self,pos):
        self.pos = pos
        bl = pos * globals.tile_dimensions
        tr = bl + (globals.tile_scale*Point(self.width,self.height))
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
    
    def Facing(self):
        facing = self.pos + (self.size/2) + self.dirs_pos[self.dir]
        #if we're in the tile, we're not facing it
        for corner in self.corners:
            pos = self.pos + corner
            if pos.to_int() == facing.to_int():
                return None
        return facing.to_int()

    def Move(self,amount):
        amount = Point(amount.x,amount.y)
        dir = None
        if amount.x > 0:
            dir = Directions.RIGHT
        elif amount.x < 0:
            dir = Directions.LEFT
        elif amount.y > 0:
            dir = Directions.UP
        elif amount.y < 0:
            dir = Directions.DOWN
        if dir != None and dir != self.dir:
            self.dir = dir
            self.quad.SetTextureCoordinates(self.dirs[self.dir])
        #check each of our four corners
        for corner in self.corners:
            pos = self.pos + corner
            target_x = pos.x + amount.x
            if target_x >= self.map.size.x:
                amount.x = 0
                target_x = pos.x
            elif target_x < 0:
                amount.x = -pos.x
                target_x = 0
            target_tile_x = self.map.data[int(target_x)][int(pos.y)]
            if target_tile_x.type in game_view.TileTypes.Impassable:
                amount.x = 0
                
            elif (int(target_x),int(pos.y)) in self.map.object_cache:
                obj = self.map.object_cache[int(target_x),int(pos.y)]
                if obj.Contains(Point(target_x,pos.y)):
                    amount.x = 0

            target_y = pos.y + amount.y
            if target_y >= self.map.size.y:
                amount.y = 0
                target_y = pos.y
            elif target_y < 0:
                amount.y = -pos.y
                target_y = 0
            target_tile_y = self.map.data[int(pos.x)][int(target_y)]
            if target_tile_y.type in game_view.TileTypes.Impassable:
                amount.y = 0
            elif (int(pos.x),int(target_y)) in self.map.object_cache:
                obj = self.map.object_cache[int(pos.x),int(target_y)]
                if obj.Contains(Point(pos.x,target_y)):
                    amount.y = 0
            

        self.SetPos(self.pos + amount)

    def GetPos(self):
        return self.pos

class Inventory(object):
    def __init__(self,items,player):
        self.player = player
        self.parent = player.map.parent
        self.screen = ui.Box(parent = globals.screen_root,
                             pos = Point(0.06,0.1),
                             tr = Point(0.94,0.9),
                             colour = (0.8,0.8,0.8,0.6))
        self.screen.title = ui.TextBox(self.screen,
                                       bl = Point(0,0.8),
                                       tr = Point(1,0.99),
                                       text = 'Inventory',
                                       textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                       colour = (0,0,0,1),
                                       scale = 5)
        self.screen.current_name = ui.TextBox(self.screen,
                                              bl = Point(0,0),
                                              tr = Point(1,0.08),
                                              text = ' ',
                                              textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                              colour = (1,0,0,1),
                                              scale = 4,
                                              alignment = drawing.texture.TextAlignments.CENTRE)
        self.screen.selected = ui.Box(parent = self.screen,
                                      pos = Point(0,0),
                                      tr = Point(0,0),
                                      colour = drawing.constants.colours.red,
                                      extra = 2)
        self.screen.slots = []
        self.width  = 5
        self.height = 3
        box_width = 0.1
        interbox_width = (1.0-self.width*box_width)/(self.width+1)
        box_height = 0.2
        interbox_height = (1.0-self.height*box_height)/(self.height+1)
        inter = Point(interbox_width,interbox_height)
        box_size = Point(box_width,box_height)
        self.selected_coords = []
        for i in xrange(self.width * self.height):
            x = i%self.width
            ypos = i/self.width
            if ypos >= self.height:
                break
            y = self.height-1-ypos
            bl = Point((interbox_width*(x+1)) + (box_width*x),
                       (interbox_height*(y+1)) + (box_height*y))
            tr = bl + box_size
            box = ui.Box(parent = self.screen,
                         pos    = bl,
                         tr     = tr,
                         colour = (0.4,0.4,0.4,1),extra = 1)
            self.selected_coords.append( (Point(bl.x,bl.y-0.2*box_height),Point(tr.x,bl.y-0.05*box_height)) )
            self.screen.slots.append(box)
        self.items = [item for item in items][:len(self.screen.slots)]
        if len(items) < len(self.screen.slots):
            self.items += [None]*(len(self.screen.slots)-len(items))
        self.SetSelected(0)
        self.screen.Disable()
        self.num_items = 0

    def SetScreen(self):
        self.screen.Enable()
        for item in self.items:
            if item:
                item.Enable()
        self.parent.computer = self
        self.current_key = None

    def SetSelected(self,n):
        if n < 0:
            n = 0
        if n > len(self.screen.slots):
            n = len(self.screen.slots)
        self.selected = n
        bl,tr = self.selected_coords[self.selected]
        self.screen.selected.bottom_left = bl
        self.screen.selected.top_right = tr
        self.screen.selected.UpdatePosition()
        item = self.items[self.selected]
        if item:
            name = item.name
        else:
            name = 'Empty'
        print 'name',name
        self.screen.current_name.SetText(name,(0,0,0,1))

    def KeyDown(self,key):
        if key in (pygame.K_ESCAPE,):
            return
        if key >= pygame.K_KP0 and key <= pygame.K_KP9:
            key -= (pygame.K_KP0 - pygame.K_0)

        self.current_key = key
        if key == pygame.K_TAB:
            return
        elif key == pygame.K_RIGHT:
            #do this in the same row
            row_pos = self.selected%self.width
            if row_pos+1 < self.width:
                self.SetSelected(self.selected + 1)
        elif key == pygame.K_LEFT:
            row_pos = self.selected%self.width
            if row_pos != 0:
                self.SetSelected(self.selected - 1)
        elif key == pygame.K_UP:
            col_pos = self.height-1-(self.selected/self.width)
            if col_pos + 1 < self.height:
                self.SetSelected(self.selected - self.width)
        elif key == pygame.K_DOWN:
            col_pos = self.height-1-(self.selected/self.width)
            if col_pos != 0:
                self.SetSelected(self.selected + self.width)
        elif key == pygame.K_RETURN:
            item = self.items[self.selected]
            if item:
                item.Describe()
        
    def AdjustSelected(self,diff):
        print ''.join(self.current)
        self.current[self.selected] = '%d' % ((int(self.current[self.selected]) + diff)%10)
        print ''.join(self.current)
        self.screen.combo.SetText(''.join(self.current),(1,0,0,1))

    def KeyUp(self,key):
        if key == pygame.K_ESCAPE or key == pygame.K_i:
            self.screen.Disable()
            for item in self.items:
                if item:
                    item.Disable()
            self.parent.CloseScreen()

        if self.current_key:
            self.current_key = None

    def Update(self,t):
        if not self.current_key:
            return
        elif self.current_key == pygame.K_TAB:
            self.current_key = None
            return

    def AddItem(self,item):
        self.items[self.num_items] = item
        item.SetCoords(self.screen.slots[self.num_items].absolute.bottom_left,self.screen.slots[self.num_items].absolute.top_right)
        self.screen.slots[self.num_items].Delete()
        self.num_items += 1
        self.SetSelected(self.selected)


class Player(Actor):
    texture = 'player'
    width = 9
    height = 16

    def __init__(self,*args,**kwargs):
        super(Player,self).__init__(*args,**kwargs)
        self.items = []
        self.inventory = Inventory(self.items,self)
        self.inventory.AddItem(RomanceNovel())


    # def AdjacentItem(self,item_type):
    #     current_tiles = set((self.pos + corner).to_int() for corner in self.corners)
    #     adjacent_tiles = set()
    #     for tile in current_tiles:
    #         #Only look in the tile above, let's restrict ourselves to only having computers pointing down
    #         for adjacent in (Point(0,1),):
    #             target = tile + adjacent
    #             try:
    #                 tile_data = self.map.data[target.x][target.y]
    #             except IndexError:
    #                 continue
    #             if isinstance(tile_data,item_type):
    #                 return tile_data

    # def AdjacentComputer(self):
    #     return self.AdjacentItem(game_view.Computer)

    # def AdjacentSwitch(self):
    #     return self.AdjacentItem(game_view.Switch)

    def AdjacentActor(self):
        for actor in self.map.actors:
            if actor is self:
                continue
            if (actor.pos - self.pos).SquareLength() < 2:
                return actor

    def AddItem(self,item):
        self.inventory.AddItem(item)
