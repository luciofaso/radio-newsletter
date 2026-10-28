# Radio Newsletter

**Too many newsletters, never the time to read them? Have them read to you.**

Your newsletters arrive in several languages: English, French, Italian and more. Radio Newsletter reads the ones collected in a Gmail label, opens the linked articles, picks the best stories and turns them into a 20-minute radio show read by a single voice, **in the language you choose** (English, French or Italian out of the box). The episode lands in a private podcast feed, so you can listen in your podcast app while you cook, walk or drive.

## How it works

1. **Mail.** Reads the Gmail label of your choice (for example "Newsletter") over IMAP, **read-only**: no email is marked as read, moved or deleted. It takes the newsletters received since the last episode, up to 5 days (3 days on the first run).
2. **Selection.** A cheap model (Claude Haiku) picks up to 15 candidate stories, whatever their language, and discards promotions, events, job offers and sponsored content.
3. **Articles.** Opens the chosen links and extracts the text. Unreadable articles (paywalls, errors, too short) are dropped silently: the show never mentions them.
4. **Script.** A better model (Claude Sonnet) chooses 5 stories and writes the script in your language, translating as it goes: an opening with a summary, the stories, a closing. The style is sober, with rhythm and no hype.
5. **Voice.** Gemini-TTS on Google Cloud reads the script.
6. **Publishing.** ffmpeg builds an M4A file with **one chapter per story**, so you can skip what does not interest you. Audio and RSS feed go to Cloudflare R2, under a random, unguessable path. The show notes list the sources with links, so you can check what was told.

There is no database: the feed itself is the state. Each newsletter ends up in exactly one episode.

## What you need

- A Mac or Linux machine with **Python 3.11+** and **ffmpeg**.
- A **Gmail** account with your newsletters filed under a label.
- An **Anthropic** API key (text).
- A **Google Cloud** project with billing (voice).
- A **Cloudflare** account with R2 (hosting for the audio and the feed).

Setup takes about an hour.

## Costs

Rough estimates; check the providers' current pricing:

- **Voice:** about $0.03 per minute with `gemini-2.5-pro-tts` (about half with `gemini-2.5-flash-tts`), so about $0.60 for a 20-minute episode.
- **Text (LLM):** a few cents per episode, depending on how many newsletters you receive.
- **Cloudflare R2:** at these volumes it fits in the free tier.

With one episode every 2-3 days you stay under about $15 a month. At the end of each run the program prints the LLM tokens used and the minutes of audio generated. Still, set a spending limit on Anthropic and a budget alert on Google Cloud.

## Installation

### 1. Code

```bash
git clone https://github.com/<user>/<repository>.git
cd <repository>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Install ffmpeg (on a Mac: `brew install ffmpeg`).

All secrets go in `.env`, which git ignores.

### 2. Language

In `.env`, set `EPISODE_LANGUAGE` to `en`, `fr` or `it`. The newsletters can be in any language: only the episode follows this setting.

### 3. Gmail

1. Turn on 2-Step Verification for your Google account.
2. Create an app password at myaccount.google.com/apppasswords (16 characters).
3. In Gmail settings, "Forwarding and POP/IMAP": make sure IMAP is enabled.
4. Create a filter that files your newsletters under a label, for example "Newsletter", and make sure the label is visible in IMAP (Settings, Labels, "Show in IMAP" column).
5. In `.env`: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `GMAIL_FOLDER` (the label name).

### 4. Anthropic

1. Create an API key at console.anthropic.com and set a low monthly spending limit.
2. In `.env`: `ANTHROPIC_API_KEY`. `MODEL_SELECTION` and `MODEL_SCRIPT` already have a starting value; model IDs are listed in the Anthropic documentation.

### 5. Google Cloud (voice)

1. Create a Google Cloud project with billing and enable the "Agent Platform API" (formerly Vertex AI).
2. Create a service account with the "Agent Platform User" role.
3. In Credentials, create an API key **bound to that service account** and restricted to the Agent Platform API. A plain API key does not work with Gemini-TTS.
   - If your organization blocks the key creation, in the project's Organization Policies set `iam.managed.disableServiceAccountApiKeyCreation` to "Override parent's policy → Off" (this needs the Organization Policy Administrator role).
4. Create a monthly budget with an alert.
5. In `.env`: `GOOGLE_API_KEY` and `GOOGLE_CLOUD_PROJECT` (the project number). `TTS_MODEL` and `TTS_VOICE` already have a starting value.

### 6. Cloudflare R2

1. Create an R2 bucket, for example `radio-newsletter`.
2. Enable the bucket's public r2.dev URL. Cloudflare describes it as meant for development and rate-limited; for a single listener it is enough.
3. Create an R2 API token with read and write access to that bucket.
4. In `.env`: `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL` (the r2.dev URL).
5. Generate a random prefix and put it in `R2_SECRET_PREFIX`:
   ```bash
   python3 -c "import secrets;print(secrets.token_urlsafe(16))"
   ```
   Anyone who knows the feed URL can listen to your episodes: keep it to yourself.

## Usage

Try it first without spending on voice:

```bash
.venv/bin/python main.py --dump          # newsletters and articles only, no LLM: check what it reads
.venv/bin/python main.py --script-only   # selection and script, saved in out/<date>/, no voice
.venv/bin/python main.py --voice-sample  # reads only the first story of today's script, to try the voice
```

Then the full episode:

```bash
.venv/bin/python main.py                 # everything: script, voice, publishing
.venv/bin/python main.py --publish       # voice and publishing of the script already saved today, no LLM
```

At the end the program prints the feed URL. On an iPhone: Podcasts app, Library, "…" menu, "Follow a Show by URL", paste the URL. Podcast apps refresh private feeds with some delay: pull down on the show page to force a refresh.

## Make it yours

Almost everything changes without touching the code:

- **`prompts/script.md`**: who you are, what you like, the tone, the number and length of stories. The "The listener" section makes the biggest difference: describe yourself, your work, the languages you speak, and the name you want to be greeted with.
- **`prompts/selection.md`**: what counts as a good story and what to discard.
- **`prompts/voice.md`**: the reading style.
- **`TTS_VOICE`**: the Gemini voice (the list is in the Google Cloud documentation).
- **`MODEL_SELECTION`, `MODEL_SCRIPT`, `TTS_MODEL`**: the models.

In the code, the few places worth knowing:

- `main.py`, `LANGUAGES`: the episode languages. To add one, add an entry with its name, voice language code, chapter labels, date format, weekdays and months.
- `mail.py`, `SKIP_SENDER`: senders to ignore (by default The Economist, whose articles are all behind a paywall).

If you use [Claude Code](https://claude.com/claude-code), you can ask it to make these changes for you.

## Known limits

- The model may invent details that are not in the source. The prompt forbids it, and the sources in the show notes are there for you to check.
- Paywalled articles cannot be read: for those newsletters only the email text counts.
- Pages that need JavaScript cannot be read. This is not a problem for Substack, whose full text is already in the email.

## License

MIT, see [LICENSE](LICENSE).
