Write the script of a radio show read by a single voice, for a single listener. Write it in {language}. The source material may be in other languages: translate as you write.

## The listener

The listener is curious and well read, and speaks several languages. They listen in the kitchen or on the move, often with their hands busy. They will not read the original articles: this show replaces them. Write for their style and culture: they like clarity and dry irony, and cannot stand hype. When a comparison helps, take it from everyday life.

## Style

Explain soberly, but with rhythm. The model is The Economist: explain well, open with something that makes the listener curious, never raise your voice.

1. Rhythm comes from structure: short sentences alternating with medium ones, a concrete fact before the concept, a clean break from one story to the next.
2. No superlatives or hype adjectives: "incredible", "fascinating", "extraordinary", "revolutionary" and their equivalents in {language} are banned.
3. No exclamation marks. At most one rhetorical question per story.
4. Write for the ear. Sentences under 25 words. No brackets, lists or notes. Explain acronyms the first time. Round numbers and say them in words when it helps ("almost a third", "about two billion").
5. No descriptions of scenes, places, gestures or people's looks, even when the article opens that way. Long articles often open with a scene: skip it and get to the point. A concrete detail is fine only if it helps understand the fact.
6. No worn-out radio formulas such as "Now let's turn to", "Stay with us", "But that's not all", or their equivalents in {language}.

## Structure

1. **Opening.** A short greeting and the day of the week. Then the summary: one hook sentence per story, under 20 words each. The summary should make the listener want to listen, without promising more than the story delivers.
2. **Stories.** 5, about 600 words each, about 3,000 words in total. Each story follows this sequence:
   a. An opening that states the fact or the thesis right away: what happened and why it matters, in one or two sentences. No scenes.
   b. The context needed to understand it.
   c. Why it matters, more calmly.
   d. A detail that sticks.
   e. Closing and transition to the next story.
   Name the source once, naturally ("reports the Financial Times", "according to the ... newsletter").
3. **Order.** The strongest story first. Alternate heavy and light stories. End with a light one.
4. **Closing.** One or two sentences. No sugary goodbyes.

## Faithfulness, absolute rule

1. Use only facts present in the texts provided. If a detail is unclear, drop it instead of guessing.
2. Opinions and interpretations must be attributed to whoever expresses them in the source. Do not add opinions of your own.
3. Never mention paywalls, unavailable articles or discarded stories.
4. Translate quotations into {language} and keep them short.

## Tone example

Avoid: "Incredible news from the tech world! A startup has revolutionised the battery industry with a truly extraordinary discovery."

Do: "A startup of thirty people near Toulouse builds batteries without lithium. Last week it signed its first contract with a bus maker. The point is not the chemistry. It is the price."

## Response format

Reply ONLY with valid JSON, no preamble and no code fences. Keys stay in English; every value except URLs is in {language}:

{"summary": "text of the opening and summary",
 "stories": [
   {"chapter_title": "short chapter title, at most 6 words",
    "text": "text to read",
    "source": "name of the source",
    "url": "link of the article or null"}
 ],
 "closing": "text of the closing"}

## Material for this episode

Date: {date}

{candidates}
