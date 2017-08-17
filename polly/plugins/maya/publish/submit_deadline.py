import os
import re
import json
import shutil
import getpass

from maya import cmds

from avalon import api
from avalon.vendor import requests

import pyblish.api


def get_vray_extension():
    """Retrieve the extension which has been set in the VRay settings

    Will return None if the current renderer is not VRay

    Returns:
        str
    """

    ext = None
    if cmds.getAttr("defaultRenderGlobals.currentRenderer") == "vray":
        # check for vray settings node
        settings_node = cmds.ls("vraySettings", type="VRaySettingsNode")
        if not settings_node:
            raise AttributeError("Could not find a VRay Settings Node, "
                                 "to ensure the node exists open the "
                                 "Render Settings window")

        # get the extension
        image_format = cmds.getAttr("vraySettings.imageFormatStr")
        if image_format and image_format != ext:
            ext = "{}".format(image_format)

    return ext


class MindbenderSubmitDeadline(pyblish.api.InstancePlugin):
    """Submit available render layers to Deadline

    Renders are submitted to a Deadline Web Service as
    supplied via the environment variable AVALON_DEADLINE

    """

    label = "Submit to Deadline"
    order = pyblish.api.IntegratorOrder
    hosts = ["maya"]
    families = ["colorbleed.renderlayer"]

    def process(self, instance):

        deadline = api.Session.get("AVALON_DEADLINE", None)
        assert deadline is not None, "Requires AVALON_DEADLINE"

        context = instance.context
        workspace = context.data["workspaceDir"]
        fpath = context.data["currentFile"]
        fname = os.path.basename(fpath)
        name, ext = os.path.splitext(fname)
        comment = context.data.get("comment", "")
        dirname = os.path.join(workspace, "renders", name)

        try:
            os.makedirs(dirname)
        except OSError:
            pass

        # E.g. http://192.168.0.1:8082/api/jobs
        url = "{}/api/jobs".format(deadline)

        # Documentation for keys available at:
        # https://docs.thinkboxsoftware.com
        #    /products/deadline/8.0/1_User%20Manual/manual
        #    /manual-submission.html#job-info-file-options

        payload = {
            "JobInfo": {
                # Top-level group name
                "BatchName": fname,

                # Job name, as seen in Monitor
                "Name": "%s - %s" % (fname, instance.name),

                # Arbitrary username, for visualisation in Monitor
                "UserName": getpass.getuser(),

                "Plugin": "MayaBatch",
                "Frames": "{start}-{end}x{step}".format(
                    start=int(instance.data["startFrame"]),
                    end=int(instance.data["endFrame"]),
                    step=int(instance.data["byFrameStep"]),
                ),

                "Comment": comment,

                # Optional, enable double-click to preview rendered
                # frames from Deadline Monitor
                "OutputFilename0": self.preview_fname(instance, dirname),
            },
            "PluginInfo": {
                # Input
                "SceneFile": fpath,

                # Output directory and filename
                "OutputFilePath": dirname,
                "OutputFilePrefix": "<RenderLayer>/<RenderLayer>",

                # Mandatory for Deadline
                "Version": cmds.about(version=True),

                # Only render layers are considered renderable in this pipeline
                "UsingRenderLayers": True,

                # Render only this layer
                "RenderLayer": instance.name,

                # Determine which renderer to use from the file itself
                "Renderer": "file",

                # Resolve relative references
                "ProjectPath": workspace,
            },

            # Mandatory for Deadline, may be empty
            "AuxFiles": []
        }

        # Include critical variables with submission
        environment = dict({
            # This will trigger `userSetup.py` on the slave
            # such that proper initialisation happens the same
            # way as it does on a local machine.
            # TODO(marcus): This won't work if the slaves don't
            # have accesss to these paths, such as if slaves are
            # running Linux and the submitter is on Windows.
            "PYTHONPATH": os.getenv("PYTHONPATH", ""),

        }, **api.Session)

        payload["JobInfo"].update({
            "EnvironmentKeyValue%d" % index: "{key}={value}".format(
                key=key,
                value=environment[key]
            ) for index, key in enumerate(environment)
        })

        # Include optional render globals
        payload["JobInfo"].update(instance.data.get("renderGlobals", {}))

        self.preflight_check(instance)

        self.log.info("Submitting..")
        self.log.info(json.dumps(payload, indent=4, sort_keys=True))

        response = requests.post(url, json=payload)

        if response.ok:
            # Write metadata for publish
            fname = os.path.join(dirname, "{}.json".format(instance.name))
            data = {
                "submission": payload,
                "session": api.Session,
                "instance": instance.data,
                "jobs": [
                    response.json()
                ],
            }

            with open(fname, "w") as f:
                json.dump(data, f, indent=4, sort_keys=True)

        else:
            try:
                shutil.rmtree(dirname)
            except OSError:
                # This is nice-to-have, but not critical to the operation
                pass

            raise Exception(response.text)

    def preview_fname(self, instance, dirname):
        """Return outputted filename with #### for padding

        Passing the absolute path to Deadline enables Deadline Monitor
        to provide the user with a Job Output menu option.

        Deadline requires the path to be formatted with # in place of numbers.

        From
            /path/to/render.0000.png
        To
            /path/to/render.####.png

        """

        # We'll need to take tokens into account
        fname = cmds.renderSettings(firstImageName=True,
                                    fullPath=True,
                                    layer=instance.name)[0]

        # outFormatControl:
        # - 0 is no extension, name.#
        # - 1 is with extension, name.#.ext
        # - 2 is use custom extension
        formatcontol = cmds.getAttr("defaultRenderGlobals.outFormatControl")
        if formatcontol == 0:
            raise RuntimeError("Output has no extension")

        # Check the filename formatting from the render settings
        # Does the output have frames?
        has_frames = cmds.getAttr("defaultRenderGlobals.animation")
        if not has_frames:
            self.log.info("No frames in filename")
            file_name = os.path.join(dirname, os.path.basename(fname))
            return file_name

        # Where are the frame put in the filename?
        frame_before = cmds.getAttr("defaultRenderGlobals.putFrameBeforeExt")
        # Get the number of digits the padding will get
        padding_count = cmds.getAttr("defaultRenderGlobals.extensionPadding")
        try:
            basename = os.path.basename(fname)
            basename_parts = basename.rsplit(".", 2)
            # Depending on the where the frame is places, get the right
            # variables rsplit
            if frame_before:
                name, padding, ext = basename_parts
            else:
                name, ext, padding = basename_parts

            # check if the extension is correct for vray
            new_ext = get_vray_extension() or ext
            new_padding = "#" * padding_count
            fname = basename.replace(padding, new_padding)
            if new_ext != ext:
                fname = fname.replace(ext, new_ext)

            self.log.info("Assuming renders end up @ %s" % fname)

            file_name = os.path.join(dirname, instance.name, fname)
        except ValueError:
            file_name = ""
            self.log.info("Couldn't figure out where renders go")

        return file_name

    def preflight_check(self, instance):
        """Ensure the startFrame, endFrame and byFrameStep are integers"""

        for key in ("startFrame", "endFrame", "byFrameStep"):
            value = instance.data[key]

            if int(value) == value:
                continue

            self.log.warning(
                "%f=%d was rounded off to nearest integer"
                % (value, int(value))
            )
