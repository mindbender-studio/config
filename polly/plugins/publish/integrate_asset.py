import os
import errno
import shutil
from pprint import pformat

import pyblish.api
from mindbender import api, io


class IntegrateMindbenderAsset(pyblish.api.InstancePlugin):
    """Write to files and metadata

    This plug-in exposes your data to others by encapsulating it
    into a new version.

    Schema:
        Data is written in the following format.
         ____________________
        |                    |
        | version            |
        |  ________________  |
        | |                | |
        | | representation | |
        | |________________| |
        | |                | |
        | | ...            | |
        | |________________| |
        |____________________|

    """

    label = "Integrate Mindbender Asset"
    order = pyblish.api.IntegratorOrder
    families = [
        "mindbender.model",
        "mindbender.rig",
        "mindbender.animation",
        "mindbender.lookdev",
        "mindbender.historyLookdev",
        "mindbender.group"
    ]

    def process(self, instance):
        # Required environment variables
        PROJECT = os.environ["MINDBENDER_PROJECT"]
        ASSET = instance.data.get("asset") or os.environ["MINDBENDER_ASSET"]
        SILO = os.environ["MINDBENDER_SILO"]
        LOCATION = os.getenv("MINDBENDER_LOCATION")

        # todo(marcus): avoid hardcoding labels in the integrator
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

        assert all([project, asset]), "This is bug"

        subset = io.find_one({
            "type": "subset",
            "parent": asset["_id"],
            "name": instance.data["subset"]
        })

        if subset is None:
            subset_name = instance.data["subset"]
            self.log.info("Subset '%s' not found, creating.." % subset_name)

            _id = io.insert_one({
                "schema": "mindbender-core:subset-2.0",
                "type": "subset",
                "name": subset_name,
                "data": {},
                "parent": asset["_id"]
            }).inserted_id

            subset = io.find_one({"_id": _id})

        # get next version
        latest_version = io.find_one({"type": "version",
                                      "parent": subset["_id"]},
                                     {"name": True},
                                     sort=[("name", -1)])

        next_version = 1
        if latest_version is not None:
            next_version += latest_version["name"]

        self.log.debug("Next version: %i" % next_version)

        version = self.create_version(subset, next_version, [LOCATION])
        version["data"] = self.create_version_data(context, instance)

        self.backwards_compatiblity(instance, subset, version)

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

        for fname in os.listdir(stagingdir):
            name, ext = os.path.splitext(fname)
            template_data["representation"] = ext[1:]

            src = os.path.join(stagingdir, fname)
            dst = template_publish.format(**template_data)

            # Backwards compatibility
            if fname == ".metadata.json":
                dirname = os.path.dirname(dst)
                dst = os.path.join(dirname, ".metadata.json")

            self.log.info("Copying %s -> %s" % (src, dst))

            self.copy_source(src, dst)

            representation = {
                "schema": "mindbender-core:representation-2.0",
                "type": "representation",
                "parent": version_id,
                "name": ext[1:],
                "data": {"label": representation_labels.get(ext)},
                "dependencies": instance.data.get("dependencies", "").split(),

                # Imprint shortcut to context
                # for performance reasons.
                "context": {
                    "project": PROJECT,
                    "asset": ASSET,
                    "silo": SILO,
                    "subset": subset["name"],
                    "version": version["name"],
                    "representation": ext[1:]
                }
            }

            io.insert_one(representation)

        self.log.info("Successfully integrated \"%s\" to \"%s\"" % (
            instance, dst))

    def create_version(self, subset, version_number, locations):
        """ Copy given source to destination

        Arguments:
            subset (dict): the registered subset of the asset
            version_number (int): the version number
            locations (list): the currently registered locations
        """
        # Imprint currently registered location
        version_locations = [location for location in locations if
                             location is not None]

        return {"schema": "mindbender-core:version-2.0",
                "type": "version",
                "parent": subset["_id"],
                "name": version_number,
                "locations": version_locations,
                "data": None}

    def create_version_data(self, context, instance):
        """
        Create the data colllection for th verison
        Args:
            context (object): the current context
            instance(object): the current instance being published

        Returns:
            dict: the required information with instance.data as key
        """

        current_families = instance.data.get("families", list())

        instance_family = instance.data.get("family", None)
        if current_families:
            families += current_families
        if instance_family is not None:
            families.append(instance_family)

        # create relative source path for DB
        relative_path = os.path.relpath(context.data["currentFile"],
                                        api.registered_root())
        source = os.path.join("{root}", relative_path).replace("\\", "/")

        version_data = {"families": families,
                        "time": context.data["time"],
                        "author": context.data["user"],
                        "source": source,
                        "comment": context.data.get("comment")}

        return dict(instance.data, **version_data)

    def copy_source(self, src, dst):
        """ Copy given source to destination

        Arguments:
            src (str): the source file which needs to be copied
            dst (str): the destination of the sourc file
        Returns:
            None
        """

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

    def backwards_compatiblity(self, instance, subset, version):
        """Maintain backwards compatibility with newly published assets

        With the introduction of the database in 2.0, the artist would be
        unable to publish in 2.0 and use the files in 1.0. Therefore, we
        introduce this mechanism which continue to write for 1.0 even
        when writing from the 2.0 pipeline.

        This behaviour is deprecated and is to be removed in a future release.

        """
        from mindbender import api

        MINDBENDER_PROJECT = os.environ["MINDBENDER_PROJECT"]
        MINDBENDER_ASSET = os.environ["MINDBENDER_ASSET"]
        MINDBENDER_SILO = os.environ["MINDBENDER_SILO"]

        context = instance.context

        # Metadata
        #  _________
        # |         |.key = value
        # |         |
        # |         |
        # |         |
        # |         |
        # |_________|
        #
        stagingdir = instance.data.get("stagingDir")
        fname = os.path.join(stagingdir, ".metadata.json")

        root = os.environ["MINDBENDER_ASSETPATH"]
        instancedir = os.path.join(root, "publish", instance.data["subset"])

        try:
            os.makedirs(instancedir)
        except OSError as e:
            if e.errno != errno.EEXIST:  # Already exists
                self.log.critical("An unexpected error occurred.")
                raise

        versiondir = os.path.join(
            instancedir,
            api.format_version(version["name"])
        )

        try:
            with open(fname) as f:
                version_1_0 = json.load(f)

        except IOError:
            version_1_0 = dict(version, **{
                "schema": "mindbender-core:version-1.0",

                # Hard-coded during transition
                "path": versiondir.replace("\\", "/"),
                "representations": list(),

                "version": version["name"],

                # Used to identify family of assets already on disk
                "families": instance.data.get("families", list()) + [
                    instance.data.get("family")
                ],

                "time": context.data["time"],
                "timeFormat": "%Y%m%dT%H%M%SZ",
                "author": context.data["user"],

                # Record within which silo this asset was made.
                "silo": os.environ["MINDBENDER_SILO"],

                # Collected by pyblish-maya
                "source": os.path.join(
                    "{root}",
                    os.path.relpath(
                        context.data["currentFile"],
                        os.path.join(
                            api.registered_root(),
                            os.environ["MINDBENDER_PROJECT"]
                        )
                    )
                ).replace("\\", "/"),

                # Discard database keys
                "parent": None,
            })

        for filename in instance.data.get("files", list()):
            name, ext = os.path.splitext(filename)
            version_1_0["representations"].append(
                {
                    "schema": "mindbender-core:representation-1.0",
                    "format": ext,
                    "path": os.path.join(
                        "{dirname}",
                        "%s{format}" % name,
                    ).replace("\\", "/"),

                    # Imprint shortcut to context
                    # for performance reasons.
                    "context": {
                        "project": MINDBENDER_PROJECT,
                        "asset": MINDBENDER_ASSET,
                        "silo": MINDBENDER_SILO,
                        "subset": subset["name"],
                        "version": version["name"],
                        "representation": ext[1:]
                    }
                }
            )

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
        with open(fname, "w") as f:
            json.dump(version_1_0, f, indent=4)

        self.log.info("Successfully wrote %s." % fname)
