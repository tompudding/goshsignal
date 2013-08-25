from OpenGL.GL import *
import random,numpy,cmath,math,pygame
import hashlib
import string
import sqlite3
import modes

import ui,globals,drawing,os,copy
from globals.types import Point

class Path(object):
    def __init__(self,path,keepRelative = False):
        parts = []
        escaped = False
        current = []
        for i,char in enumerate(path):
            if char == '\0':
                break
            if escaped:
                current.append(char)
                escaped = False
            if char == '\\':
                escaped = True
                continue
            if char == '/':
                if current == []:
                    continue
                parts.append(''.join(current))
                current = []
                continue
            current.append(char)
        filename = ''.join(current)
        if filename == '':
            try:
                filename = parts.pop()
            except IndexError:
                #It's the root dir
                filename = '/'
        
        self.filename = filename
        parts.append(filename)
        self.parts = []
        for part in parts:
            if not keepRelative and part == '..':
                try:
                    self.parts.pop()
                except IndexError:
                    pass
                continue
            if part == '.':
                continue
            self.parts.append(part)
        if self.parts == []:
            self.parts = ['/']
            self.filename = '/'
        elif self.filename == '..':
            self.filename = self.parts[-1]
        self.parts = tuple(self.parts)

    def Add(self,extra):
        return Path('/' + '/'.join(self.parts + (extra,)))

    def Extend(self,path):
        return Path('/' + '/'.join(self.parts + path.parts))

    def __hash__(self):
        return hash(self.parts)

    def format(self):
        if self.parts == ('/',):
            return '/'
        return '/' + '/'.join(self.parts)

class File(object):
    def __init__(self,path,data,handler):
        self.path = path
        self.data = data
        self.filename = self.path.filename
        self.handler = handler

    def lsformat(self):
        return '%5d  %s' % (len(self.data),self.filename)

class Directory(File):
    def __init__(self,path):
        super(Directory,self).__init__(path,None,None)
        self.files = []
        self.filename = self.path.filename

    def GetFile(self,name):
        for file in self.files:
            if name == file.filename:
                return file
        return None

    def AddFile(self,f):
        self.files.append(f)

    def lsformat(self):
        return '<dir>  %s' % self.filename

class FileSystemException(Exception):
    pass

class InvalidPath(FileSystemException):
    pass

class NoSuchFile(FileSystemException):
    pass

class FileSystem(object):
    def __init__(self,files):
        self.root = Directory(Path('/'))
        
        for path,(filename,handler) in files.iteritems():
            if filename != None:
                with open(filename,'rb') as f:
                    data = f.read()
            else:
                data = None
            path = Path(path)
            current_dir = self.root
            bad = False
            for part in path.parts[:-1]:
                f = current_dir.GetFile(part)
                if f and not isinstance(f,Directory):
                    #tried to use a file as a dir, skip this guy
                    bad = True
                if not f:
                    f = Directory(current_dir.path.Add(part))
                    current_dir.AddFile(f)
                current_dir = f
            if bad:
                continue
            if data == None:
                new_file = Directory(path)
            else:
                new_file = File(path,data,handler)
            current_dir.AddFile(new_file)
        d = self.root

    def GetFile(self,path):
        current_dir = self.root
        if len(path.parts) == 1 and path.filename == '/':
            return self.root
        for part in path.parts[:-1]:
            f = current_dir.GetFile(part)
            if f and not isinstance(f,Directory):
                raise InvalidPath()
            if not f:
                raise NoSuchFile()
            current_dir = f
        out = current_dir.GetFile(path.filename)
        if not out:
            raise NoSuchFile()
        return out

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
        self.text_buffer = ''
        self.last = 0
        
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
            
        self.cursor = Point(0,0)
        self.start = None
        
        self.AddMessage(self.GetBanner())

    def GetBanner(self):
        return self.Banner

    def GameOver(self):
        return False

    def StartMusic(self):
        pass

    def StopMusic(self):
        pass

    def Update(self,t):
        self.t = t
        if self.text_buffer:
            self.AddText(self.text_buffer[:100])
            self.text_buffer = self.text_buffer[100:]
            if not self.text_buffer:
                if not self.current_command:
                    self.AddKey(ord('$'),True)
                self.current_buffer = []
            return
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
        self.ClearScreen()

    def Enable(self):
        super(Emulator,self).Enable()
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                self.quads[x][y].Enable()

    def ClearScreen(self):
        for x in xrange(self.size.x):
            for y in xrange(self.size.y):
                globals.text_manager.SetLetterCoords(self.quads[x][y],' ')
        self.cursor = Point(0,0)

    def Dispatch(self,command):
        pass

    def AddTextBuffer(self,message):
        self.text_buffer = message

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
        if userInput and key == 3:
            if self.current_command:
                self.current_command = None
                self.AddTextBuffer('\n')
                return
            self.text_buffer = ''
            self.AddTextBuffer('\n')
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

