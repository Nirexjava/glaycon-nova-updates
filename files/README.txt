NOVA COLLECTOR v4.33  -  Crystal Saga Nova daily auto-collector

INSTALL (first time)  : install.bat, then start.bat      (Python 3.13)
UPDATING from v3      : extract to a NEW folder, run install.bat, copy your old
                        settings.json / history.json if you want to keep them.

FIRST SETUP
1. Open the ACCOUNTS tab, type your e-mail and password, press SAVE ACCOUNT.
   They are kept only on this PC in account.json (plain text, not encrypted).
   Never share that file or zip this folder with it inside.
   (The password is NOT included in this download.)
2. Press RUN NOW on the CONTROLLER tab. Watch the first run.

WHAT IT DOES (in this order, each one only if not yet collected today)
 - Login page -> types e-mail/password, presses Login
 - Enter-game screen -> clicks the small up arrow (removes the advert bar), then Enter Game
 - DRAGON PACK advert -> clicks outside it
 - Privileges: Lifetime Pass claim, Monthly Pass claim, Daily Deals claim
 - Shop: Daily Limit -> free Gold Pack -> Purchase (only if the dialog is the Gold Pack)
 - Perks: Login Rewards -> Check-in, Online Bonus -> both Claim buttons
 - Reward animations are closed by clicking outside; grey "CLAIMED" buttons are recognised
   (it only clicks buttons that are green/yellow).
 - Ends on the main page.

SCHEDULES TAB: switch on a row, pick the days and time (PC clock). "+ ADD" for more rows;
choose "All daily collections" or one collection per row. Keep the app open.
The game day resets at server midnight (about 08:00 UK).

CONTROLLER: double-click a collection to run just that one (even if done today).
If an icon is ever missed, SETUP / CALIBRATION panel (beside the game) lets you capture it.
Failures save a screenshot into the debug folder - send it with nova_v2.log.

NOT live-tested against the real game (built and checked against your screenshots).
Colour of the Check-in button after claiming and the Online Bonus pop-ups are the most
likely things to need a tweak: send the log and debug screenshot if something is wrong.

v4.1: closes the game's server "Notice" window (red X, top right) that can appear after login.

v4.2: icons on the game map are now recognised more leniently; if they are still not seen it uses your calibrated icon positions (or built-in defaults) and carries on.

v4.3: Shop - Gold Pack fixed (Shop already opens on Daily Limit; Purchase dialog recognition updated). Online Bonus bottom-left no longer counts as a failure if the button stays visible.

v4.4:
- Several accounts: ACCOUNTS tab has a list (+ NEW ACCOUNT, SAVE, REMOVE). Each SCHEDULES row picks its account;
  the CONTROLLER has an ACCOUNT box for RUN NOW. If another account is logged in, the bot logs it out
  (clears the login cookies), reloads, and logs in with the chosen account. Done-today progress is kept per account.
  Your old single account is moved over automatically.
- Schedule hour/minute boxes are now typeable (two digits each).
- Faster: shorter waits between steps; each step moves on as soon as the screen shows it worked
  (button gone, menu open) instead of fixed pauses. It still only moves on after the claim is confirmed.

v4.5: icon clicks (Privileges/Shop/Perks) now use your calibrated position and never a loose picture match, so nothing is clicked on the map by mistake.

ICON: double-click create_shortcut.bat once - it puts a "Glaycon Nova" robot icon on your Desktop that starts the app (pin it to the taskbar from there).

EXE: double-click build_exe.bat once. It creates Glaycon Nova.exe (robot icon) in this folder; it starts the app with no black window. Keep it in this folder. If antivirus complains about a new small exe, allow it (it only starts nova_bot.py).

v4.6 BACKGROUND: the game keeps drawing when other windows cover it (Chromium occlusion switched off), so scheduled runs work while you play other games or browse. If the window is MINIMISED when a run starts, it is restored invisibly (almost transparent, click-through, no focus steal) and minimised again afterwards (SCHEDULES tab checkbox). Clicks are sent inside the game, so your own mouse is never moved. The PC must be awake and not locked.

