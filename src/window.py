# window.py
#
# Copyright 2024 Nokse22
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import gi
from gi.repository import Adw
from gi.repository import Gtk, Gdk, Gio, GLib, GObject

from .widgets import *
from .vector_math import *

import f3d
from f3d import *

import math
import os
import threading
import datetime
import json
import re

from wand.image import Image
from enum import IntEnum

from . import logger_lib

up_dir_n_to_string = {
    0: "-X",
    1: "+X",
    2: "-Y",
    3: "+Y",
    4: "-Z",
    5: "+Z"
}

up_dir_string_to_n = {
    "-X": 0,
    "+X": 1,
    "-Y": 2,
    "+Y": 3,
    "-Z": 4,
    "+Z": 5
}

up_dirs_vector = {
    "-X": (-1.0, 0.0, 0.0),
    "+X": (1.0, 0.0, 0.0),
    "-Y": (0.0, -1.0, 0.0),
    "+Y": (0.0, 1.0, 0.0),
    "-Z": (0.0, 0.0, -1.0),
    "+Z": (0.0, 0.0, 1.0)
}

file_patterns = ["*.vtk", "*.vtp", "*.vtu", "*.vtr", "*.vti", "*.vts", "*.vtm", "*.ply", "*.stl", "*.dcm", "*.drc", "*.nrrd",
    "*.nhrd", "*.mhd", "*.mha", "*.ex2", "*.e", "*.exo", "*.g", "*.gml", "*.pts",
    "*.ply", "*.step", "*.stp", "*.iges", "*.igs", "*.brep", "*.abc", "*.vdb", "*.obj", "*.gltf",
    "*.glb", "*.3ds", "*.wrl", "*.fbx", "*.dae", "*.off", "*.dxf", "*.x", "*.3mf", "*.usd", "*.usda", "*.usdc", "*.usdz"]

allowed_extensions = [pattern.lstrip('*.') for pattern in file_patterns]

image_patterns = ["*.hdr", "*.exr", "*.png", "*.jpg", "*.pnm", "*.tiff", "*.bmp"]

class PeriodicChecker(GObject.Object):
    def __init__(self, function):
        super().__init__()

        self._running = False
        self._function = function

    def run(self):
        if self._running:
            return
        self._running = True
        GLib.timeout_add(500, self.periodic_check)

    def stop(self):
        self._running = False

    def periodic_check(self):
        if self._running:
            self._function()
            return True
        else:
            return False

 #                                     On change
 #                         ┌─────────┐ update the UI
 #                         │         ∨
 # Update           ┌─────────┐     ┌──┐
 # the settings ━━━▶│ListStore│     │UI│
 #                  └─────────┘     └──┘
 #   ┏━━━━━━┓        │     ∧         │
 #   ┃Viewer┃<───────┘     └─────────┘ On change update
 #   ┗━━━━━━┛  On change               the ListStore
 #             update the
 #             view options
 #
 #  Made with  ASCII Draw

class SettingType(IntEnum):
    VIEW = 0
    OTHER = 1
    INTERNAL = 2

class Setting(GObject.Object):
    __gtype_name__ = 'Setting'

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, (str, int, )),
        'user-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, int, )),
    }

    def __init__(self, name, value, setting_type):
        super().__init__()

        self._name = name
        self._value = value
        self._type = setting_type

    @GObject.Property(type=str)
    def name(self) -> str:
        return self._name

    @GObject.Property(type=str)
    def value(self) -> str:
        return self._value

    @GObject.Property(type=str)
    def type(self) -> str:
        return self._type

    def set_value(self, value):
        if value != self._value:
            self._value = value
            self.emit("changed", self._name, self._type)

    def set_value_without_signal(self, value):
        if value != self._value:
            self._value = value
            self.emit("user-changed", self._name, self._type)

    def __repr__(self):
        return f"<Setting {self._name}: {self._value}>"

