import cairocffi
import copy
import re
import os

from xdg.IconTheme import getIconPath

from libqtile import widget, images, qtile
from libqtile.log_utils import logger

from .mixins import AppMixin, IconTextMixin
from ..icon_theme import get_icon_path


class PinnedApp(object):
    def __init__(self, desktop, icon, cmd):
        self.desktop = desktop
        self.icon = icon
        self.cmd = cmd
        self.window = None

    def clone(self):
        return PinnedApp(desktop=self.desktop, icon=self.icon, cmd=self.cmd)

    def matches(self, window):
        win_classes = window.get_wm_class() or []

        if self.get_name() == window.name:
            return True

        if self.get_wm_class() and self.get_wm_class() in win_classes:
            return True

        for cl in win_classes:
            if self.get_name().lower().startswith(cl.lower()):
                return True

            if self.get_icon().lower().startswith(cl.lower()):
                return True

        return False

    def get_name(self):
        return self.desktop['Desktop Entry']['Name']

    def get_icon(self):
        return self.desktop['Desktop Entry']['Icon']

    def get_wm_class(self):
        if 'StartupWMClass' in self.desktop['Desktop Entry']:
            return self.desktop['Desktop Entry']['StartupWMClass']


class UnpinnedApp(object):
    def __init__(self, window):
        self.window = window


class Dock(IconTextMixin, AppMixin, widget.TaskList):
    def __init__(self, **config):
        super().__init__(**config)

        self._fallback_icon = None
        icon = get_icon_path(
            'application-x-executable',
            size=self.icon_size, theme=self.theme_path)
        if icon:
            self._fallback_icon = self.get_icon_surface(icon, self.icon_size)

        self.other_border = config.get('other_border', self.border)

        self.pinned = []
        flatpaks = dict(self.get_flatpaks())
        for pinned_name in config.get('pinned_apps', []):
            if pinned_name in flatpaks:
                desktop = flatpaks[pinned_name]
                surface = self.get_flatpak_icon(pinned_name, desktop)
                if surface:
                    app = PinnedApp(
                        desktop=desktop, icon=surface,
                        cmd=f'flatpak run {pinned_name}')
                    self.pinned.append(app)

            else:
                for desktop_path, desktop in self.get_desktop_files():
                    if os.path.basename(desktop_path) != f'{pinned_name}.desktop':
                        continue

                    icon = get_icon_path(
                        desktop['Desktop Entry']['Icon'], size=self.icon_size,
                        theme=self.theme_path)
                    if icon:
                        cmd = desktop['Desktop Entry']['Exec']
                        cmd = re.sub(r'%[A-Za-z]', '', cmd)
                        surface = self.get_icon_surface(icon, self.icon_size)
                        app = PinnedApp(desktop=desktop, icon=surface, cmd=cmd)
                        self.pinned.append(app)

                    break

    def box_width(self, text):
        return 0

    def get_taskname(self, window):
        return ''

    def calc_box_widths(self):
        apps = self.windows
        if not apps:
            return []

        icons = [self.get_window_icon(app) for app in apps]
        names = ['' for app in apps]
        width_boxes = [(self.icon_size + self.padding_x) for icon in icons]
        return zip(apps, icons, names, width_boxes)

    @property
    def windows(self):
        pinned_apps = [app.clone() for app in self.pinned]
        unpinned_apps = []

        for group in self.qtile.groups:
            for window in group.windows:
                for i, app in enumerate(pinned_apps):
                    if app.matches(window):
                        if app.window:
                            app = app.clone()
                            pinned_apps.insert(i + 1, app)
                        app.window = window
                        break
                else:
                    unpinned_apps.append(UnpinnedApp(window))

        return pinned_apps + unpinned_apps

    def select_window(self):
        if self.clicked:
            app = self.clicked
            w = app.window

            if not w:
                qtile.spawn(app.cmd)
                return

            if w is w.group.current_window and self.bar.screen.group.name == w.group.name:
                # if not w.minimized:
                #     w.minimized = True
                w.toggle_minimize()

            else:
                for i, screen in enumerate(qtile.screens):
                    if screen == w.group.screen:
                        qtile.focus_screen(i)
                        break
                w.group.toscreen()
                w.group.focus(w, False)

                if w.minimized:
                    w.minimized = False
                if w.floating:
                    w.bring_to_front()

    def get_window_icon(self, app):
        if isinstance(app, PinnedApp):
            return app.icon

        w = app.window
        icon = super().get_window_icon(w)
        if icon:
            return icon

        for cl in w.get_wm_class() or []:
            for appid, desktop in self.get_flatpaks():
                name = desktop['Desktop Entry']['Name']
                wmclass = desktop['Desktop Entry'].get('StartupWMClass')
                if cl.lower() == name.lower() or cl.lower() == wmclass:
                    icon = desktop['Desktop Entry']['Icon']
                    surface = self.get_flatpak_icon(appid, desktop)
                    if surface:
                        self._icons_cache[w.wid] = surface
                        return surface

        return self._fallback_icon

    def drawbox(self, offset, text, bordercolor, textcolor, width=None, rounded=False,
                block=False, icon=None):
        self.drawer.set_source_rgb(bordercolor or self.background or self.bar.background)

        x = offset
        y = (self.bar.height - (self.icon_size + self.padding_y * 2)) // 2
        w = self.icon_size + self.padding_x * 2
        h = self.icon_size + self.padding_y * 2

        if not block:
            x += w // 4
            y = 0
            w = w // 2
            h = self.padding_y

        if bordercolor:
            if rounded:
                self.drawer.rounded_fillrect(x, y, w, h, self.borderwidth)
            else:
                self.drawer.fillrect(x, y, w, h, self.borderwidth)

        if icon:
            self.draw_icon(icon, offset)

    def draw_icon(self, surface, offset):
        if not surface:
            return

        self.drawer.ctx.save()
        self.drawer.ctx.translate(offset + self.padding, (self.bar.height - self.icon_size) // 2)
        self.drawer.ctx.set_source(surface)
        self.drawer.ctx.paint()
        self.drawer.ctx.restore()

    def draw(self):
        self.drawer.clear(self.background or self.bar.background)
        offset = self.margin_x

        self._box_end_positions = []
        for app, icon, task, bw in self.calc_box_widths():
            self._box_end_positions.append(offset + bw)
            border = self.unfocused_border or None

            w = app.window
            if w:
                if w.urgent:
                    border = self.urgent_border
                elif w is w.group.current_window:
                    if self.bar.screen.group.name == w.group.name and self.qtile.current_screen == self.bar.screen:
                        border = self.border
                    elif self.qtile.current_screen == w.group.screen:
                        border = self.other_border
            else:
                border = None

            textwidth = (
                bw - 2 * self.padding_x - ((self.icon_size + self.padding_x) if icon else 0)
            )
            self.drawbox(
                offset,
                task,
                border,
                border,
                rounded=self.rounded,
                block=self.highlight_method == 'block',
                width=textwidth,
                icon=icon,
            )
            offset += bw + self.spacing

        self.drawer.draw(offsetx=self.offset, offsety=self.offsety, width=self.width)