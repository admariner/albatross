import glob
import lzma
import os

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from albatross.logging import LogMixin


class Archive(LogMixin, models.Model):

    STATUS_ACTIVE = 1
    STATUS_DISABLED = 2
    STATUSES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_DISABLED, "Disabled")
    )

    ARCHIVES_DIR = os.path.join(settings.MEDIA_ROOT, "archives")
    ARCHIVES_URL = os.path.join(settings.MEDIA_URL, "archives")

    query = models.CharField(max_length=32)
    user = models.ForeignKey(
        "users.User",
        related_name="archives",
        null=True,
        on_delete=models.PROTECT
    )
    started = models.DateTimeField(auto_created=True)
    stopped = models.DateTimeField(
        blank=True, null=True, help_text="Defaults to start + 24hours")

    is_running = models.BooleanField(default=False)
    allow_consumption = models.BooleanField(
        default=True,
        help_text="Should incoming tweets actually be consumed or just left "
                  "in the queue?"
    )
    allow_search = models.BooleanField(default=False)
    last_distilled = models.DateTimeField(blank=True, null=True)
    status = models.PositiveIntegerField(
        choices=STATUSES, default=STATUS_ACTIVE)

    cloud = models.TextField(blank=True)
    statistics = models.TextField(blank=True)
    images = models.TextField(blank=True)

    # These are used to gauge availability of the distillations
    cloud_generated = models.DateTimeField(blank=True, null=True)
    map_generated = models.DateTimeField(blank=True, null=True)
    search_generated = models.DateTimeField(blank=True, null=True)
    statistics_generated = models.DateTimeField(blank=True, null=True)
    images_generated = models.DateTimeField(blank=True, null=True)

    colour_overrides = models.TextField(
        blank=True,
        help_text="A JSON field used to override the colours used by c3 in "
                  "generating pie charts."
    )

    total = models.BigIntegerField(default=0)
    size = models.BigIntegerField(
        default=0, help_text="The size, in bytes, of the tweets field")

    class Meta:
        ordering = ("-started",)

    def __str__(self):
        return self.query

    @property
    def hashless_query(self):
        return self.query.replace("#", "").lower()

    @property
    def rate(self):
        stop_time = self.stopped or timezone.now()
        return self.total / (stop_time - self.started).total_seconds()

    def calculate_size(self):
        path = os.path.join(self.ARCHIVES_DIR, "raw", f"{self.pk:05}*fjson.xz")
        return sum([os.stat(f).st_size for f in glob.glob(path)])

    def get_raw_path(self):
        """
        Generate a conforming file name for this archive.
        """
        return os.path.join(self.ARCHIVES_DIR, "raw", f"{self.pk:09}.fjson.xz")

    def get_tweets(self):
        """
        Collect all tweets from all compressed files and give us a generator
        yielding one tweet per iteration.
        """
        try:
            with lzma.open(self.get_raw_path()) as f:
                for line in f:
                    yield str(line.strip(), "UTF-8")
        except EOFError:
            pass

    def get_tweets_url(self):
        if not os.path.exists(self.get_raw_path()):
            return None
        return os.path.join(self.ARCHIVES_URL, "raw", f"{self.pk:09}.fjson.xz")

    def get_map_path(self):
        return os.path.join(
            self.ARCHIVES_DIR, "map", f"{self.pk:09}.json.xz")

    def get_map_url(self):
        return os.path.join(
            self.ARCHIVES_URL, "map", f"{self.pk:09}.json.xz")

    def get_absolute_url(self):
        return "/archives/{}/statistics/".format(self.pk)

    def stop(self):
        self.stopped = timezone.now()
        self.save(update_fields=("stopped",))


class ArchiveSegment(models.Model):

    TYPE_RAW = "raw"
    TYPE_CLOUD = "cloud"
    TYPE_STATS = "statistics"
    TYPE_IMAGES = "images"
    TYPE_MAP = "map"
    TYPE_SEARCH = "search"
    TYPES = (
        (TYPE_RAW, "Raw"),
        (TYPE_CLOUD, "Cloud"),
        (TYPE_STATS, "Statistics"),
        (TYPE_IMAGES, "Images"),
        (TYPE_MAP, "Map"),
        (TYPE_SEARCH, "Search")
    )

    type = models.CharField(max_length=10, choices=TYPES)
    archive = models.ForeignKey(
        Archive, related_name="segments", on_delete=models.CASCADE)

    start_time = models.DateTimeField(default=timezone.now)
    stop_time = models.DateTimeField(null=True)

    def __str__(self):
        if self.stop_time:
            return f"Completed {self.type} segment of {self.archive}"
        return f"Incomplete {self.type} segment of {self.archive}"


class Event(models.Model):
    """
    Arbitrary event values for an archive that help explain behaviour.  These
    are plotted on the hours chart.
    """

    archive = models.ForeignKey(
        Archive, related_name="events", on_delete=models.CASCADE)
    time = models.DateTimeField()
    label = models.CharField(max_length=64)

    def __str__(self):
        return self.label


class Tweet(models.Model):
    """
    Created for the purpose of allowing searches of specific collections.  This
    is probably not a good idea and it's yet to be used, since large
    collections tend to produce Very Large Databases.  If we're going to have
    search, something like ElasticSearch makes more sense, but until that's
    figured out, this will stick around.
    """
    id = models.BigIntegerField(primary_key=True)
    archive = models.ForeignKey(
        "archive.Archive", related_name="tweets", on_delete=models.CASCADE)
    created = models.DateTimeField(db_index=True)
    mentions = ArrayField(
        models.CharField(max_length=64), blank=True, null=True)
    hashtags = ArrayField(
        models.CharField(max_length=280), blank=True, null=True)
    text = models.CharField(max_length=256, db_index=True)
