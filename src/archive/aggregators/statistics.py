import collections
import copy
import datetime
import json
import math
import os
import re

import pycountry
from django.conf import settings
from django.utils import timezone

from .base import Aggregator


class StatisticsAggregator(Aggregator):

    SENTIMENT_THRESHOLD = 0.6
    SENTIMENT_SPLIT_REGEX = re.compile(r"\W+")

    TIME_FORMATS = {
        "twitter": "%a %b %d %H:%M:%S %z %Y",
        "iso": "%Y-%m-%dT%H:00:00%z",
    }

    DEFAULT_AGGREGATE = {
        "makeup": {"Retweets": 0, "Original Content": 0, "Replies": 0},
        "languages": collections.defaultdict(int),
        "urls": 0,
        "countries": {"complete": collections.defaultdict(int)},
        "hashtags": collections.defaultdict(int),
        "hours": collections.defaultdict(int),
        "mentions": collections.defaultdict(int),
        "retweetees": collections.defaultdict(int),
        "total": 0,
        "sentiments": {"Positive": 0, "Negative": 0, "Neutral": 0}
    }

    def __init__(self, archive):

        super().__init__(archive)

        self.read_cache()
        self._set_afinn_db()

    def collect(self, tweets):

        aggregate = copy.deepcopy(self.DEFAULT_AGGREGATE)

        for tweet in tweets:

            aggregate["languages"][self.get_language(tweet)] += 1

            if "entities" in tweet:

                # URL Count
                if "urls" in tweet["entities"]:
                    aggregate["urls"] += len(tweet["entities"]["urls"])

                # Hashtags
                if "hashtags" in tweet["entities"]:
                    for hashtag in tweet["entities"]["hashtags"]:
                        hash_text = hashtag["text"].lower()
                        if not hash_text == self.archive.hashless_query:
                            aggregate["hashtags"][hash_text] += 1

                # Mentions
                if "user_mentions" in tweet["entities"]:
                    for mention in tweet["entities"]["user_mentions"]:
                        aggregate["mentions"][mention["screen_name"]] += 1

            # Countries
            if "place" in tweet and tweet["place"]:
                if "country_code" in tweet["place"]:
                    country = tweet["place"]["country_code"].lower()
                    if country:
                        aggregate["countries"]["complete"][country] += 1

            # Times
            created = datetime.datetime.strptime(
                tweet["created_at"],
                self.TIME_FORMATS["twitter"]
            ).strftime(self.TIME_FORMATS["iso"])
            aggregate["hours"][created] += 1

            # Tweet types
            if tweet["in_reply_to_user_id"]:
                aggregate["makeup"]["Replies"] += 1
            elif "retweeted_status" in tweet:
                aggregate["makeup"]["Retweets"] += 1
                user = tweet["retweeted_status"]["user"]["screen_name"]
                aggregate["retweetees"][user] += 1

            sentiment = self._get_sentiment(tweet)
            if sentiment > self.SENTIMENT_THRESHOLD:
                aggregate["sentiments"]["Positive"] += 1
            elif sentiment < self.SENTIMENT_THRESHOLD * -1:
                aggregate["sentiments"]["Negative"] += 1
            else:
                aggregate["sentiments"]["Neutral"] += 1

            aggregate["total"] += 1

        aggregate["makeup"]["Original Content"] = \
            aggregate["total"] - \
            aggregate["makeup"]["Retweets"] - \
            aggregate["makeup"]["Replies"]

        self.write_cache(aggregate)

    def generate(self):
        
        aggregate = self.read_cache()

        aggregate["makeup"] = list(aggregate["makeup"].items())

        aggregate["languages"] = self._simplify_statistic(
            self._translate_from_codes(aggregate["languages"], "languages")
        )
        aggregate["countries"]["pie"] = self._simplify_statistic(
            self._translate_from_codes(
                aggregate["countries"]["complete"].copy(),
                "countries"
            )
        )

        for group in ("hashtags", "mentions", "retweetees"):
            aggregate[group] = self._simplify_statistic(aggregate[group])

        aggregate["hours"] = self._hour_ranges(aggregate["hours"])
        aggregate["sentiments"] = list(aggregate["sentiments"].items())

        self.archive.statistics = json.dumps(aggregate, separators=(",", ":"))
        self.archive.statistics_generated = timezone.now()
        self.archive.total = aggregate["total"]

        self.archive.save(update_fields=(
            "statistics",
            "statistics_generated",
            "total"
        ))

    def update_aggregate(self, aggregate, addendum):

        self.update_aggregate_dict(aggregate["makeup"], addendum["makeup"])
        self.update_aggregate_dict(aggregate["languages"], addendum["languages"])  # NOQA: E501
        self.update_aggregate_dict(aggregate["countries"]["complete"], addendum["countries"]["complete"])  # NOQA: E501
        self.update_aggregate_dict(aggregate["hashtags"], addendum["hashtags"])
        self.update_aggregate_dict(aggregate["mentions"], addendum["mentions"])
        self.update_aggregate_dict(aggregate["retweetees"], addendum["retweetees"])  # NOQA: E501
        self.update_aggregate_dict(aggregate["hours"], addendum["hours"])
        self.update_aggregate_dict(aggregate["sentiments"], addendum["sentiments"])  # NOQA: E501

        aggregate["total"] += addendum["total"]
        aggregate["urls"] += addendum["urls"]

    @staticmethod
    def _translate_from_codes(stats, library):

        r = {}
        for code, total in stats.items():
            try:
                r[getattr(pycountry, library).lookup(code).name] = total
            except LookupError:
                pass

        if library == "languages" and "und" in stats:
            r["Undefined"] = stats["und"]

        return r

    @staticmethod
    def _simplify_statistic(stats):
        """
        Sort and limit the size of the result to a threshold number of results,
        lumping everything else into an "other" category.
        """

        # Whittle down the stats to a maximum of a top 8
        top = []
        for k, v in stats.items():
            if not top or v > min(_[1] for _ in top):
                top.append((k, v))
            top = sorted(top, key=lambda _: _[1], reverse=True)[:8]

        stats["*"] = 0
        threshold = sum([v for k, v in stats.items()]) / 12.5  # 1/8 of 100
        top_names = [_[0] for _ in top]
        delete = []

        for name, subtotal in stats.items():
            if name == "*":
                continue
            if name not in top_names:
                if subtotal < threshold:
                    stats["*"] += subtotal
                    delete.append(name)

        for name in delete:
            del(stats[name])

        return sorted(  # Second sort to put "Other" at the bottom
            sorted(  # First sort to get the 8 winners
                list(stats.items()),
                key=lambda _: _[1],
                reverse=True
            )[:8],
            key=lambda _: 0 if _[0] == "*" else _[1],
            reverse=True
        )

    @staticmethod
    def _hour_ranges(hours):
        r = {"times": [], "data": []}
        for k, v in list(sorted(hours.items(), key=lambda _: _[0])):
            r["times"].append(k)
            r["data"].append(v)
        return r

    def _set_afinn_db(self):
        db = os.path.join(
            settings.BASE_DIR, "archive", "db", "sentiment.json")
        with open(db) as f:
            self._afinn = json.load(f)

    def _get_sentiment(self, tweet):
        text = self.get_complete_text(tweet)
        text = self._split_camel_case(text.replace("#", ""))
        words = self.SENTIMENT_SPLIT_REGEX.split(text.lower())
        sentiments = [self._afinn.get(s, 0) for s in words]
        if not sentiments:
            return 0
        return round(sum(sentiments) / math.sqrt(len(sentiments)), 2)

    @staticmethod
    def _split_camel_case(s):
        matches = re.finditer(
            '.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', s)
        return " ".join([m.group(0) for m in matches])
