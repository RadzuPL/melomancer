"""Just enough of discord.py to import app.player and run the player and mixer tests where it cannot be installed.

FfmpegPCMAudio is real (it starts ffmpeg), the rest are empty shells. Never put this directory on the path of the real
test run (CI): it would shadow discord.py. See scripts/dev/README.md.
"""
import subprocess, shlex
__version__ = "stub"
class DiscordException(Exception): ...
class Forbidden(DiscordException): ...
class LoginFailure(DiscordException): ...
class Guild: ...
class VoiceChannel: ...
class VoiceClient: ...
class Intents:
    @staticmethod
    def default(): return None
class Client:
    def __init__(self, intents=None): ...
class AudioSource:
    def read(self): raise NotImplementedError
    def is_opus(self): return False
    def cleanup(self): ...
class FFmpegPCMAudio(AudioSource):
    def __init__(self, source, *, before_options=None, options=None):
        args = ["ffmpeg", "-nostdin"]
        if before_options: args += shlex.split(before_options)
        args += ["-i", source]
        if options: args += shlex.split(options)
        args += ["-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "warning", "pipe:1"]
        self._process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._stdout = self._process.stdout
    def read(self):
        data = self._stdout.read(3840)
        return data if len(data) == 3840 else b""
    def cleanup(self):
        self._process.kill(); self._process.communicate()