v4.7: before using any game icon the bot checks the advert bar is folded away (small up arrow) and clicks the arrow if it is still there (waits for it to settle, max 4 tries a run).

v4.8: PAUSE / RESUME button (CONTROLLER). Pausing stops all clicking; RESUME re-checks the screen and continues the step it was on.
REFRESH button: reloads the game and asks where to continue - "Resume from <current collection>", "Start from beginning" or Cancel.
"RUN NOW STARTS FROM" box: pick a collection to start at (it runs that one and everything after), or leave "Next unfinished collection".

v4.9: background mode now takes its screenshots through the browser itself (DevTools) instead of grabbing the Qt window, which went stale when minimised. Also used automatically if a normal screenshot comes back blank. Log shows "Background mode: ..." when it kicks in, and "DevTools screenshot failed" if it cannot.

v4.10: the first screen opening of a run waits up to 25 s (later ones 10 s) and also recognises the left-menu entries as proof the screen opened, so a slow first load no longer fails the first collection.

v4.11 - Faster: the bot now reacts as soon as a screen/icon/button is detected (check every ~0.1 s, short settle waits, 0.3 s minimum between clicks). Safety checks (claimed/grey button, pop-up closed, Gold Pack dialog) are unchanged.

v4.12 - Much faster picture recognition: the screen is searched at reduced size and the match confirmed at full size (about 5x quicker per check, same accuracy), and each step only looks for the pictures it needs. Going back to the main page no longer waits once the back arrow is gone.
        New RESET PROGRESS button (left panel): clears today's "done" marks so the list shows 0/6 and you can run everything again (choose this account or all accounts).

v4.13 - Fixed: after Daily Deals the bot could think the Shop was already open (the Deals tiles look like Shop items), skip the Shop icon and click "Gold Pack" on the game map. It now always goes back to the main page and presses the Shop icon, waits until the old screen has really gone, and only presses Gold Pack while a menu screen is open. "Nothing to claim" is decided after 3 s instead of 5 s.
        The app, shortcut and exe are now called "Glaycon Nova" (no hyphen). create_shortcut.bat removes the old "Glaycon-Nova" desktop shortcut; build_exe.bat removes the old exe.

v4.14 - No more manual icon calibration needed: when an icon has no calibrated position, the bot finds it from the whole top-right icon row (Perks / Privileges / Shop sit in one line, equally spaced - it needs two of them to line up like that, so it cannot land on the game map) and saves the position automatically once the screen has opened. Your existing calibration.json is still used first.

v4.15 - Schedules now work from YOUR chosen time on your PC's clock, not the game server's reset time:
        * At the scheduled day/time the bot first clears that account's "done" marks (the daily attempts) - once per day - and then collects everything again. If the PC was off at that time, it does this as soon as the app is open and the game has loaded.
        * Each schedule row has SAVE and CANCEL buttons (they appear when you change the account, collection, days or time). Nothing is changed until you press SAVE. The on/off switch applies immediately.
        * Switching a schedule on, or saving a new time, after that time has already passed today does not start a run straight away; it waits for the next scheduled day.
        * Retries (up to 3, 10 minutes apart) only redo the collections that are still missing - they never clear the marks again.
        * While any schedule is switched on, the marks are only cleared by the schedule (or the RESET PROGRESS button), not by the date. With no schedule on, they clear at midnight PC time.
        * The footer now shows PC time and the next scheduled reset + run.

v4.16 - Fixed: the bot could click the minimap (top right) and open the big Starglade map instead of the Shop icon. When the icon row could not be recognised for a moment, an old fallback accepted a loose single picture match. That fallback is gone: icons are now found only from the calibrated position, the icon row (two icons lined up and equally spaced), or the default top-right icon position - and never anywhere else.

