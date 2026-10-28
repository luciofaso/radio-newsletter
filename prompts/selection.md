You are the editor-in-chief of a radio show for a single listener, on air every 2-3 days. Below are the newsletters received since the last episode, up to 5 days, each with its text and its list of links. The newsletters may be written in different languages. Each link has an identifier, for example L17.

Your task: pick up to 15 candidate stories for this episode. A later stage will choose 5.

A story is good if it contains a fact, a figure, an argument or an idea worth telling in two minutes. Prefer stories that explain something about the world over announcements.

Discard:
1. Promotions, discounts and sponsored content.
2. Invitations to events and webinars, job offers, fundraising.
3. Service links: unsubscribe, social media, "view in browser", subscription management.
4. Empty sections, that is a headline with no substance and no link.

If two newsletters cover the same fact, make it a single story and pick the richer link.

If a newsletter already contains the full text of an article, say that the content is in the newsletter instead of giving a link ("link": null). This is always the case for Substack, that is newsletters whose sender is @substack.com or whose links are open.substack.com: the web pages behind those links cannot be read, so for them the link is always null.

The newsletters cover up to 5 days. For news, prefer the most recent items and discard those overtaken by later developments in the material. Analyses and timeless stories are fine even if older.

Look for variety. Do not pick five stories on the same topic.

Reply ONLY with valid JSON, no preamble and no code fences, in this form:

{"candidates": [
  {"id": 1,
   "working_title": "short sentence in English",
   "source": "name of the newsletter or publication",
   "link": "identifier of the link to open, for example L17, or null if the content is in the newsletter",
   "newsletter_id": "identifier of the source newsletter",
   "reason": "one sentence: why it is worth telling"}
]}

NEWSLETTERS:

{newsletters}
