from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import sys

class Mode(object):
    """ Abstract base class to represent game modes """
    def __init__(self,parent):
        self.parent = parent
    
    def KeyDown(self,key):
        pass
    
    def KeyUp(self,key):
        pass

    def MouseButtonDown(self,pos,button):
        return False,False

    def Update(self,t):
        pass

class TitleStages(object):
    STARTED  = 0
    COMPLETE = 1
    TEXT     = 2
    SCROLL   = 3
    WAIT     = 4
    ZOOM     = 5

class Titles(Mode):
    blurb = "The GOSH signal"
    def __init__(self,parent):
        self.parent          = parent
        self.start           = pygame.time.get_ticks()
        self.stage           = TitleStages.STARTED
        self.handlers        = {TitleStages.STARTED  : self.Startup,
                                TitleStages.COMPLETE : self.Complete}
        globals.sounds.PlayVoice(globals.sounds.intro)
        #bl = self.parent.GetRelative(Point(0,0))
        #tr = bl + self.parent.GetRelative(globals.screen)
        bl = Point(0.3,0)
        tr = Point(1,0.6)
        self.blurb_text = ui.TextBox(parent = globals.screen_root,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                     colour = (0,1,0,1),
                                     scale  = 4)
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,1))
        self.backdrop.Enable()

    def KeyDown(self,key):
        self.stage = TitleStages.COMPLETE

    def Update(self,t):        
        self.elapsed = t - self.start
        self.stage = self.handlers[self.stage](t)
        if self.stage == TitleStages.COMPLETE:
            self.parent.mode = self.parent.game_mode = GameMode(self.parent)
            self.parent.viewpos.Follow(globals.time,self.parent.map.player)
            #self.parent.StartMusic()

    def Complete(self,t):
        self.backdrop.Delete()
        self.blurb_text.Delete()
        #self.parent.mode = GameOver(self.parent)
        return TitleStages.COMPLETE

    def Startup(self,t):
        return TitleStages.STARTED

class GameOver(Mode):
    blurb = "Well done player, you've realised the true nature of the universe and re-united with your friends in the outer-verse. Or something. Hooray!"
    def __init__(self,parent):
        self.parent          = parent
        self.blurb           = self.blurb
        self.blurb_text      = None
        self.handlers        = {TitleStages.ZOOM   : self.Zoom,
                                TitleStages.TEXT   : self.TextDraw,
                                TitleStages.SCROLL : self.Wait,
                                TitleStages.WAIT   : self.Wait}
        self.backdrop        = ui.Box(parent = globals.screen_root,
                                      pos    = Point(0,0),
                                      tr     = Point(1,1),
                                      colour = (0,0,0,1))
        
        bl = Point(0,0)
        tr = Point(1,0.7)
        self.blurb_text = ui.TextBox(parent = globals.screen_root,
                                     bl     = bl         ,
                                     tr     = tr         ,
                                     text   = self.blurb ,
                                     textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                     scale  = 3)

        self.start = None
        self.blurb_text.EnableChars(0)
        self.stage = TitleStages.ZOOM
        self.played_sound = False
        self.skipped_text = False
        self.letter_duration = 20
        self.continued = False
        #pygame.mixer.music.load('end_fail.mp3')
        #pygame.mixer.music.play(-1)

    def Update(self,t):
        if self.start == None:
            self.start = t
        self.elapsed = t - self.start
        self.stage = self.handlers[self.stage](t)
        if self.stage == TitleStages.COMPLETE:
            raise sys.exit('Come again soon!')

    def Wait(self,t):
        return self.stage

    def Zoom(self,t):
        if globals.zoom_scale == None:
            globals.zoom_scale = 1.0
            globals.sounds.fadein.play()
        globals.zoom_scale = 1+(10*(float(self.elapsed)/3000))
        if self.elapsed > 3000:
            print 'done zoom'
            globals.sounds.fadein.stop()
            globals.sounds.explode.play()
            globals.game_view.computer.screen.Disable()
            globals.game_view.CloseScreen()
            globals.zoom_scale = None
            self.start = t
            return TitleStages.TEXT
        return self.stage

    def SkipText(self):
        if self.blurb_text:
            self.skipped_text = True
            self.blurb_text.EnableChars()

    def TextDraw(self,t):
        if not self.skipped_text:
            if self.elapsed < (len(self.blurb_text.text)*self.letter_duration) + 2000:
                num_enabled = int(self.elapsed/self.letter_duration)
                self.blurb_text.EnableChars(num_enabled)
            else:
                self.skipped_text = True
        elif self.continued:
            return TitleStages.COMPLETE
        return TitleStages.TEXT


    def KeyDown(self,key):
        #if key in [13,27,32]: #return, escape, space
        if not self.skipped_text:
            self.SkipText()
        else:
            self.continued = True

    def MouseButtonDown(self,pos,button):
        self.KeyDown(0)
        return False,False

class GameMode(Mode):
    speed = 8
    direction_amounts = {pygame.K_LEFT  : Point(-0.01*speed, 0.00),
                         pygame.K_RIGHT : Point( 0.01*speed, 0.00),
                         pygame.K_UP    : Point( 0.00, 0.01*speed),
                         pygame.K_DOWN  : Point( 0.00,-0.01*speed)}
    class KeyFlags:
        LEFT  = 1
        RIGHT = 2
        UP    = 4
        DOWN  = 8
    keyflags = {pygame.K_LEFT  : KeyFlags.LEFT,
                pygame.K_RIGHT : KeyFlags.RIGHT,
                pygame.K_UP    : KeyFlags.UP,
                pygame.K_DOWN  : KeyFlags.DOWN}
    """This is a bit of a cheat class as I'm rushed. Just pass everything back"""
    def __init__(self,parent):
        self.parent            = parent
        self.parent.info_box.Enable()
        self.keydownmap = 0

    def KeyDown(self,key):
        if self.parent.computer:
            return self.parent.computer.KeyDown(key)
        if key in self.direction_amounts:
            self.keydownmap |= self.keyflags[key]
            self.parent.player_direction += self.direction_amounts[key]

    def KeyUp(self,key):
        if key in self.direction_amounts and (self.keydownmap & self.keyflags[key]):
            self.keydownmap &= (~self.keyflags[key])
            self.parent.player_direction -= self.direction_amounts[key]
        if self.parent.computer:
            return self.parent.computer.KeyUp(key)

        elif key == pygame.K_SPACE:
            facing = self.parent.map.player.Facing()
            if not facing:
                return
            print facing
            if (facing.x,facing.y) in self.parent.map.object_cache:
                obj = self.parent.map.object_cache[(facing.x,facing.y)]
                obj.Interact(self.parent.map.player)
                return

            try:
                tile = self.parent.map.data[facing.x][facing.y]
            except IndexError:
                return
            tile.Interact(self.parent.map.player)
        elif key == pygame.K_i:
            self.parent.map.player.inventory.SetScreen()

                
