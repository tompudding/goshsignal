from OpenGL.GL import *
import random,numpy,cmath,math,pygame
import hashlib
import string
import sqlite3

import ui,globals,drawing,os,copy
from globals.types import Point

class Emulator(ui.UIElement):
    cursor_char     = chr(0x9f)
    cursor_interval = 500
    def __init__(self,parent,gameview,computer,background,foreground):
        bl = Point(13,13).to_float()/parent.absolute.size
        tr = (Point(1,1) - bl)
        super(Emulator,self).__init__(parent,bl,tr)
        self.background_colour = background
        self.foreground_colour = foreground
        self.scale = 3
        self.gameview = gameview
        self.computer = computer
        
        self.size = (self.absolute.size/(globals.text_manager.GetSize(' ',self.scale).to_float())).to_int()
        self.quads = []
        
        for x in xrange(self.size.x):
            col = []
            for y in xrange(self.size.y):
                q = globals.text_manager.Letter(' ',drawing.texture.TextTypes.SCREEN_RELATIVE,self.foreground_colour)
                bl = (Point(x,self.size.y - 1 - y).to_float())/self.size
                tr = (Point(x+1,self.size.y - y).to_float())/self.size
                q.SetVertices(self.GetAbsolute(bl),self.GetAbsolute(tr),drawing.constants.DrawLevels.ui + self.level + 1)
                col.append(q)
            self.quads.append(col)
        self.cursor_flash = None
        self.cursor_flash_state = False
        self.current_buffer = []
            
        self.cursor_entry = Point(0,0)
        self.cursor_view  = Point(0,0)
        self.cursor = self.cursor_entry
        self.saved_buffer = []
        
        self.AddMessage(self.GetBanner())

    def GetBanner(self):
        return self.Banner

    def GameOver(self):
        return False

    def Update(self,t):
        self.t = t
        if self.cursor_flash == None:
            self.cursor_flash = t
            return
        if t - self.cursor_flash > self.cursor_interval:
            self.cursor_flash = t
            if not self.cursor_flash_state:
                #Turn the cursor on
                self.FlashOn()
            else:
                self.FlashOff()

    def FlashOn(self):
        old_letter = self.quads[self.cursor.x][self.cursor.y].letter
        globals.text_manager.SetLetterCoords(self.quads[self.cursor.x][self.cursor.y],self.cursor_char)
        self.quads[self.cursor.x][self.cursor.y].letter = old_letter
        self.cursor_flash_state = True

    def FlashOff(self):
        l = self.quads[self.cursor.x][self.cursor.y]
        globals.text_manager.SetLetterCoords(l,l.letter)
        self.cursor_flash_state = False

    def Disable(self):
        super(Emulator,self).Disable()
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                self.quads[x][y].Disable()

    def Enable(self):
        super(Emulator,self).Enable()
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                self.quads[x][y].Enable()

    def Dispatch(self,command):
        #print 'Got command : ',command
        pass

    def AddText(self,text):
        for char in text:
            if char == '\n':
                key = pygame.K_RETURN
            else:
                key = ord(char)
            self.AddKey(key,False)

    def AddMessage(self,message,fail = None):
        if fail == True:
            globals.sounds.access_denied.play()
        elif fail == False:
            globals.sounds.access_granted.play()
        for char in '\n' + message:
            if char == '\n':
                key = pygame.K_RETURN
            else:
                key = ord(char)
            self.AddKey(key,False)

    def SaveEntryBuffer(self):
        self.saved_buffer = []
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                self.saved_buffer.append(self.quads[x][y].letter)
        
    def RestoreEntryBuffer(self):
        pos = 0
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                globals.text_manager.SetLetterCoords(self.quads[x][y],self.saved_buffer[pos])
                pos += 1

    def SetViewBuffer(self):
        #Just set the text from the view buffer
        numlines = 0
        for y,line in enumerate(self.viewlines[self.viewpos:self.viewpos + self.size.y]):
            numchars = 0
            for x,char in enumerate(line[:self.size.x]):
                globals.text_manager.SetLetterCoords(self.quads[x][y],char)
                numchars += 1
            for x in xrange(numchars,self.size.x):
                globals.text_manager.SetLetterCoords(self.quads[x][y],' ')
            numlines += 1
        for y in xrange(numlines,self.size.y):
            for x in xrange(self.size.x):
                globals.text_manager.SetLetterCoords(self.quads[x][y],' ')

    def AddKey(self,key,userInput = True,repeat = False):
        if userInput and not repeat:
            #for sound in globals.sounds.typing_sounds:
            #    sound.stop()
            #print dir(globals.sounds.typing_sounds[0])
            #random.choice(globals.sounds.typing_sounds).play()
            pass

        #Handle special keys
        self.FlashOff()
        if key == pygame.K_RETURN:
            command = ''.join(self.current_buffer)
            #Move to the start of the next line
            for i in xrange(self.size.x - self.cursor.x):
                self.AddKey(ord(' '),userInput)
            if userInput:
                self.Dispatch(command)
            self.current_buffer = []
        elif key == pygame.K_BACKSPACE:
            if len(self.current_buffer) == 0:
                #ignore the backspace
                return
            if userInput:
                self.current_buffer.pop()
            if self.cursor.x == 0:
                if self.cursor.y == 0:
                    return
                self.cursor.x = self.size.x - 1
                self.cursor.y -= 1
            else:
                self.cursor.x -= 1
            c = Point(self.cursor.x,self.cursor.y)
            self.AddKey(ord(' '),userInput)
            self.current_buffer.pop() #remove the space we just added
            self.cursor.x = c.x
            self.cursor.y = c.y
            return
        try:
            key = chr(key)
        except ValueError:
            return

        if not globals.text_manager.HasKey(key):
            return
        globals.text_manager.SetLetterCoords(self.quads[self.cursor.x][self.cursor.y],key)

        self.cursor.x += 1
        if self.cursor.x >= self.size.x:
            self.cursor.x = 0
            self.cursor.y += 1
        if self.cursor.y >= self.size.y:
            #Move everything up
            for x in xrange(self.size.x):
                for y in xrange(self.size.y):
                    globals.text_manager.SetLetterCoords(self.quads[x][y],self.quads[x][y+1].letter if y+1 < self.size.y else ' ')
            self.cursor.y = self.size.y - 1
        if userInput:
            self.current_buffer.append(key)

class BashComputer(Emulator):
    Banner = 'hi\n$'
    def __init__(self,parent,gameview,computer,background,foreground):
        self.commands = {'ls' : self.ls}
        super(BashComputer,self).__init__(parent,gameview,computer,background,foreground)
    def Dispatch(self,message):
        self.Handle(message)
        self.AddKey(ord('$'),True)

    def Handle(self,message):
        parts = message.split(' ')
        try:
            command = self.commands[parts[0]]
        except KeyError:
            self.AddText('%s : command not found\n' % parts[0])
            return
        output = command(parts[1:])
        self.AddText(output)
        
    def ls(self,args):
        print args
        return '\n'.join('abcd') + '\n'
        
