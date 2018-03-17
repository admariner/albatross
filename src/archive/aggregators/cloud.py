import copy
import json
import re

from django.utils import timezone

from .base import Aggregator


class CloudAggregator(Aggregator):

    DEFAULT_AGGREGATE = {}

    BUCKETS = 300
    BUCKET_SIZES = range(10, 310)

    ANTI_PUNCTUATION_REGEX = re.compile(
        '["\[\]{}:;,./<>?!@#$%^&*()\-=+…\'\d|‘’“”]')

    STOP_WORDS = {
        "*": [
            "rt",
        ],
        "en": [
            "and", "or", "you", "a", "to", "be", "by", "on", "from", "is",
            "at", "it", "its", "of", "but", "do", "so", "for", "not", "the",
            "in", "are", "will", "this", "as", "that", "thats", "with", "an",
            "than", "amp",
        ],
        "el": [
            "και", "αν", "τον", "τα", "την", "τη", "το", "είναι", "ο", "ότι",
            "του", "σε", "θα", "δεν", "για", "που", "οι", "να", "ή", "η",
            "στο", "με", "ωστε", "μου", "τι", "αυτο", "αυτό", "στις", "τις",
            "κι", "απο", "τους", "αλλά", "αλλα", "από", "της", "στην", "ειναι",
            "σας", "μετά", "ακόμα", "ακόμη", "πως", "των", "ήδη", "οτι", "μην",
        ],
        "nl": [
            "de", "het", "voor", "en", "naar", "met", "dit", "is", "die",
            "ook", "te", "bij", "zo", "om", "wat", "op", "van", "in", "ik",
            "dat", "er", "aan", "tot", "een",
        ],
        "fr": [
            "le", "la", "de", "du",
        ]
    }

    def __init__(self, archive):
        
        super().__init__(archive)

        self.query_regex = re.compile(re.escape(archive.query), re.IGNORECASE)

    def collect(self, tweets):

        aggregate = copy.deepcopy(self.DEFAULT_AGGREGATE)

        for tweet in tweets:

            text = self.query_regex.sub("", self.get_complete_text(tweet))

            for word in text.split():

                word = self.ANTI_PUNCTUATION_REGEX.sub(
                    "", word.lower()).strip()

                stop_words = self._get_stop_words(self.get_language(tweet))
                if word and word not in stop_words:
                    if "http" not in word:
                        if word not in aggregate:
                            aggregate[word] = 0
                        aggregate[word] += 1

        self.write_cache(aggregate)

    def generate(self):

        aggregate = self.read_cache()

        # Since we need a min & max, we kick any index less than 2.
        if len(list(aggregate.keys())) < 2:
            return

        # Sort and reduce the aggregate
        index = sorted(
            aggregate.items(), key=lambda _: _[1], reverse=True)[1:500]

        frequency_max = index[0][1]
        frequency_min = index[-1][1]
        bucket_size = (frequency_max + 1 - frequency_min) / self.BUCKETS

        cloud = []
        for word, total in index:
            bucket = int((total - frequency_min) / bucket_size)
            cloud.append({
                "text": word,
                "size": self.BUCKET_SIZES[bucket]
            })

        self.archive.cloud = json.dumps(cloud, separators=(",", ":"))
        self.archive.cloud_generated = timezone.now()
        self.archive.save(update_fields=("cloud", "cloud_generated"))

    def update_aggregate(self, aggregate, addendum):
        self.update_aggregate_dict(aggregate, addendum)

    def _get_stop_words(self, language):
        return self.STOP_WORDS["*"] + self.STOP_WORDS.get(language, [])