class WindowSettings(Gio.ListStore):
    __gtype_name__ = 'WindowSettings'

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, (Setting, )),
    }

    default_settings = {
        "translucency-support": True,
        "tone-mapping": False,
        "ambient-occlusion": False,
        "anti-aliasing": True,
        "hdri-ambient": False,
        "light-intensity": 1.0,

        "show-edges": False,
        "edges-width": 1.0,

        "show-points": False,
        "point-size": 1.0,

        "model-metallic": 0.0,
        "model-roughness": 0.3,
        "model-opacity": 1.0,

        "comp": -1,
        "cells": True,
        "model-color": (1.0, 1.0, 1.0),

        "grid": True,
        "grid-absolute": False,

        "hdri-skybox": False,
        "hdri-file": "",
        "blur-background": True,
        "blur-coc": 20.0,

        "bg-color": (1.0, 1.0, 1.0),

        "up": "+Y",
        "orthographic": False,
        "point-up": True,

        # There is no UI for the following ones
        "texture-matcap": "",
        "texture-base-color": "",
        "emissive-factor": (1.0, 1.0, 1.0),
        "texture-emissive": "",
        "texture-material": "",
        "normal-scale": 1.0,
        "texture-normal": "",
        "point-sprites": False,
        "point-type": "sphere",
        "volume": False,
        "inverse": False,
        "final-shader": "",
        "grid-unit": 0.0,
        "grid-subdivisions": 10,
        "grid-color": (0.0, 0.0, 0.0),
    }

    other_settings = {
        "use-color": False,
        "point-up" : True,
        "auto-reload": False
    }

    internal_settings = {
        "auto-best" : True,
        "load-type": None, # 0 for geometry and 1 for scene
        "sidebar-show": True
    }

    def __init__(self):
        super().__init__()

        self.logger = logger_lib.logger

        for name, value in self.default_settings.items():
            setting = Setting(name, value, SettingType.VIEW)
            setting.connect("changed", self.on_setting_changed)
            setting.connect("user-changed", self.on_setting_changed)
            self.append(setting)

        for name, value in self.other_settings.items():
            setting = Setting(name, value, SettingType.OTHER)
            setting.connect("changed", self.on_setting_changed)
            setting.connect("user-changed", self.on_setting_changed)
            self.append(setting)

        for name, value in self.internal_settings.items():
            setting = Setting(name, value, SettingType.INTERNAL)
            setting.connect("changed", self.on_setting_changed)
            setting.connect("user-changed", self.on_setting_changed)
            self.append(setting)

    def sync_all_settings(self):
        for setting in self:
            setting.emit("changed", setting.name, setting.type)

    def on_setting_changed(self, setting, name, enum):
        self.emit("changed", setting)

    def set_setting(self, key, val):
        for index, setting in enumerate(self):
            if key == setting.name:
                setting.set_value(val)
                return
        self.logger.warning(f"{key} key not present")

    def set_setting_without_signal(self, key, val):
        for index, setting in enumerate(self):
            if key == setting.name:
                setting.set_value_without_signal(val)
                return
        self.logger.warning(f"{key} key not present")

    def get_setting(self, key):
        for setting in self:
            if key == setting.name:
                return setting

    def get_default_user_customizable_settings(self):
        settings = self.default_settings.copy()
        settings.update(self.other_settings)
        return settings

    def get_user_customized_settings(self):
        settings = self.get_view_settings()
        settings.update(self.get_other_settings())
        return settings

    def set_settings(self, dictionary):
        for key, value in dictionary:
            self.set_setting(key, value)

    def get_view_settings(self):
        options = {}
        for setting in self:
            if setting.type == SettingType.VIEW:
                options[setting.name] = setting.value
        return options

    def get_other_settings(self):
        options = {}
        for setting in self:
            if setting.type == SettingType.OTHER:
                options[setting.name] = setting.value
        return options

    def __repr__(self):
        out = ""
        for setting in self:
            out += f"{setting.name}:    {setting.value}\n"
        return out

