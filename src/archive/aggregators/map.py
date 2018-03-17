import json
import lzma

from django.utils import timezone

from .base import Aggregator


class NoCoordinatesFound(Exception):
    pass


class MapAggregator(Aggregator):

    DEFAULT_AGGREGATE = []

    def collect(self, tweets):

        aggregate = self.DEFAULT_AGGREGATE.copy()

        for tweet in tweets:
            try:
                aggregate.append(self._get_refined_data(tweet))
            except NoCoordinatesFound:
                pass

        self.write_cache(aggregate)

    def generate(self):

        aggregate = self.read_cache()

        with lzma.open(self.archive.get_map_path(), "wb") as f:
            f.write(bytes(json.dumps(
                aggregate,
                separators=(",", ":"),
                sort_keys=True
            ), "UTF-8"))

        self.archive.map_generated = timezone.now()
        self.archive.save(update_fields=("map_generated",))

    def _get_refined_data(self, tweet):

        if "coordinates" not in tweet:
            if "place" not in tweet:
                raise NoCoordinatesFound()

        if self._tweet_contains_coordinates(tweet):
            coordinates = (
                round(tweet["coordinates"]["coordinates"][0], 8),
                round(tweet["coordinates"]["coordinates"][1], 8)
            )
        elif self._place_contains_bounding_box(tweet):
            coordinates = self._get_centre(
                tweet["place"]["bounding_box"]["coordinates"][0])
        else:
            raise NoCoordinatesFound()

        return [
            tweet["id_str"],
            tweet["user"]["screen_name"],
            tweet["text"],
            tweet["user"]["profile_image_url_https"],
            coordinates
        ]

    @staticmethod
    def _tweet_contains_coordinates(tweet):
        if "coordinates" in tweet:
            if tweet["coordinates"]:
                if "type" in tweet["coordinates"]:
                    if tweet["coordinates"]["type"] == "Point":
                        if tweet["coordinates"]["coordinates"]:
                            return True
        return False

    @staticmethod
    def _place_contains_bounding_box(tweet):
        if "place" not in tweet:
            return False
        if not tweet["place"]:
            return False
        if "bounding_box" not in tweet["place"]:
            return False
        if not tweet["place"]["bounding_box"]:
            return False
        if "coordinates" not in tweet["place"]["bounding_box"]:
            return False
        if not tweet["place"]["bounding_box"]["coordinates"]:
            return False
        if len(tweet["place"]["bounding_box"]["coordinates"]) > 1:
            return False
        return True

    @staticmethod
    def _get_centre(points):
        """
        Ripped shamelessly from http://stackoverflow.com/questions/18440823/

        Obviously, this doesn't work in cases where the bounding box overlaps
        the international date line, but since the box is typically very small,
        it's unlikely that'll ever happen given the locations of human
        habitation on Earth.
        """
        centroid = [0.0, 0.0]

        for point in points:
            centroid[0] += point[0]
            centroid[1] += point[1]

        total_points = len(points)
        centroid[0] /= total_points
        centroid[1] /= total_points

        return round(centroid[0], 8), round(centroid[1], 8)