def AlienSignal(t):
    char = ord('type import universe'[int((t%10)*2)])
    p = (t*math.pi)/10
    signal_level = math.sin(p)*math.cos(3*p)
    return signal_level*((float(char*2)/256)-1) 
 

class SignalComputer(Emulator):
    Banner = ''
    time_between = 500
    def __init__(self,*args,**kwargs):
        super(SignalComputer,self).__init__(*args,**kwargs)
        self.num_outputted = 0
    def Update(self,t):
        if self.start == None:
            self.start = t
        self.t = t
        if (self.t - self.last) > self.time_between:
            t = float(self.t)/1000
            message = 't=%5.2f : signal=%10.7f   ' % (t,AlienSignal(t))
            if (self.num_outputted%2) == 1:
                message += '\n'
            self.num_outputted += 1
            self.AddTextBuffer(message)
            self.last = self.t
        if self.text_buffer:
            self.AddText(self.text_buffer[:100])
            self.text_buffer = self.text_buffer[100:]
            if not self.text_buffer:
                self.current_buffer = []
            return
        #print self.t,self.start

    def StartMusic(self):
        pygame.mixer.music.load('beeps.ogg')
        pygame.mixer.music.play(-1)

    def StopMusic(self):
        pygame.mixer.music.stop()

    def ClearScreen(self):
        super(SignalComputer,self).ClearScreen()
        self.num_outputted = 0
    def AddKey(self,key,userInput = True,repeat = False):
        if userInput:
            return
        super(SignalComputer,self).AddKey(key,userInput,repeat)
    

