"""The daily collections, in the order they run. Pure data - no Qt, no OpenCV.

Each task lists the steps that are done once the right game screen ("group") is open.
Step kinds (see nova_bot.py):
  slayer     Slayer screen: tick Skip Animation, press Spin x1 while Dragon coins remain
  perf       (not a task step) after login: Settings > Hide FX + Hide Models
  open       click a left-menu entry
  claim      click a green/yellow Claim style button if it is there, close the reward pop-up
  dotclaim   press an item that carries a red dot inside a region (e.g. milestone chests), close the pop-up
  shop_free  buy the free Gold Pack (retries until the purchase dialog shows) (with a safety check that it really is the free pack)
Regions are fractions (left, top, right, bottom) of the game view.
"""

TASKS = [
    dict(id='lifetime', title='Lifetime Pass', group='privileges', steps=[
        dict(k='open', find='lifetime_pass', label='Lifetime Pass menu'),
        dict(k='claim', find='claim_text', region=(.62, .28, 1.0, .80), claimed='claimed',
             label='Lifetime Pass Claim'),
    ]),
    dict(id='monthly', title='Monthly Pass', group='privileges', steps=[
        dict(k='open', find='menu_monthly', label='Monthly Pass menu'),
        dict(k='claim', find='claim_text', region=(.62, .28, 1.0, .80), label='Monthly Pass Claim'),
    ]),
    dict(id='deals', title='Daily Deals', group='privileges', steps=[
        dict(k='open', find='menu_deals', label='Daily Deals menu'),
        dict(k='claim', find='claim_text', region=(.38, .22, .90, .62), label='Daily Deals Claim'),
    ]),
    dict(id='shop', title='Shop - Gold Pack', group='shop', steps=[
        dict(k='open', find='menu_daily_limit', already='shop_goldpack', label='Daily Limit menu'),
        dict(k='shop_free', label='free Gold Pack'),
    ]),
    dict(id='checkin', title='Perks - Check-in', group='perks', steps=[
        dict(k='open', find='menu_login_rewards', label='Login Rewards menu'),
        dict(k='claim', find='checkin_btn', region=(.45, .75, .90, 1.0), label='Check-in'),
        # the 2 / 3 / 5 / 7 / 15 / 25 Days gift chests under the calendar: only a chest with a red dot is pressed
        dict(k='dotclaim', dot_region=(.12, .82, .72, .97), dot_offset=(-.0078, .0153), wait=0.9, label='Check-in milestone chest (1)'),
        dict(k='dotclaim', dot_region=(.12, .82, .72, .97), dot_offset=(-.0078, .0153), wait=0.7, label='Check-in milestone chest (2)'),
        dict(k='dotclaim', dot_region=(.12, .82, .72, .97), dot_offset=(-.0078, .0153), wait=0.7, label='Check-in milestone chest (3)'),
    ]),
    dict(id='online', title='Perks - Online Bonus', group='perks', steps=[
        dict(k='open', find='menu_online_bonus', label='Online Bonus menu'),
        dict(k='claim', find='claim_text', region=(.60, .15, 1.0, .50), label='Online Bonus Claim (top right)'),
        dict(k='claim', find='claim_diamond', region=(.08, .68, .55, 1.0), soft=True, label='Online Bonus Claim (bottom left)'),
    ]),
    dict(id='afk', title='Perks - AFK Bonus', group='perks', steps=[
        dict(k='open', find='menu_afk_bonus', label='AFK Bonus menu'),
        dict(k='claim', find='claim_text', region=(.70, 0.2, 1.0, 0.36), wait=1.4, soft=True, label='AFK Bonus Claim (row 1)'),
        dict(k='claim', find='claim_text', region=(.70, 0.36, 1.0, 0.52), wait=1.4, soft=True, label='AFK Bonus Claim (row 2)'),
        dict(k='claim', find='claim_text', region=(.70, 0.52, 1.0, 0.69), wait=1.4, soft=True, label='AFK Bonus Claim (row 3)'),
        dict(k='claim', find='claim_text', region=(.70, 0.69, 1.0, 0.86), wait=1.4, soft=True, label='AFK Bonus Claim (row 4)'),
    ]),
    # Perks > Level Rewards: the green Claim buttons of the Lvl 30 / 40 / ... rows (grey ones are not yet reachable).
    dict(id='levelrewards', title='Perks - Level Rewards', group='perks', steps=[
        dict(k='open', find='menu_level_rewards', fallback=(.0586, .636), label='Level Rewards menu'),
        dict(k='claim', find='claim_text', region=(.80, .12, 1.0, .98), soft=True, wait=1.4, label='Level Rewards Claim (1)'),
        dict(k='claim', find='claim_text', region=(.80, .12, 1.0, .98), soft=True, wait=1.0, label='Level Rewards Claim (2)'),
        dict(k='claim', find='claim_text', region=(.80, .12, 1.0, .98), soft=True, wait=1.0, label='Level Rewards Claim (3)'),
        dict(k='claim', find='claim_text', region=(.80, .12, 1.0, .98), soft=True, wait=1.0, label='Level Rewards Claim (4)'),
    ]),
    dict(id='r2login', title='R2 Pass - Login Reward', group='r2pass', steps=[
        dict(k='open', find='r2_login_tab', already='r2_claim_today', selected_ok=True, fallback=(.2031, .8813), label='Login Reward tab'),
        dict(k='claim', find='claim_text', region=(.62, .12, 1.0, .40), label='R2 Pass Login Reward Claim'),
    ]),
    # Slayer first: spending the Dragon coins unlocks the "Complete Dragon Slayer once" quest that Pet Theme / Daily then claim.
    dict(id='slayer', title='Slayer - Dragon Spins', group='slayer', steps=[
        dict(k='slayer', label='Slayer: Skip Animation on, Spin x1 for every Dragon coin'),
    ]),
    dict(id='pettheme', title='Pet Theme - Daily Login', group='pettheme', steps=[
        dict(k='claim', find='claim_text', region=(.28, .10, .62, .36), label='Pet Theme Daily Login Claim'),
        # Quest tab (the page opens on it): the other quests - e.g. "Complete Dragon Slayer once", unlocked by the Slayer spins. Green Claim only.
        dict(k='claim', find='claim_text', region=(.28, .36, .62, .80), soft=True, wait=1.0, label='Pet Theme Quest Claim (left column)'),
        dict(k='claim', find='claim_text', region=(.62, .10, 1.0, .80), soft=True, wait=1.0, label='Pet Theme Quest Claim (right column)'),
    ]),
    # Battle Pass tab > green "Claim All" only. Never touches the $ buttons (Activate / Unlock).
    dict(id='petbattle', title='Pet Theme - Battle Pass', group='pettheme', steps=[
        dict(k='open', find='pet_tab_battlepass', already='pet_tab_battlepass_on', selected_ok=True, fallback=(.216, .883), label='Battle Pass tab'),
        dict(k='claim', find='pet_claimall', region=(.45, .07, .75, .26), soft=True, wait=2.0, label='Battle Pass Claim All'),
    ]),
    # Limited-Time Event icon (second row of the main page; only there while an event runs). Only green "Claim" buttons are pressed,
    # never "Go to" or anything with a price. The page's other tabs are not explored yet.
    dict(id='limited', title='Limited-Time Event', group='limited', steps=[
        dict(k='claim', find='claim_text', region=(.18, .12, 1.0, .86), soft=True, wait=1.2, label='Limited-Time Event Claim (1)'),
        dict(k='claim', find='claim_text', region=(.18, .12, 1.0, .86), soft=True, wait=1.0, label='Limited-Time Event Claim (2)'),
        dict(k='claim', find='claim_text', region=(.18, .12, 1.0, .86), soft=True, wait=1.0, label='Limited-Time Event Claim (3)'),
    ]),
    # Daily system (bottom-right icon on the main page): Daily Quests tab - green Claim buttons only (never "Go to"),
    # then the Activity chest Claim at the bottom right.
    # Valley of Light through the map's Priest (Event) NPC, as many runs as the day allows; then Daily claims "Join the Valley of Light once".
    dict(id='valley', title='Valley of Light - Priest Event', group='main', steps=[
        dict(k='valley', label='Valley of Light: map (M) > Priest (Event) > runs until the daily limit'),
    ]),
    # Character (round portrait, top left) > Rank (left column) > green "Claim Pay". Fixed places, each checked by a picture of the
    # screen it opens; a screen that does not open is reported as a failure of this collection only.
    dict(id='rankpay', title='Rank - Claim Pay', group='main', steps=[
        dict(k='tapfrac', at_h=(.0554, .059), expect='char_title', wait=1.2, skip_if_open=True, label='Character screen (portrait)'),
        dict(k='tapfrac', at_h=(.134, .331), expect='rank_title', wait=1.2, label='Rank window'),
        dict(k='claim', find='rank_claimpay', region=(.20, .50, .75, .85), soft=True, wait=1.5, label='Rank Claim Pay'),
    ]),
    dict(id='daily', title='Daily - Quests and Activity', group='daily', steps=[
        dict(k='claim', find='claim_text', region=(.40, .10, 1.0, .78), soft=True, wait=1.5, label='Daily Quest Claim (1)'),
        dict(k='claim', find='claim_text', region=(.40, .10, 1.0, .78), soft=True, wait=1.0, label='Daily Quest Claim (2)'),
        dict(k='claim', find='claim_text', region=(.40, .10, 1.0, .78), soft=True, wait=1.0, label='Daily Quest Claim (3)'),
        dict(k='claim', find='claim_text', region=(.40, .10, 1.0, .78), soft=True, wait=1.0, label='Daily Quest Claim (4)'),
        dict(k='claim', find='claim_text', region=(.78, .82, 1.0, .99), soft=True, wait=1.2, label='Daily Activity Claim'),
    ]),
]

TASK_BY_ID = {t['id']: t for t in TASKS}

# Where the game's top-right icons sit (fractions of the game view), used only if the picture
# of the icon is not found and nothing was captured on the Setup panel.
DEFAULT_POS = {
    'privileges': (.8954, .041),
    'shop': (.9225, .041),
    'perks': (.8688, .041),
    'r2pass': (.790, .041),
    'ad_arrow': (.502, .030),
}

# Points (fractions of the game view) that are empty/harmless in every screen; used to
# "tap outside" a pop-up. Only ever clicked while a pop-up (dimmed screen) is detected.
DISMISS_POINTS = [(.40, .075), (.68, .83), (.55, .075)]

# Safe taps for the Dragon Pack advert on the MAIN screen: the chat panel (bottom left). A tap there never walks the character.
ADVERT_POINTS = [(.07, .90), (.10, .86)]
