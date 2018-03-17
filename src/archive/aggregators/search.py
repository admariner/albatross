import datetime

import pytz
from django.db import IntegrityError
from django.utils import timezone

from ..models import Tweet
from .base import Aggregator


class SearchAggregator(Aggregator):

    def collect(self, tweets):

        if not self.archive.allow_search:
            return

        for tweet in tweets:
            try:
                Tweet.objects.create(
                    id=tweet["id"],
                    archive=self.archive,
                    created=datetime.datetime(
                        *datetime.datetime.strptime(
                            tweet["created_at"],
                            "%a %b %d %H:%M:%S +0000 %Y"
                        ).timetuple()[:6],
                        tzinfo=pytz.UTC
                    ),
                    mentions=self._get_mentions_from_tweet(tweet),
                    hashtags=self._get_hashtags_from_tweet(tweet),
                    text=tweet["text"]
                )
            except IntegrityError:
                pass  # Sometimes we get >1 of the same tweet.  Weird.

    def generate(self):
        self.archive.search_generated = timezone.now()
        self.archive.save(update_fields=("search_generated",))

    @staticmethod
    def _get_hashtags_from_tweet(tweet):
        r = []
        if "entities" in tweet and "hashtags" in tweet["entities"]:
            for hashtag in tweet["entities"]["hashtags"]:
                r.append(hashtag["text"])
        return list(set(r))

    @staticmethod
    def _get_mentions_from_tweet(tweet):
        r = []
        if "entities" in tweet and "user_mentions" in tweet["entities"]:
            for mention in tweet["entities"]["user_mentions"]:
                r.append(mention["screen_name"])
        return list(set(r))
