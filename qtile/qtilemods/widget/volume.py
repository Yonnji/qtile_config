import re
import os
import subprocess

from libqtile import widget, images
from libqtile.command.base import expose_command
from libqtile.log_utils import logger
from libqtile.widget import base

from .mixins import IconTextMixin


class Volume(IconTextMixin, base.PaddingMixin, widget.Volume):
    icon_names = (
            'audio-volume-high-symbolic',
            'audio-volume-medium-symbolic',
            'audio-volume-low-symbolic',
            'audio-volume-muted-symbolic',
    )

    def __init__(self, **config):
        # self.foreground = config.get('foreground', '#ffffff')
        self.icon_ext = config.get('icon_ext', '.png')
        self.icon_size = config.get('icon_size', 0)
        self.icon_spacing = config.get('icon_spacing', 0)
        self.images = {}
        self.current_icon = 'audio-volume-muted-symbolic'

        base._TextBox.__init__(self, '', **config)
        self.add_defaults(widget.Volume.defaults)
        self.volume = 0
        self.add_callbacks({
            'Button1': self.mute,
            'Button2': self.run_app,
            'Button3': self.run_app,
            'Button4': self.increase_vol,
            'Button5': self.decrease_vol,
        })

        self.add_defaults(base.PaddingMixin.defaults)
        self.channel = config.get('channel', '@DEFAULT_AUDIO_SINK@')
        self.check_mute_string = config.get('check_mute_string', '[MUTED]')

    def create_amixer_command(self, *args):
        cmd = ['wpctl']

        for arg in args:
            if arg.startswith('-'):
                continue
            elif arg == 'sget':
                cmd.append('get-volume')
            elif arg == 'sset':
                if 'toggle' in args:
                    cmd.append('set-mute')
                else:
                    cmd.append('set-volume')
            else:
                cmd.append(arg)

        return subprocess.list2cmdline(cmd)

    def get_volume(self):
        try:
            if self.get_volume_command is not None:
                get_volume_cmd = self.get_volume_command
            else:
                get_volume_cmd = self.create_amixer_command('sget', self.channel)

            mixer_out = subprocess.getoutput(get_volume_cmd)
        except subprocess.CalledProcessError:
            return -1

        check_mute = mixer_out
        if self.check_mute_command:
            check_mute = subprocess.getoutput(self.check_mute_command)

        if self.check_mute_string in check_mute:
            return -1

        volgroups = mixer_out and mixer_out.split(' ')
        if volgroups:
            return int(float(volgroups[1]) * 100)
        else:
            return -1

    def get_icon_key(self, volume):
        if volume <= 0:
            mode = 'muted'
        elif volume < 33:
            mode = 'low'
        elif volume < 66:
            mode = 'medium'
        else:
            mode = 'high'

        return f'audio-volume-{mode}-symbolic'

    def calculate_length(self):
        return (
            super().calculate_length() +
            self.icon_size + self.icon_spacing)

    @expose_command()
    def increase_vol(self):
        if self.volume < 100:
            super().increase_vol()
        self.update()

    @expose_command()
    def decrease_vol(self):
        if self.volume > 0:
            super().decrease_vol()
        self.update()

    @expose_command()
    def mute(self):
        super().mute()
        self.update()

    def update(self):
        vol = self.get_volume()
        if vol != self.volume:
            self.volume = vol
            self.text = ''
            # self.text = f'{vol}%'

            icon = self.get_icon_key(vol)
            if icon != self.current_icon:
                self.current_icon = icon

            self.draw()

        self.timeout_add(self.update_interval, self.update)