@Gtk.Template(resource_path='/io/github/nokse22/Exhibit/ui/window.ui')
class Viewer3dWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'Viewer3dWindow'

    split_view = Gtk.Template.Child()

    f3d_viewer = Gtk.Template.Child()

    title_widget = Gtk.Template.Child()
    stack = Gtk.Template.Child()
    toolbar_view = Gtk.Template.Child()

    view_button_headerbar = Gtk.Template.Child()

    drop_revealer = Gtk.Template.Child()
    view_drop_target = Gtk.Template.Child()
    loading_drop_target = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()

    grid_switch = Gtk.Template.Child()
    absolute_grid_switch = Gtk.Template.Child()

    translucency_switch = Gtk.Template.Child()
    tone_mapping_switch = Gtk.Template.Child()
    ambient_occlusion_switch = Gtk.Template.Child()
    anti_aliasing_switch = Gtk.Template.Child()
    hdri_ambient_switch = Gtk.Template.Child()
    light_intensity_spin = Gtk.Template.Child()

    edges_switch = Gtk.Template.Child()
    edges_width_spin = Gtk.Template.Child()

    use_skybox_switch = Gtk.Template.Child()

    hdri_file_row = Gtk.Template.Child()
    blur_switch = Gtk.Template.Child()
    blur_coc_spin = Gtk.Template.Child()

    use_color_switch = Gtk.Template.Child()
    background_color_button = Gtk.Template.Child()

    point_up_switch = Gtk.Template.Child()
    up_direction_combo = Gtk.Template.Child()

    automatic_settings_switch = Gtk.Template.Child()

    automatic_reload_switch = Gtk.Template.Child()

    points_group = Gtk.Template.Child()
    spheres_switch = Gtk.Template.Child()
    points_size_spin = Gtk.Template.Child()

    model_load_combo = Gtk.Template.Child()

    material_group = Gtk.Template.Child()

    model_roughness_spin = Gtk.Template.Child()
    model_metallic_spin = Gtk.Template.Child()
    model_color_button = Gtk.Template.Child()
    model_opacity_spin = Gtk.Template.Child()

    model_color_row = Gtk.Template.Child()
    model_scivis_component_combo = Gtk.Template.Child()
    color_group = Gtk.Template.Child()

    startup_stack = Gtk.Template.Child()

    settings_section = Gtk.Template.Child()

    save_dialog = Gtk.Template.Child()
    settings_column_view = Gtk.Template.Child()
    settings_column_view_name_column = Gtk.Template.Child()
    settings_column_view_value_column = Gtk.Template.Child()
    save_settings_button = Gtk.Template.Child()
    save_settings_name_entry = Gtk.Template.Child()
    save_settings_extensions_entry = Gtk.Template.Child()
    save_settings_expander = Gtk.Template.Child()

    width = 600
    height = 600
    distance = 0

    file_name = ""
    filepath = ""

    _cached_time_stamp = 0

    def __init__(self, application=None, startup_filepath=None):
        super().__init__(application=application)

        self.logger = logger_lib.logger

        self.applying_breakpoint = False

        # Defining all the actions
        self.save_as_action = self.create_action('save-as-image', self.open_save_file_chooser)
        self.open_new_action = self.create_action('open-new', self.open_file_chooser)

        self.settings_action = Gio.SimpleAction.new_stateful(
            "settings",
            GLib.VariantType.new("s"),
            GLib.Variant("s", "general"),
        )
        self.settings_action.connect("activate", self.on_settings_changed)
        self.add_action(self.settings_action)

        self.save_settings_action = self.create_action('save-settings', self.on_save_settings)
        self.save_settings_action.set_enabled(False)

        # Initialize the change checker
        self.change_checker = PeriodicChecker(self.periodic_check_for_file_change)

        # Saving all the useful paths
        data_home = os.environ["XDG_DATA_HOME"]

        self.hdri_path = data_home + "/HDRIs/"
        self.hdri_thumbnails_path = self.hdri_path + "/thumbnails/"

        self.user_configurations_path = data_home + "/configurations/"

        os.makedirs(self.hdri_path, exist_ok=True)
        os.makedirs(self.hdri_thumbnails_path, exist_ok=True)
        os.makedirs(self.user_configurations_path, exist_ok=True)

        # HDRI
        hdri_names = ["city.hdr", "meadow.hdr", "field.hdr", "sky.hdr"]
        for hdri_filename in hdri_names:
            if not os.path.isfile(self.hdri_path + hdri_filename):
                hdri = Gio.resources_lookup_data('/io/github/nokse22/Exhibit/HDRIs/' + hdri_filename, Gio.ResourceLookupFlags.NONE).get_data()
                hdri_bytes = bytearray(hdri)
                with open(self.hdri_path + hdri_filename, 'wb') as output_file:
                    output_file.write(hdri_bytes)
                self.logger.info(f"Added {hdri_filename}")

        # Loading the saved configurations
        self.configurations = Gio.resources_lookup_data('/io/github/nokse22/Exhibit/configurations.json', Gio.ResourceLookupFlags.NONE).get_data().decode('utf-8')
        self.configurations = json.loads(self.configurations)

        for filename in os.listdir(self.user_configurations_path):
            if filename.endswith('.json'):
                filepath = os.path.join(self.user_configurations_path, filename)
                with open(filepath, 'r') as file:
                    try:
                        configuration = json.load(file)

                        # Check if the loaded configurations have all the required keys
                        required_keys = {"name", "formats", "view-settings", "other-settings"}
                        first_key_value = next(iter(configuration.values()))
                        if required_keys.issubset(first_key_value.keys()):
                            self.configurations.update(configuration)
                        else:
                            self.logger.error(f"Error: {filepath} is missing required keys.")

                    except json.JSONDecodeError as e:
                        self.logger.error(f"Error reading {config_file}: {e}")

        item = Gio.MenuItem.new("Custom", "win.settings")
        item.set_attribute_value("target", GLib.Variant.new_string("custom"))
        self.settings_section.append_item(item)

        for key, setting in self.configurations.items():
            item = Gio.MenuItem.new(setting["name"], "win.settings")
            item.set_attribute_value("target", GLib.Variant.new_string(key))
            self.settings_section.append_item(item)

        # Setting drop target type
        self.view_drop_target.set_gtypes([Gdk.FileList])
        self.loading_drop_target.set_gtypes([Gdk.FileList])

        # Getting the saved preferences and setting the window to the last state
        self.window_settings = WindowSettings()
        self.window_settings.connect("changed", self.on_setting_changed)
        self.saved_settings = Gio.Settings.new('io.github.nokse22.Exhibit')

        self.set_default_size(self.saved_settings.get_int("startup-width"), self.saved_settings.get_int("startup-height"))
        self.split_view.set_show_sidebar(self.saved_settings.get_boolean("startup-sidebar-show"))
        self.window_settings.set_setting("sidebar-show", self.saved_settings.get_boolean("startup-sidebar-show"))

        # Setting the UI and connecting widgets
        # self.set_preference_values(False)


        # Switches signals
        switches = [
            (self.grid_switch, "grid"),
            (self.absolute_grid_switch, "grid-absolute"),
            (self.translucency_switch, "translucency-support"),
            (self.tone_mapping_switch, "tone-mapping"),
            (self.ambient_occlusion_switch, "ambient-occlusion"),
            (self.anti_aliasing_switch, "anti-aliasing"),
            (self.hdri_ambient_switch, "hdri-ambient"),
            (self.edges_switch, "show-edges"),
            (self.spheres_switch, "show-points"),
            (self.use_skybox_switch, "hdri-skybox"),
            (self.blur_switch, "blur-background"),
            (self.use_color_switch, "use-color"),
            # (self.automatic_settings_switch, "auto-best"),
            # (self.automatic_reload_switch, "auto-reload")
        ]

        for switch, name in switches:
            switch.connect("notify::active", self.on_switch_toggled, name)
            setting = self.window_settings.get_setting(name)
            setting.connect("changed", self.set_switch_to, switch, setting.value)

        # Spins
        self.edges_width_spin.connect("notify::value", self.on_spin_changed, "edges-width")
        self.points_size_spin.connect("notify::value", self.on_spin_changed, "point-size")
        self.model_roughness_spin.connect("notify::value", self.on_spin_changed, "model-roughness")
        self.model_metallic_spin.connect("notify::value", self.on_spin_changed, "model-metallic")
        self.model_opacity_spin.connect("notify::value", self.on_spin_changed, "model-opacity")
        self.blur_coc_spin.connect("notify::value", self.on_spin_changed, "blur-coc")
        self.light_intensity_spin.connect("notify::value", self.on_spin_changed, "light-intensity")

        # Color buttons
        self.model_color_button.connect("notify::rgba", self.on_color_changed, "model-color")
        self.background_color_button.connect("notify::rgba", self.on_color_changed, "bg-color")

        # Combos
        self.model_scivis_component_combo.connect("notify::selected", self.on_scivis_component_combo_changed)
        self.model_load_combo.connect("notify::selected", self.set_load_type)

        # File rows
        self.hdri_file_row.connect("open-file", self.on_open_skybox)
        self.hdri_file_row.connect("delete-file", self.on_delete_skybox)
        self.hdri_file_row.connect("file-added", lambda row, filepath: self.load_hdri(filepath))

        # Others
        self.use_color_switch.connect("notify::active", self.update_background_color)
        self.background_color_button.connect("notify::rgba", self.update_background_color)

        self.point_up_switch.connect("notify::active", self.set_point_up, "point-up")
        self.up_direction_combo.connect("notify::selected", self.set_up_direction)

        # Sync the UI with the settings
        self.window_settings.sync_all_settings()

        # Getting the saved HDRI and generating thumbnails
        for filename in list_files(self.hdri_path):
            name, _ = os.path.splitext(filename)

            thumbnail = self.hdri_thumbnails_path + name + ".jpeg"
            filepath = self.hdri_path + filename
            try:
                if not os.path.isfile(thumbnail):
                    thumbnail = self.generate_thumbnail(filepath)
                self.hdri_file_row.add_suggested_file(thumbnail, filepath)
            except Exception as e:
                self.logger.warning(f"Couldn't open HDRI file {filepath}, skipping")

        if self.window_settings.get_setting("orthographic").value:
            self.toggle_orthographic()

        self.no_file_loaded = True

        self.style_manager = Adw.StyleManager().get_default()
        self.style_manager.connect("notify::dark", self.update_background_color)

        self.update_options()
        self.update_background_color()

        if startup_filepath:
            self.load_file(filepath=startup_filepath)

        # Setting up the save settings dialog
        def _on_factory_setup(_factory, list_item):
            label = Gtk.Label(xalign=0, ellipsize=3)
            list_item.set_child(label)

        def _on_factory_bind(_factory, list_item, what):
            label_widget = list_item.get_child()
            setting = list_item.get_item()
            label_widget.set_label(str(getattr(setting, what)))

        self.settings_column_view_name_column.get_factory().connect("setup", _on_factory_setup)
        self.settings_column_view_name_column.get_factory().connect("bind", _on_factory_bind, "name")
        self.settings_column_view_value_column.get_factory().connect("setup", _on_factory_setup)
        self.settings_column_view_value_column.get_factory().connect("bind", _on_factory_bind, "value")

        selection = Gtk.NoSelection.new(model=self.window_settings)
        self.settings_column_view.set_model(model=selection)

        self.save_settings_button.connect("clicked", self.on_save_settings_button_clicked)
        self.save_settings_name_entry.connect("changed", self.on_save_settings_name_entry_changed)
        self.save_settings_extensions_entry.connect("changed", self.on_save_settings_extensions_entry_changed)

    def on_setting_changed(self, window_settings, setting):
        self.logger.info(f"Setting: {setting.name} to {setting.value}")
        options = {setting.name: setting.value}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def set_switch_to(self, setting, name, enum, switch, value):
        self.logger.info(f"Setting switch to {value}")
        switch.set_active(value)

    def on_save_settings_button_clicked(self, btn):
        # Extract view settings, name, and formats
        view_settings = self.window_settings.get_view_settings()
        other_settings = self.window_settings.get_other_settings()
        name = self.save_settings_name_entry.get_text()
        formats = self.save_settings_extensions_entry.get_text()

        # Format the key
        key = name.lower().replace(' ', '_')

        # Construct the dictionary
        settings_dict = {
            key: {
                "name": name,
                "formats": f".*({formats.replace(', ', '|')})",
                "view-settings": view_settings,
                "other-settings": other_settings
            }
        }

        # Save to JSON file
        with open(self.user_configurations_path + key + '.json', 'w') as json_file:
            json.dump(settings_dict, json_file, indent=4)

        # Update configurations and menu UI
        self.configurations.update(settings_dict)
        item = Gio.MenuItem.new(name, "win.settings")
        item.set_attribute_value("target", GLib.Variant.new_string(key))
        self.settings_section.append_item(item)

        self.save_dialog.close()

    def on_save_settings_name_entry_changed(self, entry):
        if entry.get_text_length() != 0:
            self.save_settings_button.set_sensitive(True)
        else:
            self.save_settings_button.set_sensitive(False)

    def on_save_settings_extensions_entry_changed(self, entry):
        extensions_text = entry.get_text()

        if extensions_text == "":
            entry.remove_css_class("error")
            return

        entered_extensions = [ext.strip() for ext in extensions_text.split(',')]

        if all(ext in allowed_extensions for ext in entered_extensions):
            entry.remove_css_class("error")
        else:
            entry.add_css_class("error")

    def on_save_settings(self, *args):
        self.save_settings_name_entry.set_text("")
        self.save_settings_extensions_entry.set_text("")
        self.save_settings_expander.set_expanded(False)
        self.save_dialog.present(self)

    def set_settings_from_name(self, name):
        self.logger.debug("settings from name")
        if name == "custom":
            return

        # Get the default settings and change the ones defined by the chosen presets
        options = self.window_settings.get_default_user_customizable_settings()
        for key, value in self.configurations[name]["view-settings"].items():
            options[key] = value

        # Set all the settings
        for key, value in options.items():
            self.window_settings.set_setting(key, value)

        # Update all the viewer settings, to support settings without UI
        self.f3d_viewer.update_options(options)

        # Set all the settings not related to the viewer
        for key, value in self.configurations[name]["other-settings"].items():
            self.window_settings.set_setting(key, value)

    def check_for_options_change(self):
        self.settings_action.set_state(GLib.Variant("s", "custom"))
        self.save_settings_action.set_enabled(True)
        return

        state_name = self.settings_action.get_state().get_string()
        if state_name == "custom":
            return

        state_options = self.window_settings.get_default_user_customizable_settings()

        for key, value in self.configurations[state_name]["view-settings"].items():
            state_options[key] = value

        for key, value in self.configurations[state_name]["other-settings"].items():
            state_options[key] = value

        current_settings = self.window_settings.get_user_customized_settings()
        for key, value in state_options.items():
            if key in current_settings:
                if current_settings[key] != value:
                    self.logger.info(f"current key: {key}'s value is {current_settings[key]} != {value}")
                    self.settings_action.set_state(GLib.Variant("s", "custom"))
                    self.save_settings_action.set_enabled(True)
                    return

    def periodic_check_for_file_change(self):
        if self.filepath == "":
            return True

        changed = self.update_time_stamp()
        if changed:
            self.logger.debug("file changed")
            self.load_file(preserve_orientation=True, override=True)

        if self.window_settings.get_setting("auto-reload").value:
            return True
        return False

    def update_time_stamp(self):
        stamp = os.stat(self.filepath).st_mtime
        if stamp != self._cached_time_stamp:
            self._cached_time_stamp = stamp
            return True
        return False

    def on_settings_changed(self, action: Gio.SimpleAction, state: GLib.Variant):
        # Called when the preset is changed
        self.logger.debug("settings changed")

        self.set_settings_from_name(state.get_string())

        # Update the UI
        self.set_preference_values(False)

        self.update_background_color()

        self.settings_action.set_state(state)

        # Enable saving the settings only if it's not one already saved
        if state == GLib.Variant("s", "custom"):
            self.save_settings_action.set_enabled(True)
        else:
            self.save_settings_action.set_enabled(False)

    def get_gimble_limit(self):
        return self.distance / 10

    def open_file_chooser(self, *args):
        file_filter = Gtk.FileFilter(name="All supported formats")

        for patt in file_patterns:
            file_filter.add_pattern(patt)

        filter_list = Gio.ListStore.new(Gtk.FileFilter())
        filter_list.append(file_filter)

        dialog = Gtk.FileDialog(
            title=_("Open File"),
            filters=filter_list,
        )

        dialog.open(self, None, self.on_open_file_response)

    def on_open_file_response(self, dialog, response):
        file = dialog.open_finish(response)

        if file:
            filepath = file.get_path()
            self.window_settings.set_setting("load-type", None)
            self.load_file(filepath=filepath)

    def load_file(self, **kwargs):
        filepath=None
        override=False
        preserve_orientation=False

        if "filepath" in kwargs:
            filepath=kwargs["filepath"]
        if "override" in kwargs:
            override=kwargs["override"]
        if "preserve_orientation" in kwargs:
            preserve_orientation=kwargs["preserve_orientation"]

        if filepath is None or filepath == "":
            filepath = self.filepath

        self.logger.debug(f"load file: {filepath}")

        self.change_checker.stop()

        if self.window_settings.get_setting("auto-best").value and not override:
            self.logger.debug("choosing best settings")
            settings = "general"
            for key, value in self.configurations.items():
                pattern = value["formats"]
                if pattern == ".*()":
                    continue
                if re.search(pattern, filepath):
                    settings = key
            self.set_settings_from_name(settings)

        scene_loaded = False
        geometry_loaded = False

        if self.window_settings.get_setting("load-type").value is None:
            if self.f3d_viewer.has_scene_loader(filepath):
                self.f3d_viewer.load_scene(filepath)
                scene_loaded = True
                self.model_load_combo.set_sensitive(True)
            elif self.f3d_viewer.has_geometry_loader(filepath):
                self.f3d_viewer.load_geometry(filepath)
                geometry_loaded = True
                self.model_load_combo.set_sensitive(False)

        elif self.window_settings.get_setting("load-type").value == 0:
            if self.f3d_viewer.has_geometry_loader(filepath):
                self.f3d_viewer.load_geometry(filepath)
                geometry_loaded = True
        elif self.window_settings.get_setting("load-type").value == 1:
            if self.f3d_viewer.has_scene_loader(filepath):
                self.f3d_viewer.load_scene(filepath)
                scene_loaded = True

        if not scene_loaded and not geometry_loaded:
            self.on_file_not_opened(filepath)
            return

        if self.f3d_viewer.has_geometry_loader(filepath) and self.f3d_viewer.has_scene_loader(filepath):
            self.model_load_combo.set_sensitive(True)
        else:
            self.model_load_combo.set_sensitive(False)

        if scene_loaded:
            self.window_settings.set_setting("load-type", 1)
        elif geometry_loaded:
            self.window_settings.set_setting("load-type", 0)

        if (scene_loaded or geometry_loaded) and preserve_orientation:
            self.f3d_viewer.set_camera_state(camera_state)

        self.filepath = filepath
        self.on_file_opened()

        if preserve_orientation:
            camera_state = self.f3d_viewer.get_camera_state()

    def on_file_opened(self):
        self.logger.debug("on file opened")

        self.update_time_stamp()
        if self.window_settings.get_setting("auto-reload").value:
            self.change_checker.run()

        self.file_name = os.path.basename(self.filepath)

        self.set_title(f"View {self.file_name}")
        self.title_widget.set_subtitle(self.file_name)
        self.stack.set_visible_child_name("3d_page")

        self.no_file_loaded = False

        self.drop_revealer.set_reveal_child(False)
        self.toast_overlay.remove_css_class("blurred")

        if self.window_settings.get_setting("load-type").value == 0:
            self.material_group.set_sensitive(True)
            self.points_group.set_sensitive(True)
            self.color_group.set_sensitive(True)
        elif self.window_settings.get_setting("load-type").value == 1:
            self.material_group.set_sensitive(False)
            self.points_group.set_sensitive(False)
            self.color_group.set_sensitive(False)
            self.window_settings.set_setting("show-points", False)

        self.set_preference_values()

        self.update_background_color()

    def on_file_not_opened(self, filepath):
        self.logger.debug("on file not opened")

        self.set_title(_("Exhibit"))
        if self.no_file_loaded:
            self.stack.set_visible_child_name("startup_page")
            self.startup_stack.set_visible_child_name("error_page")
        else:
            self.send_toast(_("Can't open") + " " + os.path.basename(filepath))
        options = {"up": self.window_settings.get_setting("up").value}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def send_toast(self, message):
        toast = Adw.Toast(title=message, timeout=2)
        self.toast_overlay.add_toast(toast)

    def update_options(self):
        options = self.window_settings.get_view_settings()

        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def save_as_image(self, filepath):
        img = self.f3d_viewer.render_image()
        img.save(filepath)

    def open_save_file_chooser(self, *args):
        dialog = Gtk.FileDialog(
            title=_("Save File"),
            initial_name=self.file_name.split(".")[0] + ".png",
        )
        dialog.save(self, None, self.on_save_file_response)

    def on_save_file_response(self, dialog, response):
        try:
            file = dialog.save_finish(response)
        except:
            return

        if file:
            file_path = file.get_path()
            self.save_as_image(file_path)
            toast = Adw.Toast(
                title="Image Saved",
                timeout=2,
                button_label="Open",
                action_name="app.show-image-externally",
                action_target=GLib.Variant("s", file_path)
            )
            self.toast_overlay.add_toast(toast)

    @Gtk.Template.Callback("on_home_clicked")
    def on_home_clicked(self, btn):
        self.f3d_viewer.reset_to_bounds()

    @Gtk.Template.Callback("on_open_button_clicked")
    def on_open_button_clicked(self, btn):
        self.open_file_chooser()

    @Gtk.Template.Callback("on_view_clicked")
    def toggle_orthographic(self, *args):
        btn = self.view_button_headerbar
        if (btn.get_icon_name() == "perspective-symbolic"):
            btn.set_icon_name("orthographic-symbolic")
            camera_options = {"orthographic": True}
            self.window_settings.set_setting("orthographic", True)
        else:
            btn.set_icon_name("perspective-symbolic")
            camera_options = {"orthographic": False}
            self.window_settings.set_setting("orthographic", False)
        self.f3d_viewer.update_options(camera_options)

    @Gtk.Template.Callback("on_drop_received")
    def on_drop_received(self, drop, value, x, y):
        filepath = value.get_files()[0].get_path()
        extension = os.path.splitext(filepath)[1][1:]

        if "*." + extension in image_patterns:
            self.load_hdri(filepath)
        else:
            self.window_settings.set_setting("load-type", None)
            self.load_file(filepath=filepath)

    @Gtk.Template.Callback("on_drop_enter")
    def on_drop_enter(self, drop_target, *args):
        self.drop_revealer.set_reveal_child(True)
        self.toast_overlay.add_css_class("blurred")

    @Gtk.Template.Callback("on_drop_leave")
    def on_drop_leave(self, *args):
        self.drop_revealer.set_reveal_child(False)
        self.toast_overlay.remove_css_class("blurred")

    @Gtk.Template.Callback("on_close_sidebar_clicked")
    def on_close_sidebar_clicked(self, *args):
        self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback("on_open_with_external_app_clicked")
    def on_open_with_external_app_clicked(self, *args):
        try:
            file = Gio.File.new_for_path(self.filepath)
        except GLib.GError as e:
            self.logger.error("Failed to construct a new Gio.File object from path.")
        else:
            launcher = Gtk.FileLauncher.new(file)
            launcher.set_always_ask(True)

            def open_file_finish(_, result, *args):
                try:
                    launcher.launch_finish(result)
                except GLib.GError as e:
                    if e.code != 2: # 'The portal dialog was dismissed by the user' error
                        self.logger.error("Failed to finish Gtk.FileLauncher procedure.")

            launcher.launch(self, None, open_file_finish)

    @Gtk.Template.Callback("on_apply_breakpoint")
    def on_apply_breakpoint(self, *args):
        state = self.window_settings.get_setting("sidebar-show").value
        self.applying_breakpoint = True
        self.split_view.set_collapsed(True)
        self.split_view.set_show_sidebar(False)
        self.applying_breakpoint = False

    @Gtk.Template.Callback("on_unapply_breakpoint")
    def on_unapply_breakpoint(self, *args):
        state = self.window_settings.get_setting("sidebar-show").value
        self.applying_breakpoint = True
        self.split_view.set_collapsed(False)
        self.split_view.set_show_sidebar(state)
        self.applying_breakpoint = False

    @Gtk.Template.Callback("on_split_view_show_sidebar_changed")
    def on_split_view_show_sidebar_changed(self, *args):
        if self.applying_breakpoint:
            return
        state = self.split_view.get_show_sidebar()
        self.window_settings.set_setting("sidebar-show", state)

    def on_switch_toggled(self, switch, active, name):
        self.window_settings.set_setting_without_signal(name, switch.get_active())

    def on_expander_toggled(self, expander, enabled, name):
        self.window_settings.set_setting(name, expander.get_enable_expansion())
        options = {name: expander.get_enable_expansion()}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def on_spin_changed(self, spin, value, name):
        val = float(round(spin.get_value(), 2))
        options = {name: val}
        self.window_settings.set_setting(name, val)

    def set_point_up(self, switch, active, name):
        val = switch.get_active()
        self.window_settings.set_setting(name, val)
        if val:
            self.f3d_viewer.set_view_up(up_dirs_vector[self.window_settings.get_setting("up").value])
            self.f3d_viewer.always_point_up = True
        else:
            self.f3d_viewer.always_point_up = False

    def on_color_changed(self, btn, color, setting):
        color_list = rgb_to_list(btn.get_rgba().to_string())
        self.window_settings.set_setting(setting, color_list)
        options = {setting: color_list}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def set_up_direction(self, combo, *args):
        direction = up_dir_n_to_string[combo.get_selected()]
        options = {"up": direction}
        self.f3d_viewer.update_options(options)
        self.window_settings.set_setting("up", direction)
        self.check_for_options_change()
        self.load_file(filepath=self.filepath, override=True)

    def set_automatic_reload(self, switch, *args):
        val = switch.get_active()
        # self.window_settings.set_setting("auto-reload", val)
        if val:
            self.change_checker.run()
        else:
            self.change_checker.stop()

    def set_load_type(self, combo, *args):
        load_type = combo.get_selected()
        self.window_settings.set_setting("load-type", load_type)
        self.load_file()

    def update_background_color(self, *args):
        self.logger.debug(f"Use color is: {self.window_settings.get_setting('use-color').value}")
        if self.window_settings.get_setting("use-color").value:
            options = {
                "bg-color": self.window_settings.get_setting("bg-color").value,
            }
            self.f3d_viewer.update_options(options)
            self.check_for_options_change()
            GLib.idle_add(self.f3d_viewer.queue_render)
            return
        if self.style_manager.get_dark():
            options = {"bg-color": [0.2, 0.2, 0.2]}
        else:
            options = {"bg-color": [1.0, 1.0, 1.0]}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()
        GLib.idle_add(self.f3d_viewer.queue_render)

    def on_scivis_component_combo_changed(self, combo, *args):
        selected = combo.get_selected()
        self.model_color_row.set_sensitive(True if selected == 0 else False)

        if selected == 0:
            options = {
                "comp": -1,
                "cells": True
            }
            self.window_settings.set_setting("comp", -1)
            self.window_settings.set_setting("cells", True)
        else:
            options = {
                "comp": - (selected - 1),
                "cells": False
            }
            self.window_settings.set_setting("comp", -(selected - 1))
            self.window_settings.set_setting("cells", False)
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def on_delete_skybox(self, *args):
        self.window_settings.set_setting("hdri-file", "")
        self.window_settings.set_setting("hdri-skybox", False)
        self.use_skybox_switch.set_active(False)
        options = {"hdri-file": "",
                         "hdri-skybox": False}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def on_open_skybox(self, *args):
        file_filter = Gtk.FileFilter(name="All supported formats")

        for patt in image_patterns:
            file_filter.add_pattern(patt)

        filter_list = Gio.ListStore.new(Gtk.FileFilter())
        filter_list.append(file_filter)

        dialog = Gtk.FileDialog(
            title=_("Open Skybox File"),
            filters=filter_list,
        )

        dialog.open(self, None, self.on_open_skybox_file_response)

    def on_open_skybox_file_response(self, dialog, response):
        file = dialog.open_finish(response)

        if file:
            filepath = file.get_path()

            self.load_hdri(filepath)

    def load_hdri(self, filepath):
        self.window_settings.set_setting("hdri-file", filepath)
        self.window_settings.set_setting("hdri-skybox", True)
        self.use_skybox_switch.set_active(True)
        self.hdri_file_row.set_filename(filepath)
        options = {"hdri-file": filepath,
                         "hdri-skybox": True}
        self.f3d_viewer.update_options(options)
        self.check_for_options_change()

    def set_preference_values(self, block=True):
        self.logger.debug("updating settings")
        return

        if block:
            self.up_direction_combo.handler_block(self.up_direction_combo_handler_id)
            self.model_load_combo.handler_block(self.load_type_combo_handler_id)

        self.grid_switch.set_active(self.window_settings.get_setting("grid").value)
        self.absolute_grid_switch.set_active(self.window_settings.get_setting("grid-absolute").value)

        self.translucency_switch.set_active(self.window_settings.get_setting("translucency-support").value)
        self.tone_mapping_switch.set_active(self.window_settings.get_setting("tone-mapping").value)
        self.ambient_occlusion_switch.set_active(self.window_settings.get_setting("ambient-occlusion"))
        self.anti_aliasing_switch.set_active(self.window_settings.get_setting("anti-aliasing").value)
        self.hdri_ambient_switch.set_active(self.window_settings.get_setting("hdri-ambient").value)
        self.light_intensity_spin.set_value(self.window_settings.get_setting("light-intensity").value)
        self.hdri_file_row.set_filename(self.window_settings.get_setting("hdri-file").value)
        self.blur_switch.set_active(self.window_settings.get_setting("blur-background").value)
        self.blur_coc_spin.set_value(self.window_settings.get_setting("blur-coc").value)
        self.use_skybox_switch.set_active(self.window_settings.get_setting("hdri-skybox").value)

        self.edges_switch.set_active(self.window_settings.get_setting("show-edges").value)
        self.edges_width_spin.set_value(self.window_settings.get_setting("edges-width").value)

        self.spheres_switch.set_active(self.window_settings.get_setting("show-points").value)
        self.points_size_spin.set_value(self.window_settings.get_setting("point-size").value)

        self.point_up_switch.set_active(self.window_settings.get_setting("point-up").value)
        self.up_direction_combo.set_selected(up_dir_string_to_n[self.window_settings.get_setting("up").value])
        self.automatic_settings_switch.set_active(self.window_settings.get_setting("auto-best").value)
        self.automatic_reload_switch.set_active(self.window_settings.get_setting("auto-reload").value)

        load_type = self.window_settings.get_setting("load-type").value
        self.model_load_combo.set_selected(load_type if load_type else 0)

        self.model_roughness_spin.set_value(self.window_settings.get_setting("model-roughness").value)
        self.model_metallic_spin.set_value(self.window_settings.get_setting("model-metallic").value)
        rgba = Gdk.RGBA()
        rgba.parse(list_to_rgb(self.window_settings.get_setting("model-color").value))
        self.model_color_button.set_rgba(rgba)
        self.model_opacity_spin.set_value(self.window_settings.get_setting("model-opacity").value)
        if self.window_settings.get_setting("comp") == -1 and self.window_settings.get_setting("cells").value:
            self.model_scivis_component_combo.set_selected(0)
        else:
            self.model_scivis_component_combo.set_selected(-self.window_settings.get_setting("comp").value + 1)

        self.use_color_switch.set_active(self.window_settings.get_setting("use-color").value)
        rgba = Gdk.RGBA()
        rgba.parse(list_to_rgb(self.window_settings.get_setting("bg-color").value))
        self.background_color_button.set_rgba(rgba)

        if block:
            self.up_direction_combo.handler_unblock(self.up_direction_combo_handler_id)
            self.model_load_combo.handler_unblock(self.load_type_combo_handler_id)

    def create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        return action

    def generate_thumbnail(self, hdri_file_path, width=300, height=200):
        base_name = os.path.basename(hdri_file_path)
        name, _ = os.path.splitext(base_name)

        thumbnail_name = f"{name}.jpeg"
        thumbnail_filepath = os.path.join(self.hdri_thumbnails_path, thumbnail_name)

        with Image(filename=hdri_file_path) as img:
            img.thumbnail(width, height)
            img.gamma(1.7)
            img.brightness_contrast(0, -5)
            img.format = 'jpeg'
            img.save(filename=thumbnail_filepath)

        return thumbnail_filepath

    @Gtk.Template.Callback("on_close_request")
    def on_close_request(self, window):
        self.logger.debug("window closed, saving settings")
        self.saved_settings.set_int("startup-width", window.get_width())
        self.saved_settings.set_int("startup-height", window.get_height())
        self.saved_settings.set_boolean("startup-sidebar-show", window.split_view.get_show_sidebar())

def rgb_to_list(rgb):
    values = [int(x) / 255 for x in rgb[4:-1].split(',')]
    return values

def list_to_rgb(lst):
    return f"rgb({int(lst[0] * 255)},{int(lst[1] * 255)},{int(lst[2] * 255)})"

def list_files(directory):
    items = os.listdir(directory)
    files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
    return files

