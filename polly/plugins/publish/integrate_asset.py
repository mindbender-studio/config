import os
import errno
import shutil
from pprint import pformat

import pyblish.api
from avalon import api, io
from avalon.vendor import clique


class IntegrateAvalonAsset(pyblish.api.InstancePlugin):
    """Write to files and metadata

    This plug-in exposes your data to others by encapsulating it
    into a new version.

    """

    label = "Asset"
    order = pyblish.api.IntegratorOrder
    families = [
        "mindbender.model",
        "mindbender.rig",
        "mindbender.animation",
        "mindbender.lookdev",
        "mindbender.historyLookdev",
        "mindbender.group",
        "mindbender.imagesequence",
    ]

    def process(self, instance):
        # Required environment variables
        PROJECT = os.environ["AVALON_PROJECT"]
        ASSET = instance.data.get("asset") or os.environ["AVALON_ASSET"]
        SILO = os.environ["AVALON_SILO"]
        LOCATION = os.getenv("AVALON_LOCATION")

        # TODO(marcus): avoid hardcoding labels in the integrator
        representation_labels = {".ma": "Maya Ascii",
                                 ".source": "Original source file",
                                 ".abc": "Alembic"}

        context = instance.context

        # Atomicity
        #
        # Guarantee atomic publishes - each asset contains
        # an identical set of members.
        #     __
        #    /     o
        #   /       \
        #  |    o    |
        #   \       /
        #    o   __/
        #
        assert all(result["success"] for result in context.data["results"]), (
            "Atomicity not held, aborting.")

        # Assemble
        #
        #       |
        #       v
        #  --->   <----
        #       ^
        #       |
        #
        stagingdir = instance.data.get("stagingDir")
        assert stagingdir, ("Incomplete instance \"%s\": "
                            "Missing reference to staging area." % instance)

        self.log.debug("Establishing staging directory @ %s" % stagingdir)

        project = io.find_one({"type": "project"})
        asset = io.find_one({"name": ASSET})

        assert all([project, asset]), ("Could not find current project or "
                                       "asset '%s'" % ASSET)

        subset = io.find_one({"type": "subset",
                              "parent": asset["_id"],
                              "name": instance.data["subset"]})

        if subset is None:
            subset_name = instance.data["subset"]
            self.log.info("Subset '%s' not found, creating.." % subset_name)

            _id = io.insert_one({
                "schema": "avalon-core:subset-2.0",
                "type": "subset",
                "name": subset_name,
                "data": {},
                "parent": asset["_id"]
            }).inserted_id

            subset = io.find_one({"_id": _id})

        latest_version = io.find_one({"type": "version",
                                      "parent": subset["_id"]},
                                     {"name": True},
                                     sort=[("name", -1)])

        next_version = 1
        if latest_version is not None:
            next_version += latest_version["name"]

        self.log.debug("Next version: %i" % next_version)

        version = {
            "schema": "avalon-core:version-2.0",
            "type": "version",
            "parent": subset["_id"],
            "name": next_version,
            "locations": [LOCATION] if LOCATION else [],
            "data": {
                "families": (
                    instance.data.get("families", list()) +
                    [instance.data["family"]]
                ),
                "time": context.data["time"],
                "author": context.data["user"],
                "source": context.data["currentFile"].replace(
                    api.registered_root(), "{root}").replace("\\", "/"),
                "comment": context.data.get("comment")
            }
        }

        self.log.debug("Creating version: %s" % pformat(version))
        version_id = io.insert_one(version).inserted_id

        # Write to disk
        #          _
        #         | |
        #        _| |_
        #    ____\   /
        #   |\    \ / \
        #   \ \    v   \
        #    \ \________.
        #     \|________|
        #
        template_data = {
            "root": api.registered_root(),
            "project": PROJECT,
            "silo": SILO,
            "asset": ASSET,
            "subset": subset["name"],
            "version": version["name"],
        }

        template_publish = project["config"]["template"]["publish"]

        for fname in instance.data["files"]:
            _, ext = os.path.splitext(fname)

            representation = ext[1:]
            template_data["representation"] = representation

            src = os.path.join(stagingdir, fname)
            dst = template_publish.format(**template_data)

            self.log.info("Copying %s -> %s" % (src, dst))

            dirname = os.path.dirname(dst)
            try:
                os.makedirs(dirname)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    pass
                else:
                    self.log.critical("An unexpected error occurred.")
                    raise

            shutil.copy(src, dst)

            representation = {
                "schema": "avalon-core:representation-2.0",
                "type": "representation",
                "parent": version_id,
                "name": ext[1:],
                "data": {"label": representation_labels.get(ext)},
                "dependencies": instance.data.get("dependencies", "").split(),

                # Imprint shortcut to context for performance reasons.
                "context": {
                    "project": PROJECT,
                    "asset": ASSET,
                    "silo": SILO,
                    "subset": subset["name"],
                    "version": version["name"],
                    "representation": representation
                }
            }

            io.insert_one(representation)

        context.data["published_version"] = str(version_id)

        self.log.info("Successfully integrated \"%s\" to \"%s\"" % (
            instance, dst))
