# User Guide

This page explains how WeatherView behaves as you use it — not just what each button
is called, but what happens when you click it, what happens automatically, and what
to expect if something goes wrong. If you just want a quick reference to the on-screen
controls, see the [Usage table in the README](../README.md#usage) instead.

## The first time you open the app

The very first time you open WeatherView (or any time you haven't picked a station
yet), it tries to find the weather station closest to you:

- Your browser will ask for permission to share your location. If you allow it, the
  nearest station is selected automatically.
- If you deny the request, it isn't supported, or it times out, the app quietly falls
  back to the first station in the list — no error message is shown, it just picks a
  default and carries on.
- This location check only happens over a secure connection (HTTPS, or `localhost`
  during local development). Over a plain, non-secure connection your browser won't
  offer the location prompt at all, and the app falls back immediately.

Once you've picked a station yourself, that choice is remembered (see "Settings and
what the app remembers" below), so this automatic search normally only happens once — unless you
turn on the "Use my location" setting, which makes it search for the nearest station
again every time you open (or reload) the app. Note that this only happens when the
page loads: while the app is open and refreshing itself automatically or when you
click "Päivitä nyt", it keeps showing the station already selected rather than
re-checking your location.

The first time you visit, you'll also see a small cookie/notice banner at the bottom
of the page. It only needs to be dismissed once.

## Picking a station

- **Dropdown list**: your 10 most recently viewed stations are grouped at the top,
  followed by the full list of 400+ stations.
- **Search**: the search button opens a small window where you can type part of a
  station's name. Matches are filtered as you type and the matching letters are
  highlighted. Selecting a result works exactly like picking it from the dropdown.
- Whatever you pick is remembered for next time, and moves to the top of your recent
  list.
- Picking a station does not change the page address or add anything to your
  browser's back/forward history — the browser's back button won't step through your
  station choices.

## Weather camera pictures

If the selected station has a nearby weather camera, its latest pictures are shown
below the observation card.

- **Click or tap a picture** to open it larger in a viewer ("lightbox").
- From there, use the **arrow buttons**, the **left/right arrow keys** on your
  keyboard, or **swipe** on a touchscreen to move between pictures.
- The **⛶ button** expands the picture to fill your entire screen. Press **Esc**,
  click the ✕ button, or click outside the picture to return to the normal view —
  any of these also un-does the full-screen expansion if it was active.
- If a station has no camera nearby, or the camera pictures can't be loaded, the
  camera section is simply left out — the rest of the page (temperature, wind, etc.)
  keeps working normally.

## Automatic and manual refresh

- The app updates itself automatically. A countdown ("Seuraava päivitys: N s") shows
  how many seconds remain until the next update, based on how often the selected
  station itself reports new data — there's no fixed refresh rate for every station.
- You can trigger an update at any time with the **"Päivitä nyt"** (Update now)
  button. This doesn't force a fresh lookup from the weather data provider — it just
  fetches the current data straight away rather than waiting for the countdown. If
  the station hasn't actually reported anything new since the last update, you'll
  see the same figures again; only the automatic update at the end of the countdown
  is guaranteed to check for genuinely new data.
- If you switch to another browser tab or minimize the window, the countdown pauses.
  When you come back, if the update was already due, it fetches fresh data right
  away; otherwise the countdown simply resumes where it left off. Nothing is fetched
  in the background while you're not looking at the tab.
- If an update fails (for example, the weather data provider is temporarily
  unreachable, or your device has no internet connection), a short error message
  appears and the countdown stops — use "Päivitä nyt" to try again once the problem
  clears up.

## Settings and what the app remembers

The gear/settings button opens a small panel where you can turn the camera pictures,
"Use my location", and the history chart on or off, and choose how many hours of
history to display. Changes here only take effect once you click **Save** — closing
the panel without saving discards them.

Between visits, the app remembers:

- Your selected station and your 10 most recently viewed stations.
- Your chosen language.
- Your settings (camera on/off, "Use my location" on/off, history chart on/off, and
  how many hours of history to show).

This is all tied to your browser — it isn't shared across different browsers or
devices, and clearing your browser's cookies/site data resets it.

## Switching language

Choosing a different language from the language dropdown updates all the text on the
page immediately — no page reload needed — and is remembered for your next visit.
Station names and weather descriptions (wind direction, present weather, camera
direction labels, etc.) are also shown in the selected language.

## History chart

If enabled in settings, a chart below the weather card shows how temperature (and,
for stations that report it, precipitation) has changed over the recent history
window you've configured. Hovering over the chart shows the exact values at that
point in time. The chart isn't scrollable or zoomable — it always shows the full
configured window at once, and redraws whenever new data arrives or you change the
history length in settings.

If there's no history data available for a station, or the history chart is turned
off in settings, this section is simply left out.

## Privacy

- **"Use my location"**: when you allow it, your exact coordinates are sent to the
  server only to work out which station is nearest to you. They're used for that one
  calculation and then discarded — they are not saved, logged, or kept anywhere, and
  they're sent in a way that specifically avoids them ending up in the server's
  access logs.
- **Your IP address**: like any web server, WeatherView sees the IP address your
  browser connects from. It's used solely to apply a rate limit (to stop any one
  visitor from overloading the service) and is kept only as a short-lived request
  counter that automatically expires after about a minute — it is not stored in a
  database or written to a persistent log by the application.
- Nothing described above is linked to your name, account, or any other identifying
  information — WeatherView doesn't have user accounts at all.

## When something isn't available

WeatherView is built to degrade gracefully rather than break: if one part of the
data is missing (say, wind direction, or humidity, or the forecast, or a whole
camera), the app just leaves that part out of the display instead of showing an
error or empty placeholder. A visible error message only appears when the app can't
load weather data for the selected station at all — everything else fails silently
and quietly omits itself.
