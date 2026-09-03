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
what the app remembers" below), so this automatic search only happens once. Note that
this only happens when the page loads: while the app is open and refreshing itself
automatically or when you click "Päivitä nyt", it keeps showing the station already
selected rather than re-checking your location.

If you want to re-check your location at any other time, click the **⌖ locate
button** next to the station dropdown. It repeats the same nearest-station search on
demand and immediately refreshes the weather data for whatever station it finds.

The first time you visit, you'll also see a small cookie/notice banner at the bottom
of the page. It only needs to be dismissed once.

## Picking a station

- **Dropdown list**: your 10 most recently viewed stations are grouped at the top,
  followed by the full list of 400+ stations.
- **Locate**: the ⌖ button asks your browser for your current location and selects
  the station closest to it, the same way the app does automatically on first visit —
  except you can trigger it again at any time. If location access is denied,
  unsupported, or times out, it falls back to the first station in the list, the same
  as the automatic search does.
- **Search**: the search button opens a small window where you can type part of a
  station's name. Matches are filtered as you type and the matching letters are
  highlighted. Selecting a result works exactly like picking it from the dropdown.
- **Distance to the station**: once your browser has given a location at least once
  (automatically on first visit, or via the locate button), a line under the dropdown
  shows how far and in which direction the selected station is from that location,
  e.g. "Etäisyys sijaintiisi: 442 m koilliseen". If your device also reports how
  accurate the fix was, that's shown too, e.g. "(tarkkuus ±1.5 km)" — desktop/laptop
  location is often IP- or Wi-Fi-based and can be off by a kilometre or more, while a
  phone with GPS is usually much more precise, so treat a large accuracy figure as a
  sign the distance itself may be off. This line is left out entirely if location
  access has never succeeded in this browser.
- Whatever you pick is remembered for next time, and moves to the top of your recent
  list.
- Picking a station does not change the page address or add anything to your
  browser's back/forward history — the browser's back button won't step through your
  station choices.

## Weather camera pictures

If the selected station has a nearby weather camera, its latest pictures are shown
below the observation card, along with how far the camera is from the station and in
which direction, e.g. "Kameran etäisyys asemasta: 1.8 km luoteeseen".

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

The gear/settings button opens a small panel where you can turn the camera pictures
and the history chart on or off, and choose how many hours of history to display.
Changes here only take effect once you click **Save** — closing the panel without
saving discards them.

Between visits, the app remembers:

- Your selected station and your 10 most recently viewed stations.
- Your chosen language.
- Your settings (camera on/off, history chart on/off, and how many hours of history
  to show).
- The last location your browser reported (used for the "distance to station" line
  under the station dropdown), if you've ever allowed location access.

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

For stations that report precipitation, two rain totals (in mm) appear below the
chart: the total rainfall over the last 24 hours, and the total over your configured
history window. If your history length is set to 24 hours, only one number is shown
since the two would be identical.

If there's no history data available for a station, or the history chart is turned
off in settings, this section is simply left out.

## Privacy

- **Location access**: whenever the app looks up your nearest station — automatically
  on first visit, or on demand via the ⌖ locate button — your exact coordinates are
  sent to the server only to work out which
  station is nearest to you. They're used for that one calculation and then discarded
  — they are not saved, logged, or kept anywhere on the server, and they're sent in a
  way that specifically avoids them ending up in the server's access logs. Your
  browser does keep the last coordinates it obtained (and how accurate they were) in
  its own local storage on your device, purely so the "distance to station" line
  (see "Picking a station" above) can keep working without asking for your location
  again on every visit — this never leaves your browser and is cleared the same way
  as your other saved settings (see "Settings and what the app remembers" above).
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
