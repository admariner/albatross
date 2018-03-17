import datetime
import glob
import json
import lzma
import os
import re
import uuid

from .base import Aggregator


class RawAggregator(Aggregator):
    """
    The component that actually writes the raw data to the archive file.
    """

    def collect(self, tweets):
        """
        As we're not dealing with a python aggregate, but rather a list of
        strings we want to store as one big list, we don't call .write_cache()
        here.  Instead we roll our own.
        """

        if not tweets:
            return

        first_tweet_time = datetime.datetime.strptime(
            tweets[0]["created_at"],
            "%a %b %d %H:%M:%S +0000 %Y"
        ).isoformat()

        key = re.sub(r"[^\w]", "", first_tweet_time) + str(uuid.uuid4())
        path = os.path.join(self.cache_dir, f"{key}.fjson.xz")
        with lzma.open(path, "wb") as f:
            for tweet in tweets:
                f.write(bytes(
                    json.dumps(tweet, separators=(",", ":")), "UTF-8"
                ) + b"\n")

        self.archive.size = 0
        for f in os.listdir(self.cache_dir):
            self.archive.size += os.stat(
                os.path.join(self.cache_dir, f)
            ).st_size

        self.archive.save(update_fields=("size",))

    def finalise(self):

        with lzma.open(self.archive.get_raw_path(), "wb") as w:
            for path in glob.glob(os.path.join(self.cache_dir, "*")):
                with lzma.open(path, "rb") as r:
                    w.write(r.read())
                os.unlink(path)

        super().finalise()
