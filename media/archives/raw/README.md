# Raw Data

This is where Albatross will write the final compressed version of your
collection.  The file format is *".fjson.xz"* which is to say each file
contains lots of tweets:

* Each tweet is a single self-contained [JSON](https://en.wikipedia.org/wiki/JSON)
  string.
* Only one tweet per line
* The file is then compressed with [x-zip](https://en.wikipedia.org/wiki/Xz) to
  keep your hard drive from exploding.

To access the data, you have a few optionbs, but be careful if you're planning
to simply decompress the archive and open it in a text editor.  Compression for
this sort of data tends to be roughly **20:1**, so a file that's only 100MB can
expand to about **2GB**.  Reading that in a typical text editor isn't going to
be much fun.

Instead, I recommend you write a little code to access the data.  Doing it this
way will allow you to access the tweets individually if you like, and most
importantly, you can do it without decompressing it.

In Python, you'd do it something like this:

```python
import json
import lzma

with lzma.open("000000001.fjson.xz") as f:
    for line in f:
        tweet = json.loads(line)
        print(tweet["text"])  # At this point, `tweet` is just a dict
```
