import datetime
import json
import lzma
import os
import time

import pytz
import tweepy
from allauth.socialaccount.models import SocialApp, SocialToken
from celery.utils.log import get_task_logger
from django.utils import timezone

from albatross.celery import app

from .aggregators.cloud import CloudAggregator
from .aggregators.images import ImagesAggregator
from .aggregators.map import MapAggregator
from .aggregators.raw import RawAggregator
from .aggregators.search import SearchAggregator
from .aggregators.statistics import StatisticsAggregator
from .models import Archive
from .settings import LOOKBACK

logger = get_task_logger(__name__)


@app.task
def backfill(archive_id):
    """
    Attempt to loop backward through the Twitter REST API to collect as much
    older stuff as possible.

    :param archive_id:
    """

    archive = Archive.objects.get(pk=archive_id)

    # Re-use the RawAggregator, so the backfilled tweets will automatically be
    # consolidated as part of RawAggregator.finalise().
    aggregator = RawAggregator(archive)
    path = os.path.join(aggregator.cache_dir, "0.fjson.xz")

    # No sense in proceeding if this has already been done
    if os.path.exists(path):
        return

    logger.info("Backfilling for %s", archive)

    socialtoken = SocialToken.objects.get(account__user=archive.user)
    socialapp = SocialApp.objects.first()

    auth = tweepy.OAuthHandler(socialapp.client_id, socialapp.secret)
    auth.set_access_token(socialtoken.token, socialtoken.token_secret)

    window_limit = timezone.now() - datetime.timedelta(minutes=LOOKBACK)
    cursor = tweepy.Cursor(tweepy.API(auth).search, archive.query)
    collected_ids = []

    with lzma.open(path, "wb") as f:

        try:

            for tweet in cursor.items():

                # As we're going backward through time, we need to account for
                # the possibility of the same tweet coming through more than
                # once.
                if tweet.id in collected_ids:
                    continue

                if pytz.UTC.localize(tweet.created_at) < window_limit:
                    break

                logger.debug(f"Backfilling: {tweet.created_at}: {tweet.text}")

                f.write(
                    bytes(
                        json.dumps(
                            tweet._json,
                            ensure_ascii=False,
                            separators=(",", ":")
                        ) + "\n",
                        "UTF-8"
                    )
                )

                collected_ids.append(tweet.id)

        except tweepy.error.TweepError:
            pass


@app.task
def collect(class_name, archive_id, tweets, is_final=False):
    """
    1. Pull in the cached copy of all stats from the cache.
    2. Update the stats dict from these tweets and re-cache it.
    3. Process the stats down into an aggregate and write that to the db.
    """

    if is_final:
        logger.info("Rolling up archive #%s", archive_id)
        time.sleep(60 * 5)

    classes = {
        "raw": RawAggregator,
        "statistics": StatisticsAggregator,
        "cloud": CloudAggregator,
        "map": MapAggregator,
        "search": SearchAggregator,
        "images": ImagesAggregator
    }

    archive = Archive.objects.get(pk=archive_id)
    aggregator = classes[class_name](archive)
    aggregator.collect(tweets)
    aggregator.generate()

    if is_final:
        aggregator.finalise()