v4.17 - Pop-ups: after pressing Claim the bot taps outside the reward pop-up at most once every 1.2 s, up to 8 times (taps made while the pop-up's animation is playing are ignored, and the earlier faster taps could be used up too soon - this caused "Daily Deals: a pop-up would not close"). If the screen only looks dim but the Claim button is gone, the claim counts as done. A failed step now saves its own screenshot (debug folder, step_failed_*.png) and the log says why the pop-up looked open.

v4.18 - NEW collection: R2 Pass - Login Reward (7th collection, runs last): opens the R2 Pass icon (found from the icon row, three places left of Perks; also saved automatically / can be calibrated on Setup), presses the "Login Reward" tab at the bottom, presses the green Claim, closes the reward pop-up. The grey "R2 Pass Bonus" Claim (needs R2 Pass activated) is ignored.
        Fixed: the free Gold Pack could be skipped ("no purchase dialog appeared"). The tile is now pressed only after it has stopped moving, pressed again (up to 3 times) if the purchase dialog does not appear, and the step FAILS (and retries later) instead of silently counting as done.
        If you saved a schedule for "All daily collections" it now includes R2 Pass automatically. Existing "done" marks stay; the new collection shows as waiting until it has run once.

v4.19 - Gold Pack fix: the bot now waits (up to 3 s) for the Gold Pack title to fade in before pressing Purchase
instead of stopping early; the "tap outside" points no longer touch the Shop's left menu (Daily Limit / VIP Shop).

v4.20 - Shop: the left menu is pressed only once it has stopped sliding; the bot re-checks that the Daily Limit list is
showing (the Shop remembers its last tab) and presses Daily Limit again if not. Fewer "tap outside" clicks: once a reward
button is gone and the screen only looks dim, it stops tapping so nothing can land on the game map.

v4.21 - Shop fix (found from your video): the highlighted "VIP Shop" row in the left menu looked like the Gold Pack
tile's beige "Free" bar, so the bot thought the Daily Limit list was already open and clicked VIP Shop. The tile search
now ignores the left menu and checks the size, so only the real Gold Pack tile counts.

v4.22
 - Dragon Pack advert on the main screen: closed with ONE tap on the chat panel (bottom-left, harmless), then it waits for the
   advert to fade before ever tapping again - no more taps on the floor / walking.
 - Fixed Monthly Pass, Online Bonus (and AFK) being skipped: v4.20 moved on while the reward pop-up was still fading, so the
   next menu click was swallowed. The bot now waits until the pop-up has really closed again.
 - New collection: Perks - AFK Bonus (claims every green Claim button on the Offline Reward list; grey ones are left alone).
   NOTE: some of those claims use up an "Offline EXP" item (the number on the icon) - remove AFK Bonus from a schedule if you
   do not want that.
 - New LOG button (left panel): view everything the bot did, REFRESH, EXPORT to a .txt file to send for checking, CLEAR LOG.

v4.23 - Shop: when the Gold Pack is already bought the bot now presses Daily Limit once to check (was 3 times) and moves on ~5 s sooner.

v4.24 - New collection: Pet Theme - Daily Login (last in the list, then back to the main page).
 - The Pet Theme icon is only on the main screen some weeks. The bot looks for it (picture match, only on the main page);
   if it is not showing, the whole collection is skipped ("event icon is not showing this week") and counts as done.
 - If the icon is there it opens the event, presses the green Daily Login Claim, closes any pop-up and goes back.
 - Small pictures (like this icon label) are now matched with finer size steps, so they are found reliably.

v4.25 - SCREENSHOT MANAGER (new "SCREENSHOTS" tab, plus CAPTURE and SCREENSHOTS buttons in the left panel, and F9)
 - Automatic: while you explore the game, a screenshot of the WHOLE game view is saved when the screen has changed a lot and
   then settled (animations / transitions are skipped). While the bot runs it reuses the frames it already looks at.
 - Saved in  <Glaycon Nova folder>\screenshots\<system>\<date-time>_<name>.png . Folders: the collection being run
   (e.g. "Perks - AFK Bonus"), or while you explore: Main screen / Privileges / Shop / Perks / R2 Pass / Other screens / Adverts.
   Type a name in "System / feature name" to file everything under that name instead (e.g. "Pet Theme - Quest tab").
 - Near-identical screens are not saved twice (picture fingerprint). Manual captures (button / F9) are always saved.
 - Library: browse by folder, preview, OPEN, RENAME, MOVE TO FOLDER, DELETE, EXPORT AS ZIP, OPEN SCREENSHOT FOLDER.
 - Light on the PC: the explore watcher looks at a tiny 96x54 copy once per second (only while the game tab is on screen and
   the window is active); saving happens in a background thread. Auto-capture pauses above a size limit (default 5 GB).
 - Files: shots.py (logic) and shots_ui.py (tab). Nothing in the collection logic was changed.

install.bat now does everything in one go: creates the environment, installs the packages AND builds "Glaycon Nova.exe".
(build_exe.bat is still there if you only want to rebuild the .exe later.) If the .exe step fails, the app is still installed and start.bat works.

v4.26 - NEW COLLECTION: "Pet Theme - Battle Pass".
After the Pet Theme Daily Login claim it opens the Battle Pass tab and presses the green "Claim All" button, nothing else.
It never presses the $ buttons (Activate / Unlock). If the Pet Theme icon is not on the main page this week, both Pet Theme collections are skipped.
There are now 10 daily collections. The screenshot library is included in this version (screenshots folder: Unsorted + Pet Theme).

v4.27 (and v4.28 screenshot fix)
- MONEY GUARD: every click is checked first; if it would land on a known paid button ($9.99 Activate, Unlock $29.99) it is refused and logged
  ("BLOCKED click ... paid button"). More paid buttons can be added to the list as they are discovered.
- RED DOT REPORT: at the end of a run the bot looks at the main page and logs how many red dots are still showing (report only, it never clicks them).
  Send me a screenshot of the main page with the dots and we can add collections for them one by one.
- RUN ALL ACCOUNTS button: collects for every account one after another (accounts already done today are skipped). STOP cancels the rest.
- Screenshots (tested on your real library): the login page is an animated scene, so it kept looking "new". Screens are now compared with a
  tolerance for animation (and the advert strip at the top is ignored), and the login page is limited to one automatic screenshot every 3 minutes.
  New SCREENSHOTS button "REMOVE DUPLICATES" deletes repeats of a screen already saved in the same folder (first one kept, manual captures never touched).

v4.29
- FIX: "Pet Theme - Battle Pass" failed with "Battle Pass tab was not found" when Claim All was already claimed (greyed out). It now recognises the
  opened tab by its selected look, so a rerun with nothing left to claim finishes cleanly.
- NEW COLLECTION "Daily - Quests and Activity": opens the Daily system from the bottom-right icon on the main page, presses the green Claim
  buttons on the Daily Quests tab (Daily Login and any finished quest; never "Go to"), then the Activity Claim at the bottom right.
- NEW COLLECTION "Limited-Time Event": opens the Limited-Time Event icon (second row of the main page; skipped when it is not there) and presses green
  Claim buttons only. The page's other tabs are not explored yet - send screenshots of them and we will extend it.
- There are now 12 daily collections.

v4.33 - THEMES (12) + STATIC / ANIMATED HEADER
  * Palette button (top right of the header, next to the status and account chips): pick Seraph, Lunar Seraph,
    Void Archangel, Titan Protocol, Eclipse, Orbital, Redline, Elysium, Nebula, Fieldcraft, Monolith or Classic.
    Each row shows a colour preview; the active one is marked. Changes apply instantly - the game, the run and the
    schedules are never touched. Your choice is remembered. "Restore default" returns to Seraph + animated header.
  * Header: STATIC (finished emblem + GLAYCON NOVA) or ANIMATED (wings flex segment by segment, halo pulses/spins,
    letters descend / appear one by one / emerge from a glow, then only gentle motion). "Animation on" switches the
    motion off without changing the mode; "Replay header animation" plays the entrance again. If Windows has
    "Show animations" switched off, the header stays static. Animation only ever draws inside the header strip.
  * The same controls are on the SCHEDULES tab (THEME / HEADER / Animation on / REPLAY HEADER / RESTORE DEFAULT).
  * Every theme has its own icon set (tabs and buttons) in its colours. Layout and sizes are identical in all themes,
    so the game view never moves. Completed (tick), running (play), waiting (?) and failed (cross) rows keep distinct
    shapes AND colours in every theme; red is always failure/stop.
  * Files: theme.py (system), theme_defs.py (colours - edit to tweak a theme), theme_icons\<theme>\ (icons).

v4.32 - NEW LOOK: SERAPH
  * Gold armour plating with cyan accents, a small winged/halo header above the tabs, and gold line icons on every
    tab and button (RUN NOW, STOP, PAUSE, REFRESH, RUN ALL ACCOUNTS, RE-RUN FAILED, RESET PROGRESS, RELOAD GAME, LOG,
    CAPTURE, SCREENSHOTS, REC, SETUP / CALIBRATION). The header also shows RUNNING / IDLE and the account name.
  * Switch any time: Schedules tab -> LOOK -> Seraph or Classic (the original dark/orange look). Nothing else changed:
    every setting, tab, collection and feature works exactly as before.
  * The look lives in theme.py + the theme_icons folder; if either is missing the bot simply runs in Classic.

v4.31 - NEW
  * REC (click recorder): press REC, then click around in the game as you normally would. For every click it saves
    a screenshot of the game, a copy with the click marked in red, and a list of the click positions, in
    Recordings\rec_<date>_<time>\ (clicks.txt + clicks.json). Send that folder to build new collections fast.
  * Input lock: while a run is going, stray clicks/keys on the game view are ignored (the bot's own clicks work).
    It lifts while paused. Untick "Lock the game view while the bot runs" to take control.
  * Results grid: the collection list now shows a green tick (collected), red cross (failed - hover for the reason,
    remembered until the next run) or ? (not done yet).
  * RE-RUN FAILED: runs again only the collections that failed last time (shows how many).

v4.30
- "Perks - Check-in" now also claims the check-in milestone gift chests under the calendar (2 / 3 / 5 / 7 / 15 / 25 Days). Only a chest that shows a red dot is pressed
  (up to three per run), then the reward pop-up is closed. Nothing else in that area is touched.

v4.34 - ANIMATED SCENES (header)
  New "ANIMATED SCENES" dropdown on the SCHEDULES tab (Off + 8 scenes), a SPEED dropdown (0.5x-2x) and PREVIEW / REPLAY.
  Scenes: Robot Sparring, Assembly Line, Gear Works, Energy Clash, Angelic Core, Night Skyline, Data Stream, Seraph Wingspan.
  - Drawn in the free gap of the header, between the title and the status chips; clipped to that box, scaled to fit.
  - Independent of the theme and of the header Static/Animated setting; any scene works with any theme (it takes
    the theme's colours). Changing theme never changes the scene and vice versa; RESTORE DEFAULT leaves the scene alone.
  - Remembered in settings ('scene'). Default: Off. No image files needed: everything is vector-drawn (header_scenes.py).
  - Light on the CPU: ~25 fps (15 fps while a run is active), stops when minimised / background mode / hidden.
    If Windows "Show animations" is off, the scene shows one still frame instead of moving.
  - If the header is too narrow for the box (under ~220 px) the scene is simply not drawn.

v4.35
  - Animated scenes: now ON by default (Robot Sparring) the first time; drawn in a box centred in the header gap
    (about 40% of the header width, like the area you marked). ANIMATED SCENES dropdown sits directly left of THEME
    on the SCHEDULES tab, and is also in the palette menu (top right) under ANIMATED SCENES.
  - Floating GAME LOCK control (lock_overlay.py): lock icon + SAVE button, one draggable group over the game area.
    Click = lock/unlock (blocks your mouse/keys on the game; the bot's own clicks keep working). Drag = move (never
    toggles). SAVE = remember the position (settings key 'lock_pos'). Stays inside the game area when the window is
    resized; colours follow the theme. The old "Lock while the bot runs" tick-box still works as before.
  - Wings redrawn with three feather rows and a continuous gentle flap, with an occasional wider stretch.

v4.36
  - Header: separate "LIVE" (animated scenes) and "THEME" drop-downs, each with a small caption above, placed after the
    account chip: Account -> Live -> Theme. Live = Off + the eight scenes, speed and "Replay scene". Theme = themes and the
    header animation settings. They are saved separately and never change each other.
  - Illustrated headers for 12 themes (Seraph, Lunar Seraph, Void Archangel, Titan Protocol, Eclipse, Orbital, Redline,
    Elysium, Nebula, Fieldcraft, Monolith and the new Celestial) taken from your reference sheet (folder theme_art/).
    Static = the finished artwork. Animated = the same artwork plus swaying/breathing wings, pulsing halo and a light that
    travels over the lettering. Classic keeps the old drawn header.
  - Lock control is now a theme-matched badge (theme_art/<theme>/badge.png) with "INPUT LOCKED" / "INPUT UNLOCKED",
    closed/open padlock, the SAVE button below; still draggable (drag never toggles), position saved with SAVE.

v4.37
- Header art is livelier: wings open and close in a slow cycle (folded, spread, brief flare, settle) with a beat while open; the halo bobs with a travelling highlight; the name drops in / emerges from a void, holds, fades away and returns, in a smooth loop.
- Five new character scenes in the Live menu: Mech Duel, Dragon, Phoenix, Starfleet, Angel vs Demon. All stay inside the header box and loop seamlessly.
- Unchanged: game window, layout, lock overlay, automation, remembered Live/Theme choices.

v4.38
- One lock control only: the checkbox "Lock the game view while the bot runs" is gone. The draggable lock badge on the game (with SAVE) does it all. Every run starts locked; click the badge to take over, click again to lock. Position and SAVE unchanged.

v4.39
- Every run now opens the game's Settings right after login and ticks Hide FX and Hide Models (less CPU), then closes the window. A box is only pressed if it is not ticked yet, so nothing is ever switched off. If Settings cannot be handled, the run carries on and says so in the results.
- New collection "Slayer - Dragon Spins" (runs before Pet Theme, so the "Complete Dragon Slayer once" quest is unlocked): opens Slayer from the main-page icon, makes sure Skip Animation is ticked, then presses Spin x1 for as long as the coin counter under the button is green, closing the reward pop-up each time. Spin x10 is never pressed. Only the Green Dragon page is handled.
- Collections now total 13 (RESET PROGRESS shows 0/13).

v4.40
- Fixed: after the Slayer spins the Pet Theme (and Limited-Time Event) icon was reported "not showing this week". The icon labels sit on top of the game map, and the old pictures only matched one background. Each icon now has a second picture (icon_pettheme_b / icon_limited_b) and the old Pet Theme threshold is a little looser.
- Pet Theme now also claims the other green Claim buttons on the Quest tab (left column below the first row, and right column), so "Complete Dragon Slayer once" is collected after the Slayer spins.

v4.41
- New collection "Valley of Light - Priest Event" (14 collections; runs just before Daily): presses M, scrolls the map's NPC list to Priest (Event), clicks it and waits for the character to walk there, then Enter Valley of Light > Enter Valley Light (Party 3+) > Enter (single player) > Open inside the dungeon; after the character dies it presses Revive (or Accept Revive when that button is available / not greyed). Repeats until the "Member ... reached entry limit!" notice shows, clicks Confirm and stops. Never presses Revive on Spot (added to the money guard), Leave or Abandon Dungeon.
- The existing Daily step then claims "Join the Valley of Light once" and the Activity Claim.

v4.42
- Fixed: the map's NPC list was not scrolling to Priest (Event). The old code sent one huge wheel jump or one very fast drag every 1.3 s and never checked the result. Now it works like a person: the pointer rests on the list, it scrolls in small mouse-wheel notches (or holds a name and drags it slowly, as in your video), and it WATCHES the list. If the list moved it measures how far and aims for about half a page per step, so no name is skipped. If it did not move it tries the other way (wheel down, drag up, wheel up, drag down); once one works it remembers it. At the end of the list it turns around. It clicks Priest (Event) only once the list has stopped moving.
- The bot now also checks that the map window is really open (green name buttons) before scrolling, and presses M again if it is not. If the click on Priest (Event) did not start the walk it looks again after 6 s.
- Clear failure messages: "the map list would not scroll" (nothing moved after 8 tries) or "Priest (Event) was not found".
- v4.42 update: the list scroll is much faster. It now grabs the name at the bottom of the list and pulls it to the top (about 40% of the view per drag, quick motion), does not wait for the next check between drags, and starts with the drag (the way that works in the game) before trying the wheel. The old step measurement was fooled by rows of identical "Guard" names and made tiny steps; unreliable measurements are now ignored.
- Fixed: after the entry-limit notice the bot clicked Confirm a second time on the (already closed) notice, which made the character walk. It now clicks Confirm once and waits 4 s before it would ever try again.

v4.42 (3rd update)
- Valley of Light map list: the game ignores the first wheel/drag after the map opens unless the pointer has been resting on the list - that is why the first try always missed. The bot now rests the pointer on the list first, grabs a name near the bottom and pulls it up slowly, like your manual video (about 1 s per drag), and one missed drag no longer counts as "end of the list" (it needs 3 misses in a row before turning around). This also stops the list bouncing back to the top.
- Fixed: the fallback icon positions for Privileges / Shop / Perks / R2 Pass were a few pixels too far left; Perks missed three times in a row ("the perks screen did not open"). They now match where the icons really are.
- Slayer icon: match threshold lowered from 0.78 to 0.72 (it was scoring 0.74-0.77 after the theme change and the step skipped itself).

v4.42 (4th update) - from the 22:52 / 22:55 logs
- Valley of Light: the bot sometimes clicked Priest (Event) 2-4 times (once at the wrong spot while the list was still sliding). Cause: it acted on a screenshot taken BEFORE the last drag finished. Every screenshot now carries its capture time; the bot only trusts a picture taken after the drag has ended and settled, and a second click on Priest (Event) needs 8 s and a fresh picture (so a stale picture can never make a click land on the game world).
- R2 Pass - Login Reward: "Login Reward tab was not found on screen" happened when the game had already opened on that tab (clicking it changes nothing and the selected tab looks different). The step now treats "tab looks selected" as success and has a fixed-position fallback, like the Battle Pass step.
- Enter Game: if it was pressed twice and nothing happened (e.g. the page had been sitting on the login screen for 10 minutes and the session expired), the game page is reloaded once and the login runs again, instead of failing.


v4.43 - AUTO UPDATE
 - New UPDATE button (left panel, under RELOAD GAME). Click it to look for a new version. If there is one a small box shows
   the version and what is new; "Install & restart" installs it and reopens the bot by itself.
 - The bot also checks every minute. When idle it shows the box and installs after 15 s unless you press Later (tick box
   "Install new updates by myself when the bot is idle" controls this). It never updates in the middle of a run.
 - Updates come from the folder  updates\  inside the bot folder (no internet). Each update backs up the files it replaces
   to  backups\  and is undone automatically if the new version does not start. account/settings/progress/history/log are never touched.
 - "Install from file..." (in the box shown when you are up to date) loads an update .zip from anywhere.

v4.44 - test update only (no changes except the version number), to check auto update works.

v4.45 - REMOTE UPDATE
 - The bot also checks the online update repo (GitHub: Nirexjava/glaycon-nova-updates) every 30 minutes and when you press UPDATE.
 - Online updates are only accepted if they carry the owner's digital signature; anything else is ignored. Same popup, backup and automatic rollback as before.

v4.46 - test update only (version number changed, nothing else).

v4.47
 - NEW collection "Perks - Level Rewards": presses the green Claim buttons of the level rows (Lvl 30, 40, ...). Grey rows are left alone.
 - NEW collection "Rank - Claim Pay": portrait (top left) > Rank > green "Claim Pay". Each screen is checked by picture; if one does not
   open, only this collection fails and the run goes on.
 - NEW stuck-run watchdog: if a step makes no progress (no new step, no click) for 10 minutes, the run is stopped with a screenshot in debug\,
   the game is reloaded and the remaining collections start again (at most twice a day).
 - NEW run report: after every run (also scheduled ones) a small box shows what was collected / failed and why; the full text is kept in
   reports\report_<date>.txt and the LAST REPORT button (left panel) shows it again.
 - Not done yet (needs screens from you): Mail, other red-dot collections, Power Up / Daily Quiz tabs, bag-full warning.
