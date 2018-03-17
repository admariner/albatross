import copy
import glob
import json
import lzma
import os
import shutil
import uuid

from django.conf import settings

from albatross.logging import LogMixin


class Aggregator(LogMixin):

    CACHE_DIR = os.path.join(settings.MEDIA_ROOT, "cache")

    DEFAULT_AGGREGATE = None

    def __init__(self, archive):

        self.archive = archive

        self.cache_dir = os.path.join(
            self.CACHE_DIR,
            str(archive.pk),
            self.__class__.__name__.lower().replace("aggregator", "")
        )

        os.makedirs(self.cache_dir, exist_ok=True)

        self.logger.debug("Aggregate logger using %s ready", self.cache_dir)

    def write_cache(self, aggregate):
        """
        Write aggregate data to disk.  This is later picked up in
        ``.read_cache()``.
        """

        path = os.path.join(self.cache_dir, f"{uuid.uuid4()}.json.xz")

        self.logger.info("Writing aggregate for %s to %s", self.archive, path)

        with lzma.open(path, "wb") as f:
            f.write(
                bytes(json.dumps(aggregate, separators=(",", ":")), "UTF-8")
            )

    def read_cache(self):
        """
        Return a complete aggregate from all the cache files on-disk, including
        the one recently generated in this pass.
        """

        aggregate = copy.deepcopy(self.DEFAULT_AGGREGATE)

        self.logger.info(
            "Reading aggregate for %s from %s", self.archive, self.cache_dir)

        for path in glob.glob(os.path.join(self.cache_dir, "*")):
            with lzma.open(path, "rb") as f:
                self.update_aggregate(
                    aggregate,
                    json.loads(f.read())
                )

        return aggregate

    def clear_cache(self):
        """
        Remove the cache files.  The various try/except blocks are there to
        account for race conditions where the directory may already have been
        deleted.
        """

        try:
            self.logger.info("Clearing out %s", self.cache_dir)
            shutil.rmtree(self.cache_dir)
        except FileNotFoundError:
            pass

        parent = os.path.dirname(self.cache_dir)

        if not os.listdir(parent):
            try:
                self.logger.info("Clearing out parent dir: %s", parent)
                shutil.rmtree(parent)
            except FileNotFoundError:
                pass

    def update_aggregate(self, aggregate, addendum):
        if isinstance(aggregate, dict):
            aggregate.update(addendum)
        elif isinstance(aggregate, list):
            aggregate += addendum
        else:
            raise NotImplementedError()

    @staticmethod
    def update_aggregate_dict(primary, update):
        for key, value in update.items():
            if key not in primary:
                primary[key] = 0
            primary[key] += update[key]

    @classmethod
    def get_complete_text(cls, tweet):
        """
        Twitter likes to strictly define `text` as 280characters, which means
        that if a tweet is retweeted or quoted, the text of the tweet is
        mangled to contain things like a prefixed `RT ` and a suffixed `...`.
        This is how we can always be sure we get the actual text of the tweet
        in question.
        """

        if "retweeted_status" in tweet:
            return cls.get_complete_text(tweet["retweeted_status"])

        if "quoted_status" in tweet:
            return cls.get_complete_text(tweet["quoted_status"])

        return tweet["text"]

    @staticmethod
    def get_language(tweet):
        """
        Twitter has a very strange way of identifying languages
        """

        r = tweet.get("lang") or tweet["user"].get("lang")

        if not r or r in ("in", "enen", "enes", "fil"):
            r = "und"

        r = r.lower()
        if r in ("en-gb",):
            r = "en"
        if r in ("zh-cn",):
            r = "zh"

        return r

    @classmethod
    def get_original_user(cls, tweet):

        if "retweeted_status" in tweet:
            return cls.get_original_user(tweet["retweeted_status"])

        if "quoted_status" in tweet:
            return cls.get_original_user(tweet["quoted_status"])

        return tweet["user"]["screen_name"]

    @classmethod
    def get_url(cls, tweet):

        if "retweeted_status" in tweet:
            return cls.get_url(tweet["retweeted_status"])

        if "quoted_status" in tweet:
            return cls.get_url(tweet["quoted_status"])

        return "https://twitter.com/{}/status/{}".format(
            tweet["user"]["screen_name"],
            tweet["id"]
        )

    def collect(self, tweet):
        raise NotImplementedError("Must be defined by subclass")

    def generate(self):
        pass

    def finalise(self):
        self.clear_cache()