class BashComputer(Emulator):
    def __init__(self,parent,gameview,computer,background,foreground):
        self.commands = {'ls'   : self.ls,
                         'cd'   : self.cd,
                         'pwd'  : self.pwd,
                         'cat'  : self.cat,
                         'file' : self.file,
                         'import' : self.import_function,
                         'strings' : self.strings}
        super(BashComputer,self).__init__(parent,gameview,computer,background,foreground)
        self.current_command = None
        self.file_sigs = {'ae1dbfcbb43c1a38a3c8114283a602487b69fcdf' : 'ELF 32-bit LSB executable, ARM, version 1 (SYSV), dynamically linked (uses shared libs), for GNU/Linux 2.6.26, BuildID[sha1]=0x35087c06ea71d4eff1d8e2536e96213e3bd99761, not stripped',
                          'e6eb713cd887bd0e253414d311cfb6b9f2707c2c' : 'ELF 32-bit LSB executable, ARM, version 1 (SYSV), dynamically linked (uses shared libs), for GNU/Linux 2.6.26, BuildID[sha1]=0x7f981e03f231371c5feaaeab28d9e23639e57cd3, stripped'}
        self.strings_sigs = {'ae1dbfcbb43c1a38a3c8114283a602487b69fcdf' : """/lib/ld-linux-armhf.so.3
__gmon_start__
libc.so.6
socket
puts
abort
stdin
tolower
fgets
memset
strcmp
__libc_start_main
GLIBC_2.4
This is my secret diary, enter the password:
morpheus
correct
Connecting to the diary server...
Bad password!
Error opening socket
""",
                             'e6eb713cd887bd0e253414d311cfb6b9f2707c2c' : """/lib/ld-linux-armhf.so.3
__gmon_start__
libc.so.6
socket
puts
abort
stdin
tolower
fgets
memset
strcmp
__libc_start_main
GLIBC_2.4
This is my secret diary, enter the password:
morpheus
correct
Connecting to the diary server...
Bad password!
Error opening socket
pudding@pudding-desktop:~/Projects/goshsignal$ strings ls
/lib/ld-linux-armhf.so.3
vbICw)
gII"
,crL
r~FX7
libselinux.so.1
__gmon_start__
_Jv_RegisterClasses
_init
fgetfilecon
freecon
lgetfilecon
_fini
librt.so.1
clock_gettime
libacl.so.1
acl_get_entry
acl_extended_file_nofollow
acl_get_tag_type
libgcc_s.so.1
__aeabi_unwind_cpp_pr0
libc.so.6
fflush
strcpy
__printf_chk
fnmatch
setlocale
mbrtowc
strncmp
strrchr
fflush_unlocked
dcgettext
getpwuid
closedir
__mempcpy_chk
getgrgid
error
signal
strncpy
mbstowcs
sigprocmask
__stack_chk_fail
iswprint
realloc
abort
_exit
program_invocation_name
strftime
__assert_fail
__ctype_get_mb_cur_max
isatty
getpwnam
calloc
strlen
sigemptyset
memset
localeconv
strstr
__errno_location
memcmp
mempcpy
__fxstat64
_setjmp
__fprintf_chk
sigaddset
getgrnam
wcswidth
stdout
fputc
fseeko64
memcpy
fclose
strtoul
malloc
raise
mbsinit
__lxstat64
nl_langinfo
opendir
__xstat64
__ctype_b_loc
getenv
__freading
stderr
wcwidth
ioctl
_obstack_newchunk
readlink
fileno
fwrite
gettimeofday
sigaction
__memcpy_chk
sigismember
__fpending
localtime
lseek64
strchr
iswcntrl
mktime
program_invocation_short_name
readdir64
wcstombs
__ctype_toupper_loc
__ctype_tolower_loc
__sprintf_chk
memmove
_obstack_begin
bindtextdomain
fwrite_unlocked
strcmp
__strtoull_internal
tcgetpgrp
__libc_start_main
dirfd
stpcpy
strcoll
__overflow
fputs_unlocked
free
__progname
__progname_full
__cxa_atexit
ld-linux-armhf.so.3
__stack_chk_guard
_edata
__bss_start
__bss_start__
__bss_end__
__end__
_end
GLIBC_2.4
ACL_1.2
ACL_1.0
GCC_3.5
=fff?
1	 f
3	 f
1	 f
3	 f
gfff
3	 f
3	 f
3	 f
sort_files
?pcdb-lswd
posix-
dev_ino_pop
main
sort_type != sort_version
ls.c
 %lu
%*lu 
target
%*s 
%s %*s 
%*s, %*s 
 -> 
cannot access %s
unlabeled
cannot read symbolic link %s
Try `%s --help' for more information.
Usage: %s [OPTION]... [FILE]...
List information about the FILEs (the current directory by default).
Sort entries alphabetically if none of -cftuvSUX nor --sort is specified.
Mandatory arguments to long options are mandatory for short options too.
  -a, --all                  do not ignore entries starting with .
  -A, --almost-all           do not list implied . and ..
      --author               with -l, print the author of each file
  -b, --escape               print C-style escapes for nongraphic characters
      --block-size=SIZE      scale sizes by SIZE before printing them.  E.g.,
                               `--block-size=M' prints sizes in units of
                               1,048,576 bytes.  See SIZE format below.
  -B, --ignore-backups       do not list implied entries ending with ~
  -c                         with -lt: sort by, and show, ctime (time of last
                               modification of file status information)
                               with -l: show ctime and sort by name
                               otherwise: sort by ctime, newest first
  -C                         list entries by columns
      --color[=WHEN]         colorize the output.  WHEN defaults to `always'
                               or can be `never' or `auto'.  More info below
  -d, --directory            list directory entries instead of contents,
                               and do not dereference symbolic links
  -D, --dired                generate output designed for Emacs' dired mode
  -f                         do not sort, enable -aU, disable -ls --color
  -F, --classify             append indicator (one of */=>@|) to entries
      --file-type            likewise, except do not append `*'
      --format=WORD          across -x, commas -m, horizontal -x, long -l,
                               single-column -1, verbose -l, vertical -C
      --full-time            like -l --time-style=full-iso
  -g                         like -l, but do not list owner
      --group-directories-first
                             group directories before files.
                               augment with a --sort option, but any
                               use of --sort=none (-U) disables grouping
  -G, --no-group             in a long listing, don't print group names
  -h, --human-readable       with -l, print sizes in human readable format
                               (e.g., 1K 234M 2G)
      --si                   likewise, but use powers of 1000 not 1024
  -H, --dereference-command-line
                             follow symbolic links listed on the command line
      --dereference-command-line-symlink-to-dir
                             follow each command line symbolic link
                             that points to a directory
      --hide=PATTERN         do not list implied entries matching shell PATTERN
                               (overridden by -a or -A)
      --indicator-style=WORD  append indicator with style WORD to entry names:
                               none (default), slash (-p),
                               file-type (--file-type), classify (-F)
  -i, --inode                print the index number of each file
  -I, --ignore=PATTERN       do not list implied entries matching shell PATTERN
  -k                         like --block-size=1K
  -l                         use a long listing format
  -L, --dereference          when showing file information for a symbolic
                               link, show information for the file the link
                               references rather than for the link itself
  -m                         fill width with a comma separated list of entries
  -n, --numeric-uid-gid      like -l, but list numeric user and group IDs
  -N, --literal              print raw entry names (don't treat e.g. control
                               characters specially)
  -o                         like -l, but do not list group information
  -p, --indicator-style=slash
                             append / indicator to directories
  -q, --hide-control-chars   print ? instead of non graphic characters
      --show-control-chars   show non graphic characters as-is (default
                             unless program is `ls' and output is a terminal)
  -Q, --quote-name           enclose entry names in double quotes
      --quoting-style=WORD   use quoting style WORD for entry names:
                               literal, locale, shell, shell-always, c, escape
  -r, --reverse              reverse order while sorting
  -R, --recursive            list subdirectories recursively
  -s, --size                 print the allocated size of each file, in blocks
  -S                         sort by file size
      --sort=WORD            sort by WORD instead of name: none -U,
                             extension -X, size -S, time -t, version -v
      --time=WORD            with -l, show time as WORD instead of modification
                             time: atime -u, access -u, use -u, ctime -c,
                             or status -c; use specified time as sort key
                             if --sort=time
      --time-style=STYLE     with -l, show times using style STYLE:
                             full-iso, long-iso, iso, locale, +FORMAT.
                             FORMAT is interpreted like `date'; if FORMAT is
                             FORMAT1<newline>FORMAT2, FORMAT1 applies to
                             non-recent files and FORMAT2 to recent files;
                             if STYLE is prefixed with `posix-', STYLE
                             takes effect only outside the POSIX locale
  -t                         sort by modification time, newest first
  -T, --tabsize=COLS         assume tab stops at each COLS instead of 8
  -u                         with -lt: sort by, and show, access time
                               with -l: show access time and sort by name
                               otherwise: sort by access time
  -U                         do not sort; list entries in directory order
  -v                         natural sort of (version) numbers within text
  -w, --width=COLS           assume screen width instead of current value
  -x                         list entries by lines instead of by columns
  -X                         sort alphabetically by entry extension
  -Z, --context              print any SELinux security context of each file
  -1                         list one file per line
      --help     display this help and exit
      --version  output version information and exit
SIZE may be (or may be an integer optionally followed by) one of following:
KB 1000, K 1024, MB 1000*1000, M 1024*1024, and so on for G, T, P, E, Z, Y.
Using color to distinguish file types is disabled both by default and
with --color=never.  With --color=auto, ls emits color codes only when
standard output is connected to a terminal.  The LS_COLORS environment
variable can change the settings.  Use the dircolors command to set it.
Exit status:
 0  if OK,
 1  if minor problems (e.g., cannot access subdirectory),
 2  if serious trouble (e.g., cannot access command-line argument).
Report %s bugs to %s
bug-coreutils@gnu.org
%s home page: <%s>
GNU coreutils
http://www.gnu.org/software/coreutils/
General help using GNU software: <http://www.gnu.org/gethelp/>
Report %s translation bugs to <http://translationproject.org/team/>
For complete documentation, run: info coreutils '%s invocation'
full-iso
vdir
locale
/usr/share/locale
QUOTING_STYLE
ignoring invalid value of environment variable QUOTING_STYLE: %s
LS_BLOCK_SIZE
BLOCK_SIZE
COLUMNS
ignoring invalid width in environment variable COLUMNS: %s
TABSIZE
ignoring invalid tab size in environment variable TABSIZE: %s
abcdfghiklmnopqrstuvw:xABCDFGHI:LNQRST:UXZ1
invalid line width: %s
invalid tab size: %s
--sort
--time
--format
--color
--indicator-style
--quoting-style
Richard M. Stallman
David MacKenzie
*=>@|
TIME_STYLE
invalid time style format %s
time style
%Y-%m-%d %H:%M:%S.%N %z
%Y-%m-%d %H:%M
%Y-%m-%d 
%m-%d %H:%M
error initializing month strings
LS_COLORS
unrecognized prefix: %s
unparsable value for LS_COLORS environment variable
sizeof (struct dev_ino) <= __extension__ ({ struct obstack const *__o = (&dev_ino_obstack); (unsigned) (__o->next_free - __o->object_base); })
found
cannot open directory %s
cannot determine device and inode of %s
%s: not listing already-listed directory
reading directory %s
closing directory %s
total
//DIRED//
//SUBDIRED//
//DIRED-OPTIONS// --quoting-style=%s
hash_get_n_entries (active_dir_set) == 0
01;34
01;36
01;35
01;33
01;32
37;41
30;43
37;44
34;42
30;42
30;41
escape
directory
dired
full-time
group-directories-first
human-readable
inode
numeric-uid-gid
no-group
hide-control-chars
reverse
size
width
almost-all
ignore-backups
classify
file-type
dereference-command-line
dereference-command-line-symlink-to-dir
hide
ignore
indicator-style
dereference
literal
quote-name
quoting-style
recursive
format
show-control-chars
sort
tabsize
time
time-style
color
block-size
context
author
help
version
none
extension
atime
access
ctime
status
verbose
long
commas
horizontal
across
vertical
single-column
always
force
never
auto
if-tty
slash
%b %e  %Y
%b %e %H:%M
long-iso
8.13
invalid argument %s for %s
ambiguous argument %s for %s
Valid arguments are:
  - `%s'
, `%s'
write error
%s: %s
POSIX
# entries:         %lu
# buckets:         %lu
# buckets used:    %lu (%.2f%%)
max bucket length: %lu
KMGTPEZY
%.0Lf
%.1Lf
BLOCKSIZE
POSIXLY_CORRECT
eEgGkKmMpPtTyYzZ0
A NULL argv[0] was passed through an exec system call.
/.libs/
shell
shell-always
c-maybe
clocale
%m/%d/%y
%Y-%m-%d
%H:%M
%H:%M:%S
%s (%s) %s
%s %s
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>.
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
Written by %s.
Written by %s and %s.
Written by %s, %s, and %s.
Written by %s, %s, %s,
and %s.
Written by %s, %s, %s,
%s, and %s.
Written by %s, %s, %s,
%s, %s, and %s.
Written by %s, %s, %s,
%s, %s, %s, and %s.
Written by %s, %s, %s,
%s, %s, %s, %s,
and %s.
Written by %s, %s, %s,
%s, %s, %s, %s,
%s, and %s.
Written by %s, %s, %s,
%s, %s, %s, %s,
%s, %s, and others.
Report bugs to: %s
Copyright %s %d Free Software Foundation, Inc.
memory exhausted
xstrtoul
0 <= strtol_base && strtol_base <= 36
xstrtol.c
invalid %s%s argument `%s'
invalid suffix in %s%s argument `%s'
%s%s argument `%s' too large
xstrtoumax
%s: option '%s' is ambiguous; possibilities:
 '--%s'
%s: option '--%s' doesn't allow an argument
%s: option '%c%s' doesn't allow an argument
%s: option '--%s' requires an argument
%s: unrecognized option '--%s'
%s: unrecognized option '%c%s'
%s: invalid option -- '%c'
%s: option requires an argument -- '%c'
%s: option '-W %s' is ambiguous
%s: option '-W %s' doesn't allow an argument
%s: option '-W %s' requires an argument
"""}
        self.cwd = Path('/')
    def Dispatch(self,message):
        if self.current_command:
            output = self.current_command(message,initial = False)
            self.AddTextBuffer(output)
        else:
            self.Handle(message)
        #self.AddKey(ord('$'),True)

    def Handle(self,message):
        parts = message.strip().split()
        output = None
        if not parts:
            self.AddText('$')
            return
        try:
            command = self.commands[parts[0]]
        except KeyError:
            #It's not a built in command, maybe it's a path to a command
            try:
                file = self.GetFileData(message.strip().split()[0])
            except FileSystemException as e:
                self.AddTextBuffer('%s : bad command\n' % message)
                return
            if file.handler:
                output = file.handler(parts[1:])
                self.AddTextBuffer(output)
            return
        output = command(parts[1:])
        self.AddTextBuffer(output)

    def ls(self,args):
        #ignore any switched
        args = [arg for arg in args if arg[0] != '-']
        
        if len(args) == 0:
            path = self.cwd
        else:
            path = Path(args[0])
        try:
            file = self.FileSystem.GetFile(path)
        except InvalidPath:
            return 'Invalid Path\n'
        except NoSuchFile:
            return 'NoSuchFile\n'

        if isinstance(file,Directory):
            out = ['%s:' % file.path.format()]
            for f in file.files:
                out.append(f.lsformat())
            return '\n'.join(out) + '\n'
        else:
            return file.lsformat() + '\n'

    def cd(self,args):
        args = [arg for arg in args if arg[0] != '-']
        if len(args) == 0:
            self.cwd = self.home_path
            return '\n'
        path = args[0]
        if path[0] == '/':
            #absolute
            path = Path(path)
        else:
            path = self.cwd.Extend(Path(path,keepRelative = True))

        try:
            file = self.FileSystem.GetFile(path)
        except InvalidPath:
            return 'Invalid Path\n'
        except NoSuchFile:
            return 'No such file\n'

        self.cwd = path
        return '\n'

    def pwd(self,args):
        return self.cwd.format() + '\n'
                        
    def GetFileData(self,path):
        if path[0] == '/':
            path = Path(path)
        else:
            try:
                path = self.cwd.Extend(Path(path,keepRelative = True))
            except:
                return 'invalid path\n'
        
        try:
            file = self.FileSystem.GetFile(path)
        except InvalidPath:
            raise FileSystemException('Invalid Path\n')
        except NoSuchFile:
            raise FileSystemException('NoSuchFile\n')
        if isinstance(file,Directory):
            raise FileSystemException('%s: Is a directory\n' % file.filename)
        return file

    def cat(self,args):
        args = [arg for arg in args if arg[0] != '-']
        if len(args) == 0:
            return '\n'
        path = args[0]
        try:
            file = self.GetFileData(path)
        except FileSystemException as e:
            return 'cat: ' + str(e)
        if file.filename == 'notes':
            globals.sounds.PlayVoice(globals.sounds.holy)

        return '%s\n' % file.data

    def file(self,args):
        args = [arg for arg in args if arg and arg[0] != '-']
        if len(args) == 0:
            return '\n'
        path = args[0]
        try:
            file = self.GetFileData(path)
        except FileSystemException as e:
            return 'file: ' + str(e)

        h = hashlib.sha1(file.data).hexdigest()
        try:
            out = self.file_sigs[h]
        except KeyError:
            out = 'data'
        return '%s: %s\n' % (file.filename,out)

    def strings(self,args):
        args = [arg for arg in args if arg and arg[0] != '-']
        if len(args) == 0:
            return '\n'
        path = args[0]
        try:
            file = self.GetFileData(path)
        except FileSystemException as e:
            return 'strings: ' + str(e)

        h = hashlib.sha1(file.data).hexdigest()
        try:
            out = self.strings_sigs[h]
        except KeyError:
            out = 'data'
        return '%s: %s\n' % (file.filename,out)

    def import_function(self,args):
        if len(args) == 1 and args[0] == 'universe':
            globals.game_view.OpenDish()
            globals.sounds.dooropen.play()
            return 'Insufficient signal strength. Opening dish control...\n'
        return 'import: bad command\n'

        
