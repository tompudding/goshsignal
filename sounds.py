import sys, pygame, glob, os

from pygame.locals import *
import pygame.mixer
import globals

pygame.mixer.init()


class Sounds(object):
    def __init__(self):
        self.typing_sounds = []
        self.voice_playing = None
        path = globals.pyinst.get_path()
        for filename in glob.glob(os.path.join(path, "*.ogg")):
            # print filename
            sound = pygame.mixer.Sound(filename)
            sound.set_volume(0.6)
            name = os.path.basename(os.path.splitext(filename)[0])
            setattr(self, name, sound)

    def PlayVoice(self, sound):
        if self.voice_playing:
            self.voice_playing.stop()
        self.voice_playing = sound
        sound.play()
