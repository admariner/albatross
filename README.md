# Albatross

A Twitter live-data collector.  Keep an eye on your disk space ;-)


## What is This?

This project is largely an experiment that may one day grow into something
useful for more than just a handful of people.

> The idea is simple: Albatross is a way for you to capture everything said
> about something and then analyse the raw data yourself or let this site
> visualise it for you.

Say you're at a conference that's managing the conversation with the hashtag:
`#awesomeconference`.  You're participating when you can, but it would be
really nice to be able to collect everything everyone said during the
conference and draw some conclusions from it.

Maybe you want to do some analytics based on some natural language processing,
or want to chart the number of times a particular phrase was mentioned within
that hashtag.  Whatever you want to do with the data, just fill out the form
here with the hashtag in question, hit `submit` and when the conference ends,
you've got all the data to play with.

Similarly this can be used for international events, or national disaster
coverage.  Plot on a map the tweets posted about your subject and when, or
analyse the content of the tweets to see what different regions are saying
about a particular subject.


## Can You Do That For Me?

Analytics and visualisation is hard, and not everyone has the time or
inclination to figure out how to parse the JSON blobs Twitter makes available
via their API.  Thankfully, Albatross has a bunch of built-in visualisations
that might be sufficient for many people, but if you need something more
customised, you can open an issue and I can give it a shot.  Of course,
contributions are welcome!


## Data Format

The raw data is available as a xzip-compressed "fjson" file.  This is just a
plain text file, with one JSON object per line.  You can decompress this file
in Linux & Mac with the `xz` utility, or use a common program like WinRar in
Windows.


## Setup

Everything is dockerised, so you need:

* Docker
* Docker Compose
* A `.env` file defining the following values:
    ```
    PYTHONUNBUFFERED=1
    TWITTER_CONSUMER_KEY=<secret>
    TWITTER_CONSUMER_SECRET=<secret>
    ```
  Note that the values aren't wrapped in quotes.  You can thank Docker for
  that.

  You can also optionally set some other values here:
    * You can configure the externally-available ports for the web service and
      RabbitMQ by setting `WEB_PORT=<number>` and `RABBITMQ_PORT=<number>`
      respectively.
    * You can get more output from Albatross by changing the log level.  Set
      `DJANGO_LOG_LEVEL=INFO` or even `DJANGO_LOG_LEVEL=DEBUG` if you want.
    * If you're planning on doing some development, you can turn global
      debugging on by setting `DEBUG=true`
    * You can also change Django's `SECRET_KEY` by setting that value here.


### Instructions

#### 1. Setup your own Twitter app.

Albatross needs a `CONSUMER_KEY` and `CONSUMER_SECRET` from Twitter in order to
operate.  To get these, you'll need to log into Twitter and visit [their app site](https://apps.twitter.com/).
Once there, click the `Create New App` button, and put whatever you want into
the form fields that follow.  Just make sure that for the last box,
`Callback URL`, you put in `http://127.0.0.1:8000/accounts/twitter/login/callback/`.

Once you've submitted the form, Twitter should present you with a page that has
4 tabs, one of which is labelled `Keys and Access Tokens`.  Click that, and it
will reveal two values:

* Consumer Key (API Key)
* Consumer Secret (API Secret)

These are your `TWITTER_CONSUMER_KEY` and `TWITTER_CONSUMER_SECRET` values
respectively.  Put them into your `.env` file (mentioned above).

#### 2. Clone the repo

Now that you have the credentials to identify yourself to Twitter, you just
need the Albatross code.  You can do this with `git`, which is handy 'cause you
can use git later to keep your code up to date.

```bash
$ git clone https://github.com/danielquinn/albatross.git
```

If you don't have or want to use git, you can just download a copy of Albatross
from Github and unzip it into a directory somewhere.

#### 3. Add the environment config file mentioned above.

Before you run anything, you need to have that `.env` file mentioned above. At
the very least, it should contain your values for `TWITTER_CONSUMER_KEY` and
`TWITTER_CONSUMER_SECRET` as well as `PYTHONUNBUFFERED=1`.

```bash
$ cd albatross
$ ${EDITOR} .env
```

#### 4. Start the containers

When the above is complete, you just need to tell Docker to run all of the
required bits and keep them running.  To do that, you use docker-compose:

```bash
$ docker-compose up
```

Note that the startup process is such that some of the components, like the
collector & webserver may fail as the database isn't ready yet.  That's ok,
they should be re-started automatically at which point they'll retry to connect
to the database.  Eventually, all of the components will level out and
Albatross will be ready.

After that, just visit https://localhost:8000 and login with Twitter to start
your first collection.


## Architecture

Here's what it's doing under the hood:

![Architecture](https://raw.githubusercontent.com/danielquinn/albatross/master/docs/architecture.png)


## State of the Project

I wrote this back in 2015 as an attempt to start a company doing this sort of
thing for people & businesses.  However, not long after I had a working model,
Twitter started acting more and more hostile to projects that would dare store
"their" data, so I gave up on it.

In 2018 however, I repurposed Albatross into a self-hosted model to help a
friend do some research for her PhD.  If it works for her, it may work for
others, so I decided to polish it up a bit and re-license it under the AGPL3.