class DomsComputer(BashComputer):
    Banner = 'This is Dom\'s private diary computer : keep your nose out!\n$'
    home_path = Path('/home/dom')

    def __init__(self,*args,**kwargs):
        self.FileSystem = FileSystem({'/home/dom/edit_diary':('edit_diary',self.edit_diary),
                                      '/usr/share'          : (None,None),
                                      '/tmp'                : (None,None),
                                      '/var/log'            : (None,None),
                                      '/bin/ls'             : ('ls',self.ls)})
        super(DomsComputer,self).__init__(*args,**kwargs)

    def edit_diary(self,args,initial = True):
        if initial:
            self.current_command = self.edit_diary
            return "This is my secret diary, enter the password:\n"
        else:
            if args == 'morpheus':
                out = 'correct!\nThe locker combination is 2212\n'
            else:
                out = 'Bad password!\n'
            self.current_command = None
            return out
            


class LabComputer(BashComputer):
    Banner = 'Welcome to the Jodrell Bank Lab computer. Please enter your credentials!\nUsername:'
    home_path = Path('/home/lab')
    users = {'dom'       : ('trinity' , Path('/home/dom')),
             'admin'     : ('admin'   , Path('/home/admin')),
             'root'      : ('toor'    , Path('/root')),
             'drbabbage' : ('cabbage' , Path('/home/drbabbage')),
             'guest'     : ('password', Path('/home/guest')),
             'anonymous' : (''        , Path('/home/anonymous'))}

    def __init__(self,*args,**kwargs):
        self.FileSystem = FileSystem({'/usr/share'               : (None,None),
                                      '/tmp'                     : (None,None),
                                      '/var/log'                 : (None,None),
                                      '/home/dom/'               : (None,None),
                                      '/home/admin'              : (None,None),
                                      '/home/drbabbage/notes'    : ('babbage_notes',None),
                                      '/home/drbabbage/analysis' : ('babbage_analysis',self.analysis),
                                      '/login'                   : (None,None),
                                      '/home/guest'              : (None,None),
                                      '/home/anonymous'          : (None,None),
                                      '/home/guest'              : (None,None),
                                      '/root'                    : (None,None),
                                      '/bin/ls'                  : ('ls',self.ls)})
        super(LabComputer,self).__init__(*args,**kwargs)
        self.current_command = self.login
        self.login_username = ''
        self.login_mode = 0
        self.cwd = Path('/login')

    def login(self,args,initial = True):
        print 'lm',self.login_mode
        if self.login_mode == 0:
            #it's a username
            self.login_username = args
            if self.login_username not in self.users:
                return 'Invalid username\nUsername: '
            self.login_mode = 1
            return '%s, enter your password: ' % args
        else:
            self.login_mode = 0
            try:
                password,homedir = self.users[self.login_username]
            except KeyError:
                return 'error\n'
            if args == password:
                self.current_command = None
                self.home_path = self.cwd = homedir
                return 'Welcome %s\n' % self.login_username
            else:
                self.login_mode = 0
                return 'Invalid password\nUsername: '
            
    def analysis(self,args,initial = True):
        return 'analyse!\n'


class FinalComputer(BashComputer):
    Banner = 'Greetings human, you know what to type\n$'
    home_path = Path('/home/dom')

    def __init__(self,*args,**kwargs):
        self.FileSystem = FileSystem({'/usr/share'          : (None,None),
                                      '/tmp'                : (None,None),
                                      '/var/log'            : (None,None),
                                      '/bin/ls'             : ('ls',self.ls)})
        self.end = None
        super(FinalComputer,self).__init__(*args,**kwargs)

    def StartMusic(self):
        pygame.mixer.music.load('beeps.ogg')
        pygame.mixer.music.play(-1)

    def StopMusic(self):
        pygame.mixer.music.stop()

    def import_function(self,args):
        if len(args) == 1 and args[0] == 'universe':
            print 'finished!'
            globals.game_view.GameOver()
            return 'Nobody can be told exactly what it is, you have to see it for yourself...\n'
            #globals.game_view.OpenDish()
            #return 'Insufficient signal strength. Opening dish control...\n'
        return 'import: bad command\n'
