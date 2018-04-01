from sys import stderr
from datetime import timedelta
from django.utils import timezone
from tweepy import StreamListener

from albatross.logging import LogMixin
from users.models import User

from ..models import Archive, ArchiveSegment
from ..tasks import collect
from .mixins import NotificationMixin


class AlbatrossListener(LogMixin, NotificationMixin, StreamListener):

    BUFFER_SIZE = 999  # 1 less than the total tweets we want per batch
    AGGREGATION_WINDOW = timedelta(seconds=60)  # Max time between aggregations

    def __init__(self, archives, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # A temporary storage for use in exception forensics
        self.raw_data = None

        # All archives in a stream belong to the same user
        self.user = archives[0].user

        self.channels = []
        for archive in archives:
            self.channels.append({
                "archive": archive,
                "buffer": [],
                "last-aggregation": timezone.now()
            })

    def on_data(self, raw_data):
        self.raw_data = raw_data
        return StreamListener.on_data(self, raw_data)

    def on_status(self, status):

        self.logger.debug(".")

        for channel in self.channels:

            query = channel["archive"].query.lower()

            if query in status.text.lower():

                self.on_vetted_tweet(channel, status)

            elif hasattr(status, "retweeted_status"):

                if query in status.retweeted_status.text.lower():
                    self.on_vetted_tweet(channel, status)
                elif hasattr(status.retweeted_status, "quoted_status"):
                    if query in status.retweeted_status.quoted_status["text"].lower():  # NOQA: E501
                        self.on_vetted_tweet(channel, status)

            elif hasattr(status, "quoted_status"):

                if query in status.quoted_status["text"].lower():
                    self.on_vetted_tweet(channel, status)

    def on_vetted_tweet(self, channel, status):
        """
        IMPORTANT: status._json isn't JSON at all, but a Python dictionary
        IMPORTANT: *generated* from the initial JSON.

        This might be further optimised by overriding on_data and skipping the
        re-JSONing step.
        """

        now = timezone.now()
        channel["buffer"].append(status._json)

        do_aggregation = False
        if now - channel["last-aggregation"] > self.AGGREGATION_WINDOW:
            do_aggregation = True
        elif len(channel["buffer"]) > self.BUFFER_SIZE:
            do_aggregation = True

        if do_aggregation:
            for class_name in [_[0] for _ in ArchiveSegment.TYPES]:
                collect.delay(
                    class_name,
                    channel["archive"].pk,
                    channel["buffer"]
                )
            channel["buffer"] = []
            channel["last-aggregation"] = now

    def on_exception(self, exception):

        additional = "Source: {}".format(self.raw_data)

        self._alert(
            "Collector exception [listener]", exception, additional)

        stderr.write("\n\nEXCEPTION:\n{}\n\nSource: {}\n".format(
            exception, additional))

        self.close_log()

        return False

    def on_error(self, status_code):

        message = str(status_code)
        if status_code == 401:
            message = (
                f"Twitter issued a 401 for {self.user}, so they've been "
                f"kicked."
            )
            self.user.status = User.STATUS_DISABLED
            self.user.save(update_fields=("status",))

        self._alert("Collector Twitter error", message)

        stderr.write("ERROR: Twitter responded with {}".format(status_code))

        self.close_log()

        return False

    def on_disconnect(self, notice):
        """
        This is what happens if *Twitter* sends a disconnect, not if we
        disconnect from the stream ourselves.
        """
        self._alert("Collector disconnect", str(notice))
        stderr.write("\n\nTwitter disconnect: {}\n\n\n".format(notice))
        self.close_log()
        return False

    def close_log(self):

        for channel in self.channels:

            # Refresh the archive instance in case things have changed
            archive = Archive.objects.get(pk=channel["archive"].pk)

            for class_name in [_[0] for _ in ArchiveSegment.TYPES]:

                collect.delay(
                    class_name,
                    archive.pk,
                    channel["buffer"],
                    is_final=archive.stopped <= timezone.now()
                )
                channel["buffer"] = []

        Archive.objects.filter(
            pk__in=[__["archive"].pk for __ in self.channels]
        ).update(
            is_running=False
        )
