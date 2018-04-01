# Changelog

## 1.2.0 (Cersei Baratheon)

* Refactored the finalisation step to handle race conditions where you're
  running so many parallel celery processes that the final aggregations can
  step on each other's toes.
* This release also includes the addition of the ArchiveSegment model, which
  we use to inform the above decision-making process.

## 1.1.0 (Bellatrix Lestrange)

* Refactored the architecture to abandon a single threaded consumer in favour
  of multiple celery tasks.
* Tweets are now processed in batches 1000 at a time, or every 5 minutes,
  whichever comes first.

## 1.0.0 (Apocalypse)

* Initial Release
