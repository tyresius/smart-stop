#!/usr/bin/env python3
"""
Presentation Generator for Smart Stop Algorithm
================================================
Generates a PowerPoint slide deck with embedded GIF animations.

Deck v2 (July 17, 2026): restructured for a first-time audience per
Patrick's outline — history of traffic devices, the new world, Smart Stop,
then a scenario walk-through from simple crossings to rush hour to the
side-street case, with Smart Safe as the deployment bridge and safety told
as a found-and-closed story. Every number is from CLAIMS.md verbatim;
jargon is translated ("arterial" -> "a busy road crossing a quiet one").
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
NAVY       = RGBColor(0x1A, 0x23, 0x3A)   # Slide background
DARK_CARD  = RGBColor(0x22, 0x2D, 0x4A)   # Card / section background
ACCENT     = RGBColor(0xE6, 0x7E, 0x22)   # Orange  (matches Straight signal)
GREEN      = RGBColor(0x2E, 0xCC, 0x71)   # Green   (matches Left signal / GO)
PURPLE     = RGBColor(0x9B, 0x59, 0xB6)   # Purple  (matches Right signal)
RED        = RGBColor(0xE7, 0x4C, 0x3C)   # Red     (matches Stop sign)
BLUE       = RGBColor(0x3A, 0x9B, 0xD5)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xCC, 0xD0, 0xD8)
MID_GRAY   = RGBColor(0x7F, 0x8C, 0x8D)

# Slide dimensions (widescreen 16:9)
W = Inches(13.33)
H = Inches(7.5)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
PPTX_PATH  = os.path.join(OUTPUT_DIR, "SmartStop_Presentation.pptx")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def new_prs():
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H
    return prs


def blank_slide(prs):
    layout = prs.slide_layouts[6]   # completely blank
    return prs.slides.add_slide(layout)


def fill_bg(slide, color=NAVY):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, l, t, w, h, color, alpha=None):
    shape = slide.shapes.add_shape(
        1,   # MSO_SHAPE_TYPE.RECTANGLE
        l, t, w, h
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_text(slide, text, l, t, w, h,
             font_size=24, bold=False, color=WHITE,
             align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txBox = slide.shapes.add_textbox(l, t, w, h)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txBox


def add_bullet(slide, items, l, t, w, h,
               font_size=20, color=WHITE, bullet_color=None, spacing=1.15):
    """Add a text box with multiple bullet lines."""
    txBox = slide.shapes.add_textbox(l, t, w, h)
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.space_before = Pt(4)
        run = p.add_run()
        run.text = item
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
    return txBox


def section_header(slide, label, color=ACCENT):
    """Small colored tag at the top of content slides."""
    bar = add_rect(slide, Inches(0.5), Inches(0.3), Inches(0.07), Inches(0.55), color)
    add_text(slide, label.upper(),
             Inches(0.65), Inches(0.3), Inches(5), Inches(0.55),
             font_size=11, bold=True, color=color)


def metric_card(slide, value, label, l, t, w=Inches(2.8), h=Inches(1.6),
                value_color=GREEN, bg=DARK_CARD):
    add_rect(slide, l, t, w, h, bg)
    add_text(slide, value,
             l + Inches(0.15), t + Inches(0.15), w - Inches(0.3), Inches(0.9),
             font_size=42, bold=True, color=value_color, align=PP_ALIGN.CENTER)
    add_text(slide, label,
             l + Inches(0.15), t + Inches(1.0), w - Inches(0.3), Inches(0.5),
             font_size=14, color=LIGHT_GRAY, align=PP_ALIGN.CENTER)


def gif_slide(prs, title, gif_name, scenario_results, description, key_insight):
    """Slide with title, GIF, and metrics sidebar."""
    slide = blank_slide(prs)
    fill_bg(slide)

    # Title bar
    add_rect(slide, 0, 0, W, Inches(0.85), DARK_CARD)
    add_text(slide, title,
             Inches(0.4), Inches(0.12), Inches(10), Inches(0.65),
             font_size=26, bold=True, color=WHITE)

    # GIF (left 2/3 of slide). Width-only so python-pptx preserves the
    # reality demos' 2:1 (two-panel) aspect ratio instead of stretching it;
    # vertically centered in the content band.
    gif_path = os.path.join(OUTPUT_DIR, gif_name)
    if os.path.exists(gif_path):
        pic = slide.shapes.add_picture(gif_path,
                                       Inches(0.3), Inches(1.0),
                                       width=Inches(8.5))
        band_top, band_h = Inches(1.0), Inches(6.0)
        pic.top = band_top + int((band_h - pic.height) / 2)

    # Right sidebar
    sidebar_l = Inches(8.9)
    y = Inches(1.1)

    add_text(slide, "Results", sidebar_l, y, Inches(4.0), Inches(0.4),
             font_size=13, bold=True, color=ACCENT)
    y += Inches(0.45)

    colors_map = {
        "Smart Stop":  GREEN,
        "Smart Safe":  PURPLE,
        "Roundabout":  ACCENT,
        "Traditional": RED,
    }
    for alg, time in scenario_results.items():
        c = next((v for k, v in colors_map.items() if alg.startswith(k)), WHITE)
        add_rect(slide, sidebar_l, y, Inches(3.9), Inches(0.52), DARK_CARD)
        add_text(slide, alg,
                 sidebar_l + Inches(0.12), y + Inches(0.06),
                 Inches(2.4), Inches(0.4), font_size=13, color=c)
        add_text(slide, time,
                 sidebar_l + Inches(2.5), y + Inches(0.06),
                 Inches(1.3), Inches(0.4), font_size=13, bold=True,
                 color=WHITE, align=PP_ALIGN.RIGHT)
        y += Inches(0.58)

    y += Inches(0.3)
    add_text(slide, description,
             sidebar_l, y, Inches(4.0), Inches(1.4),
             font_size=13, color=LIGHT_GRAY, wrap=True)
    y += Inches(1.5)

    add_rect(slide, sidebar_l, y, Inches(3.9), Inches(0.04), ACCENT)
    y += Inches(0.15)
    add_text(slide, "Key Insight", sidebar_l, y, Inches(4.0), Inches(0.35),
             font_size=12, bold=True, color=ACCENT)
    y += Inches(0.38)
    add_text(slide, key_insight,
             sidebar_l, y, Inches(4.0), Inches(1.4),
             font_size=13, color=WHITE, wrap=True)

    return slide


def timeline_row(slide, y, era, device, world, color):
    """One row of the traffic-device history timeline."""
    add_rect(slide, Inches(0.5), y, Inches(1.9), Inches(1.05), color)
    add_text(slide, era, Inches(0.6), y + Inches(0.28), Inches(1.7),
             Inches(0.5), font_size=17, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER)
    add_rect(slide, Inches(2.5), y, Inches(3.1), Inches(1.05), DARK_CARD)
    add_text(slide, device, Inches(2.65), y + Inches(0.1), Inches(2.85),
             Inches(0.85), font_size=15, bold=True, color=color)
    add_rect(slide, Inches(5.7), y, Inches(7.1), Inches(1.05), DARK_CARD)
    add_text(slide, world, Inches(5.85), y + Inches(0.08), Inches(6.8),
             Inches(0.9), font_size=13, color=LIGHT_GRAY)


# ===========================================================================
# Build slides — deck v2 narrative
# ===========================================================================

def build():
    prs = new_prs()

    # -------------------------------------------------------------------
    # SLIDE 1 — Title
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    add_rect(slide, 0, 0, Inches(0.18), H, ACCENT)
    add_text(slide, "Smart Stop",
             Inches(0.55), Inches(2.0), Inches(10), Inches(1.4),
             font_size=72, bold=True, color=WHITE)
    add_text(slide, "The intersection controller for the next era of the American road",
             Inches(0.55), Inches(3.4), Inches(11.5), Inches(0.7),
             font_size=26, color=ACCENT)
    add_text(slide, "Simulation-validated intersection control  ·  no new roads, no construction",
             Inches(0.55), Inches(6.6), Inches(12), Inches(0.5),
             font_size=14, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 2 — History: every era re-invents the intersection
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "A short history of the intersection")
    add_text(slide, "Every era re-invents intersection control for its traffic",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.65),
             font_size=30, bold=True, color=WHITE)

    timeline_row(slide, Inches(1.8), "1700s-1800s", "The circle\n(market squares, plazas)",
                 "Based on natural landscapes and replicated in city design. "
                 "Mixed traffic — pedestrians, horses, carriages — flows "
                 "around a center.", BLUE)
    timeline_row(slide, Inches(2.95), "1915", "The stop sign\n(Detroit)",
                 "A mediator for early cars joining horses and pedestrians in "
                 "traffic. A cheap, unmistakable right-of-way sign and rule "
                 "anyone can follow.", RED)
    timeline_row(slide, Inches(4.1), "1914-1920s", "The traffic signal\n(Cleveland, Detroit)",
                 "As more cars take to the road, crossings grow too busy for "
                 "stop signs or human traffic cops. Timed, light-based signal "
                 "mediation — an expanded stop-sign ruleset with added "
                 "complexity. (An 1868 gas version in London exploded; the "
                 "idea waited 50 years for electricity.)", GREEN)
    timeline_row(slide, Inches(5.25), "1966", "The modern roundabout\n(UK)",
                 "The historical roundabout reinvented to accommodate more "
                 "traffic and cars at modern speeds. Same ruleset, new "
                 "application and architecture. Proof that even century-old "
                 "devices get reinvented when the traffic changes.", ACCENT)

    add_text(slide, "Each device solved the problem of its era's traffic — and we are facing "
             "a new problem which requires a new solution that melds legacy technology "
             "with modern needs.",
             Inches(0.5), Inches(6.6), Inches(12.3), Inches(0.6),
             font_size=15, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 3 — The new world
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "The new era", GREEN)
    add_text(slide, "Today's intersection serves a new kind of traffic that legacy controllers cannot adequately address",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=26, bold=True, color=WHITE)

    cols = [
        ("Human drivers", RED,
         "Unique and varying reaction times, habits, imperfect rule-"
         "following, and outright cheating. Traditional mediation devices "
         "treat them all identically — one at a time, no matter what."),
        ("Semi-autonomous", ACCENT,
         "Driver-assist cars that can react instantly and predictably — "
         "but still carry a human in the loop who may override the "
         "consistent functioning of the ruleset."),
        ("Autonomous", GREEN,
         "A consistent, predictable ruleset that other vehicles' actions "
         "can still force into unpredictable behavior. Vehicles could "
         "coordinate precisely — if the intersection were capable of "
         "coordinating them."),
    ]
    for i, (title, color, body) in enumerate(cols):
        x = Inches(0.4 + i * 4.3)
        add_rect(slide, x, Inches(1.9), Inches(4.1), Inches(3.6), DARK_CARD)
        add_rect(slide, x, Inches(1.9), Inches(4.1), Inches(0.07), color)
        add_text(slide, title, x + Inches(0.2), Inches(2.1), Inches(3.7),
                 Inches(0.5), font_size=19, bold=True, color=color)
        add_text(slide, body, x + Inches(0.2), Inches(2.75), Inches(3.7),
                 Inches(2.6), font_size=14, color=LIGHT_GRAY, wrap=True)

    add_rect(slide, Inches(0.4), Inches(5.8), Inches(12.5), Inches(0.9), DARK_CARD)
    add_text(slide, "The intersection needs a device for THIS mix. That device is the Smart Stop.",
             Inches(0.6), Inches(6.0), Inches(12.1), Inches(0.5),
             font_size=20, bold=True, color=WHITE)
    add_text(slide, "Scope of this deck: vehicle-to-vehicle traffic (human, semi-, and fully "
             "autonomous). Pedestrians, cyclists, and multi-lane crossings are the next phase — see roadmap.",
             Inches(0.5), Inches(6.95), Inches(12.3), Inches(0.45),
             font_size=12, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 4 — What Smart Stop is
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Smart Stop", GREEN)
    add_text(slide, "A stop sign that works like a traffic signal",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=30, bold=True, color=WHITE)
    add_bullet(slide, [
        "A camera watches the approaches; traditional stop-sign rules still require a stop. A per-approach GREEN FLASH signals when to go.",
        "The system reads turn signals to optimally coordinate which vehicles can safely move through the intersection — prioritizing BOTH each vehicle's wait time and the overall throughput of the system. Vehicles without conflicting paths travel at the same time.",
        "Whole queues are released together as platoons; an approaching car can be waved through without stopping (\"rolling green\").",
        "A violation camera photographs anyone who runs the flash — the red-light-camera principle applied to a stop sign. Compliance is incentivized: consistent signaling and rule-following make the system work better for everyone.",
    ], Inches(0.6), Inches(1.8), Inches(7.9), Inches(4.2),
       font_size=16, color=LIGHT_GRAY)

    add_rect(slide, Inches(8.9), Inches(1.8), Inches(3.9), Inches(3.4), DARK_CARD)
    add_rect(slide, Inches(8.9), Inches(1.8), Inches(3.9), Inches(0.08), GREEN)
    add_text(slide, "THE FAIL-SAFE", Inches(9.1), Inches(2.0), Inches(3.5),
             Inches(0.4), font_size=14, bold=True, color=ACCENT)
    add_text(slide, "A dead Smart Stop is exactly today's stop sign.",
             Inches(9.1), Inches(2.5), Inches(3.5), Inches(1.0),
             font_size=19, bold=True, color=WHITE)
    add_text(slide, "Power cut, camera fault, software crash — drivers see a "
             "normal octagon and do what they've done since 1915. No new "
             "failure mode is introduced.",
             Inches(9.1), Inches(3.6), Inches(3.5), Inches(1.5),
             font_size=13, color=LIGHT_GRAY)

    add_text(slide, "A sign-controller upgrade: no lane redesign, no signal poles, no roundabout construction.",
             Inches(0.5), Inches(6.9), Inches(12.3), Inches(0.45),
             font_size=14, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 5 — How to read the demos
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Reading the animations")
    add_text(slide, "How to read the demos that follow",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.65),
             font_size=30, bold=True, color=WHITE)

    add_text(slide, "Arrow colors = the driver's turn signal",
             Inches(0.5), Inches(1.8), Inches(6.0), Inches(0.45),
             font_size=16, bold=True, color=LIGHT_GRAY)
    for i, (c, label, desc) in enumerate([
            (PURPLE, "Purple", "turning right"),
            (GREEN,  "Green",  "turning left"),
            (ACCENT, "Orange", "going straight")]):
        y = Inches(2.35 + i * 0.8)
        add_rect(slide, Inches(0.5), y + Inches(0.05), Inches(0.4), Inches(0.5), c)
        add_text(slide, f"{label} — {desc}", Inches(1.1), y, Inches(5.0),
                 Inches(0.6), font_size=17, color=WHITE)

    add_text(slide, "Stop-sign colors = what the sign is telling that lane",
             Inches(7.0), Inches(1.8), Inches(6.0), Inches(0.45),
             font_size=16, bold=True, color=LIGHT_GRAY)
    for i, (c, label, desc) in enumerate([
            (RED,      "Red",   "wait"),
            (GREEN,    "Green", "go now"),
            (MID_GRAY, "Gray",  "nobody there")]):
        y = Inches(2.35 + i * 0.8)
        add_rect(slide, Inches(7.0), y + Inches(0.05), Inches(0.4), Inches(0.5), c)
        add_text(slide, f"{label} — {desc}", Inches(7.6), y, Inches(5.0),
                 Inches(0.6), font_size=17, color=WHITE)

    add_rect(slide, Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.5), DARK_CARD)
    add_text(slide, "Each demo shows two intersections handling the IDENTICAL arrival of cars, side by side, on the same clock.",
             Inches(0.7), Inches(5.35), Inches(11.9), Inches(0.5),
             font_size=16, bold=True, color=WHITE)
    add_text(slide, "Watch how many cars are moving at once — and who is left waiting. A yellow ring marks a car we're tracking.",
             Inches(0.7), Inches(5.95), Inches(11.9), Inches(0.5),
             font_size=14, color=LIGHT_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 6 — Round 1: simple crossings
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Round 1 - simple crossings", GREEN)
    add_text(slide, "Single car per lane: who clears fastest?",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=30, bold=True, color=WHITE)
    add_text(slide, "348 scenarios, 2-4 cars with every mix of turns, run through all three "
             "intersections under identical physics and honest human-driver behavior:",
             Inches(0.5), Inches(1.7), Inches(12.3), Inches(0.8),
             font_size=16, color=LIGHT_GRAY, wrap=True)

    metric_card(slide, "77%", "Smart Stop\nfastest  (267 of 348)",
                Inches(0.9), Inches(2.7), w=Inches(3.6), h=Inches(2.0),
                value_color=GREEN)
    metric_card(slide, "23%", "Roundabout\nfastest  (81 of 348)",
                Inches(4.9), Inches(2.7), w=Inches(3.6), h=Inches(2.0),
                value_color=ACCENT)
    metric_card(slide, "0%", "Traditional stop\nfastest  (0 of 348)",
                Inches(8.9), Inches(2.7), w=Inches(3.6), h=Inches(2.0),
                value_color=RED)

    add_bullet(slide, [
        "Why Smart Stop wins: when two paths don't cross — say, opposite drivers both turning right — it releases both at once. A stop sign can't.",
        "Why the roundabout takes 23%: with few cars and lots of left turns, circulating can beat stop-and-go.",
        "Why Traditional never wins: strict one-at-a-time is the slowest possible rule. It never wins a single scenario.",
    ], Inches(0.7), Inches(5.0), Inches(12.0), Inches(2.0),
       font_size=14, color=LIGHT_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 7 — Round 2: queues form (GIF C)
    # -------------------------------------------------------------------
    gif_slide(prs,
        "Round 2 - queues form: whole lines move, not one car at a time",
        "reality_C_platoon.gif",
        {"Smart Stop": "1 green window", "Traditional": "1 car per turn"},
        "Five cars queued on one road plus cross traffic. Smart Stop flashes "
        "the whole line through in a single green window, each car following "
        "~3 seconds behind the last; the stop sign serves one car, waits for "
        "it to clear, then serves the next.",
        "This is the mechanism behind everything that follows: releasing "
        "platoons instead of individuals is why Smart Stop handles roughly "
        "4x the traffic a stop sign can before jamming.",
    )

    # -------------------------------------------------------------------
    # SLIDE 8 — Round 2: rush hour numbers
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Round 2 - rush hour", GREEN)
    add_text(slide, "Turn up the traffic and the gap becomes a chasm",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=30, bold=True, color=WHITE)

    metric_card(slide, "~4x", "the traffic a stop sign\ncan handle before jamming\n(600-800 vs 2,400+ cars/hr)",
                Inches(0.9), Inches(1.9), w=Inches(3.6), h=Inches(2.2), value_color=GREEN)
    metric_card(slide, "~40x", "less average waiting than\nreal-world 4-way stop behavior\nat moderate traffic",
                Inches(4.9), Inches(1.9), w=Inches(3.6), h=Inches(2.2), value_color=GREEN)
    metric_card(slide, "+49%", "advantage even when 25%\nof drivers don't signal\n(real-world measured rate)",
                Inches(8.9), Inches(1.9), w=Inches(3.6), h=Inches(2.2), value_color=GREEN)

    add_bullet(slide, [
        "At 600 cars/hour: a driver waits 0.5 seconds on average under Smart Stop vs 21.7 at a human-run 4-way stop.",
        "At 1,200 cars/hour: 3.7 seconds vs 240.5 — the stop sign has effectively failed; Smart Stop hasn't noticed yet.",
        "The comparison is honest: our 4-way baseline includes the informal pairing real drivers do (which is ~3x better than the strict one-at-a-time rule).",
    ], Inches(0.7), Inches(4.5), Inches(12.0), Inches(2.2),
       font_size=15, color=LIGHT_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 9 — Smart Safe: the bridge
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Smart Safe - the bridge", PURPLE)
    add_text(slide, "You don't have to jump to the new regime in one step",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=30, bold=True, color=WHITE)
    add_text(slide, "Smart Safe is the conservative mode: same hardware, same flashes, but it "
             "only releases combinations with extra-wide safety spacing. It's the on-ramp "
             "from today's stop sign to full Smart Stop.",
             Inches(0.5), Inches(1.7), Inches(12.3), Inches(0.9),
             font_size=16, color=LIGHT_GRAY, wrap=True)

    metric_card(slide, "+42%", "faster than a Traditional\nstop (wins 336 of 348\nscenarios = 97%)",
                Inches(0.9), Inches(2.9), w=Inches(3.6), h=Inches(2.2), value_color=PURPLE)
    metric_card(slide, "4.0 m", "minimum spacing ever\nobserved between cars -\nthe widest of any mode",
                Inches(4.9), Inches(2.9), w=Inches(3.6), h=Inches(2.2), value_color=PURPLE)
    metric_card(slide, "82%", "of full Smart Stop's\nspeed - the rest is\nwaiting to be unlocked",
                Inches(8.9), Inches(2.9), w=Inches(3.6), h=Inches(2.2), value_color=PURPLE)

    add_text(slide, "Deployment story: install once, run Smart Safe while the community adapts, "
             "then graduate to full Smart Stop. Honest note: Smart Safe alone does not beat a "
             "roundabout — full Smart Stop is the destination.",
             Inches(0.5), Inches(5.6), Inches(12.3), Inches(0.9),
             font_size=15, italic=True, color=MID_GRAY, wrap=True)

    # -------------------------------------------------------------------
    # SLIDE 10 — Where the roundabout still wins
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Full disclosure", RED)
    add_text(slide, "One pattern still belongs to the roundabout",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=30, bold=True, color=WHITE)

    rows = [
        ("Light traffic, any pattern", "Smart Stop", GREEN,
         "cars are waved through without stopping"),
        ("A busy road crossing a quiet one (the common case)", "Smart Stop", GREEN,
         "waits nearly HALVED: 37.7 s vs 73.3 s at 2,000 cars/hr"),
        ("One dominant direction", "Even -> Smart Stop", ACCENT,
         "neck-and-neck at 2,000; Smart Stop ahead by 2,400"),
        ("All four directions equally slammed", "Roundabout", RED,
         "37.5 s vs our 53.6 s at 2,400 - the ring's home turf"),
    ]
    y = Inches(1.9)
    for label, winner, wc, note in rows:
        add_rect(slide, Inches(0.5), y, Inches(6.2), Inches(0.95), DARK_CARD)
        add_text(slide, label, Inches(0.7), y + Inches(0.12), Inches(5.9),
                 Inches(0.75), font_size=15, bold=True, color=WHITE)
        add_rect(slide, Inches(6.8), y, Inches(2.4), Inches(0.95), DARK_CARD)
        add_text(slide, winner, Inches(6.95), y + Inches(0.26), Inches(2.2),
                 Inches(0.5), font_size=15, bold=True, color=wc)
        add_rect(slide, Inches(9.3), y, Inches(3.5), Inches(0.95), DARK_CARD)
        add_text(slide, note, Inches(9.45), y + Inches(0.1), Inches(3.3),
                 Inches(0.8), font_size=12, color=LIGHT_GRAY)
        y += Inches(1.05)

    add_text(slide, "We state the loss because the numbers are honest either way - and perfectly "
             "balanced heavy traffic is also the rarest pattern in the real world, where "
             "intersections overwhelmingly skew busy-road-crossing-quiet-road.",
             Inches(0.5), Inches(6.3), Inches(12.3), Inches(0.9),
             font_size=14, italic=True, color=MID_GRAY, wrap=True)

    # -------------------------------------------------------------------
    # SLIDE 11 — GIF B: the busy road
    # -------------------------------------------------------------------
    gif_slide(prs,
        "The common case: a busy road crossing a quiet one",
        "reality_B_arterial.gif",
        {"Smart Stop": "37.7 s", "Roundabout": "73.3 s"},
        "Heavy two-way traffic on the main road, light traffic on the side "
        "street, 2,000 cars/hour. On the roundabout the two main streams "
        "keep blocking each other's entry; Smart Stop releases them as "
        "opposing platoons that share the intersection.",
        "This is the most common real-world pattern, and Smart Stop nearly "
        "halves the average wait across the entire traffic range we tested "
        "- and the verdict doesn't change under any published calibration "
        "of driver behavior.",
    )

    # -------------------------------------------------------------------
    # SLIDE 12 — GIF A: the side street
    # -------------------------------------------------------------------
    gif_slide(prs,
        "The side street: the busy road waits, not you",
        "reality_A_starvation.gif",
        {"Roundabout (worst run)": "72 s vs 14 s",
         "Roundabout": "side st. loses 3/5 runs",
         "Smart Stop": "busy road pays, 5/5"},
        "One dominant flow pouring past a side street's entrance (yellow "
        "ring = a side-street car we're tracking). On a roundabout, "
        "whether the side street gets squeezed is luck of the traffic "
        "rhythm; Smart Stop serves it on schedule, every time.",
        "Neither device fully blocks the side street - but the roundabout "
        "made it wait LONGER than the busy road in 3 of 5 test runs "
        "(worst: 72 s vs 14 s). Under Smart Stop the busy road absorbs "
        "the wait in every run. Guaranteed by the rotation itself.",
    )

    # -------------------------------------------------------------------
    # SLIDE 13 — Safety: how we tried to break it
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Safety", RED)
    add_text(slide, "We attacked our own design - here's what broke and what held",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.7),
             font_size=28, bold=True, color=WHITE)

    arc = [
        ("Slow and fast drivers mixed", RED,
         "Give every driver a different reaction time (0.5-2 s) and two "
         "green-lit cars can drift dangerously close - we found passes at "
         "2.29 m, about half a car width apart. FIXED: the controller now "
         "only pairs cars that stay safe under EVERY possible reaction "
         "time. Minimum spacing since: 3.38 m, every test."),
        ("Drivers who don't signal", ACCENT,
         "25% of real drivers turn without signaling (field-measured). "
         "Smart Stop treats a missing signal as 'could go anywhere' and "
         "plans for the worst case: a left turn, the maximum-conflict "
         "path through the intersection. The Smart Stop advantage "
         "survives - even at 100% unsignaled."),
        ("Drivers who run the flash", GREEN,
         "We simulated impatient drivers jumping the green. Unmitigated, "
         "that causes crashes - so the controller freezes new releases the "
         "moment its camera sees unauthorized motion, and cars brake "
         "defensively. Result: zero collisions in every test, even with "
         "10% of drivers cheating. The violation camera then pushes "
         "real-world cheating far below that tested rate."),
    ]
    for i, (title, color, body) in enumerate(arc):
        x = Inches(0.4 + i * 4.3)
        add_rect(slide, x, Inches(1.9), Inches(4.1), Inches(4.4), DARK_CARD)
        add_rect(slide, x, Inches(1.9), Inches(4.1), Inches(0.08), color)
        add_text(slide, title, x + Inches(0.2), Inches(2.1), Inches(3.75),
                 Inches(0.7), font_size=17, bold=True, color=color)
        add_text(slide, body, x + Inches(0.2), Inches(2.9), Inches(3.75),
                 Inches(3.3), font_size=13, color=LIGHT_GRAY, wrap=True)

    add_text(slide, "Plus the fail-safe: any fault and it's an ordinary stop sign again. "
             "Margin fine-tuning for lopsided traffic patterns is the one open calibration item - "
             "documented, bounded, zero collisions.",
             Inches(0.5), Inches(6.5), Inches(12.3), Inches(0.7),
             font_size=13, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # SLIDE 14 — Next steps
    # -------------------------------------------------------------------
    slide = blank_slide(prs)
    fill_bg(slide)
    section_header(slide, "Next steps", ACCENT)
    add_text(slide, "From validated simulation to a real intersection",
             Inches(0.5), Inches(0.9), Inches(12.5), Inches(0.65),
             font_size=30, bold=True, color=WHITE)

    cols = [
        ("Finish the controller", ACCENT, [
            "Share pre-flash speed gains fairly with side streets",
            "Widen safety margins on lopsided traffic patterns",
            "Fairness tuning at extreme saturation",
        ]),
        ("Widen the world", GREEN, [
            "Pedestrians and cyclists in the model",
            "Multi-lane approaches",
            "Explicit autonomous-vehicle coordination modes",
        ]),
        ("Make it physical", BLUE, [
            "Hardware sign-controller specification",
            "Pilot intersection candidate + partners",
            "Smart Safe first, graduate to full Smart Stop",
        ]),
    ]
    for i, (title, color, items) in enumerate(cols):
        x = Inches(0.4 + i * 4.3)
        add_rect(slide, x, Inches(1.85), Inches(4.1), Inches(4.6), DARK_CARD)
        add_rect(slide, x, Inches(1.85), Inches(4.1), Inches(0.07), color)
        add_text(slide, title, x + Inches(0.2), Inches(2.05), Inches(3.75),
                 Inches(0.5), font_size=19, bold=True, color=color)
        for j, item in enumerate(items):
            add_text(slide, f"-  {item}",
                     x + Inches(0.2), Inches(2.75 + j * 1.05), Inches(3.75),
                     Inches(1.0), font_size=14, color=LIGHT_GRAY, wrap=True)

    add_text(slide, "Every number in this deck traces to CLAIMS.md - the project's audited ledger "
             "of what may honestly be said. The regimes we lose are in here too. That's the point.",
             Inches(0.5), Inches(6.7), Inches(12.3), Inches(0.6),
             font_size=14, italic=True, color=MID_GRAY)

    # -------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------
    prs.save(PPTX_PATH)
    print(f"[ok] Presentation saved to: {PPTX_PATH}")
    print(f"     Slides: {len(prs.slides)}")


if __name__ == "__main__":
    build()
