# Changelog

## 1.2.0 (Bellatrix Lestrange)

* Refactored the architecture to abandon a single threaded consumer in favour
  of multiple celery tasks.
* Tweets are now processed in batches 1000 at a time, or every 5 minutes,
  whichever comes first.

## 1.1.0 (Apocalypse)

* Initial Release
